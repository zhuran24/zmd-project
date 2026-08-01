#!/usr/bin/env python3
"""Persistent, package-role AB16 hierarchical budget broker.

The role is research-only and is not a launcher.  A future bootstrap starts the
role from package-pinned bytes and passes its only control socket.  The broker
owns one :class:`FormalBudgetBroker`; arms receive non-refundable reservations
from that account rather than independent budgets.
"""

from __future__ import annotations

from array import array
from collections.abc import Callable, Mapping, Sequence
import ctypes
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import resource
import secrets
import signal
import socket
import stat
import struct
import sys
import threading
from types import ModuleType
from typing import Any, Final, Protocol, TypedDict, cast

if __package__:
    from . import ab16_budget_authority_v1 as budget
    from . import ab16_outer_guardian_v1 as guardian
else:
    import ab16_budget_authority_v1 as budget
    import ab16_outer_guardian_v1 as guardian


PACKAGE_ROLE: Final = "ab16-budget-broker-v1"
REQUEST_SCHEMA: Final = "noncert-cuts-ab16-budget-broker-request-v1"
RESPONSE_SCHEMA: Final = "noncert-cuts-ab16-budget-broker-response-v1"
ROOT_INVENTORY_SCHEMA: Final = "noncert-cuts-ab16-formal-root-inventory-v1"
RECOVERY_DISARM_INTENT_SCHEMA: Final = (
    "noncert-cuts-ab16-recovery-disarm-intent-v1"
)
JOURNAL_SCHEMA: Final = "noncert-cuts-ab16-budget-broker-journal-event-v1"
FORMAL_BUDGET_JOURNAL_LABEL: Final = (
    "AB16 formal budget journal segment"
)
PREPARED_EXTENT_SCHEMA: Final = "noncert-cuts-ab16-budget-prepared-extent-v1"
ARM_ALLOCATION_SCHEMA: Final = (
    "noncert-cuts-ab16-arm-budget-allocation-v1"
)
ARM_RECONCILE_SCHEMA: Final = (
    "noncert-cuts-ab16-arm-budget-reconcile-v1"
)
ARM_TERMINAL_SCHEMA: Final = (
    "noncert-cuts-ab16-arm-budget-terminal-v1"
)
ACTOR_SCHEMA: Final = "noncert-cuts-ab16-budget-broker-actor-v1"
AUTHENTICATION_SCHEMA: Final = (
    "noncert-cuts-ab16-budget-broker-authentication-v1"
)
MANAGER_OPENFILE_AUTHENTICATION_SCHEMA: Final = (
    "noncert-cuts-ab16-budget-broker-manager-openfile-authentication-v1"
)
MANAGER_OPENFILE_GRANT_SCHEMA: Final = (
    "noncert-cuts-ab16-budget-broker-manager-openfile-grant-v1"
)
MANAGER_OPENFILE_SELECTION_BINDING_SCHEMA: Final = (
    "noncert-cuts-ab16-budget-broker-manager-openfile-selection-binding-v1"
)
MANAGER_OPENFILE_ARM_AUTHENTICATION_SCHEMA: Final = (
    "noncert-cuts-ab16-budget-broker-manager-openfile-arm-authentication-v1"
)
MANAGER_OPENFILE_ARM_GRANT_SCHEMA: Final = (
    "noncert-cuts-ab16-budget-broker-manager-openfile-arm-grant-v1"
)
SESSION_GRANT_SCHEMA: Final = (
    "noncert-cuts-ab16-budget-broker-session-grant-v1"
)
FORMAL_LAUNCH_OWNER_HANDOFF_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-launch-owner-broker-handoff-v1"
)
FORMAL_LAUNCH_OWNER_CLAIM_AUTHENTICATION_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-launch-owner-claim-authentication-v1"
)
FORMAL_LAUNCH_OWNER_CLAIM_IDENTITY_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-launch-owner-claim-identity-v1"
)
FORMAL_CLOSEOUT_OWNER_HANDOFF_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-closeout-owner-broker-handoff-v1"
)
TRANSFER_ACK_SCHEMA: Final = (
    "noncert-cuts-ab16-budget-broker-transfer-ack-v1"
)
ABANDONED_RESERVATION_SCHEMA: Final = (
    "noncert-cuts-ab16-abandoned-reservation-v1"
)
DETACHED_TRANSFER_INCOMPLETE_SCHEMA: Final = (
    "noncert-cuts-ab16-detached-transfer-incomplete-v1"
)
PRIOR_SEAL_RESPONSE_ACCEPTED_SCHEMA: Final = (
    "noncert-cuts-ab16-prior-arm-seal-response-accepted-v1"
)
CLOSURE_CONTROL_TRANSFER_SCHEMA: Final = (
    "noncert-cuts-ab16-closure-control-transfer-v1"
)
BOOTSTRAP_HANDOFF_SCHEMA: Final = (
    "noncert-cuts-ab16-formal-root-budget-handoff-v2"
)
BOOTSTRAP_STRUCTURAL_HANDOFF_SCHEMA: Final = (
    "noncert-cuts-ab16-bootstrap-structural-handoff-v1"
)
BOOTSTRAP_BUDGET_ACCOUNT_HANDOFF_SCHEMA: Final = (
    "noncert-cuts-ab16-bootstrap-budget-account-handoff-v1"
)
BOOTSTRAP_STAGING_HANDOFF_SCHEMA: Final = (
    "noncert-cuts-ab16-bootstrap-staging-handoff-v1"
)
BOOTSTRAP_RETAINED_DIRECTORY_HANDOFF_SCHEMA: Final = (
    "noncert-cuts-ab16-bootstrap-retained-directory-handoff-v1"
)
FINAL_RELEASE_PARENT_HANDOFF_SCHEMA: Final = (
    "noncert-cuts-ab16-outside-final-release-adopted-handoff-v1"
)
OUTSIDE_FINAL_RELEASE_CAPABILITY_SCHEMA: Final = (
    "noncert-cuts-ab16-outside-final-release-capability-v1"
)
BOOTSTRAP_HANDOFF_SPEC_PATH: Final = "formal-root-budget-handoff.json"
CALIBRATION_TOOL_ROLES: Final = frozenset(
    {
        "aggregator",
        "alternate_replayer",
        "fd_loader",
        "observer_harness",
        "package_verifier",
        "primary_replayer",
        "protocol",
        "runner",
        "workload",
    }
)
CAMPAIGN_RUN_NONCE_RE: Final = re.compile(
    r"run-[A-Za-z0-9][A-Za-z0-9._-]{4,123}\Z"
)
FALSE_AUTHORITY_BOUNDARY: Final = {
    "changes_certified_exact": False,
    "changes_cut_state": False,
    "changes_lower_bound": False,
    "changes_production": False,
    "changes_upper_bound": False,
    "research_only": True,
}
ARM_FALSE_AUTHORIZATIONS: Final = {
    "changes_lower_bound": False,
    "changes_upper_bound": False,
    "certified_authority": False,
    "cut_authority": False,
    "formal_campaign_creation_authorized": False,
    "organic_arm_launch_authorized": False,
    "production_authority": False,
    "solver_run_authorized": False,
    "whole_witness_authority": False,
}
ARM_MANIFEST_NAME: Final = "attempt-artifact-manifest.json"
ARM_TERMINAL_DIRECTORY: Final = "budget/arm-terminals"
ARM_REPLAY_DIRECTORY: Final = "replays/arm-attempt-roots"
ARM_CONSUMPTION_DIRECTORY: Final = "prospective/consumptions"
ARM_MANIFEST_ARTIFACT_CLASS: Final = "publication"
ARM_TERMINAL_ARTIFACT_CLASS: Final = "closeout"
ARM_REPLAY_ARTIFACT_CLASS: Final = "closeout"
ARM_CONSUMPTION_ARTIFACT_CLASS: Final = "closeout"
ARM_MANIFEST_BUDGET_LABEL: Final = (
    "AB16 organic attempt artifact manifest"
)
ARM_TERMINAL_BUDGET_LABEL: Final = "AB16 arm budget terminal"
ARM_REPLAY_BUDGET_LABEL: Final = "AB16 organic attempt root replay"
ARM_CONSUMPTION_BUDGET_LABEL: Final = "organic arm consumption"
ENDPOINT_SCHEMA: Final = "noncert-cuts-ab16-budget-broker-endpoint-v1"
DEFAULT_SOCKET_RELATIVE_PATH: Final = "control/budget-broker.sock"
DEFAULT_RETIRED_SOCKET_RELATIVE_PATH: Final = (
    "control/budget-broker.sock.retired"
)
RECOVERY_PURPOSES: Final = frozenset(
    {
        "recovery-closeout",
        "recovery-takeover-consumption",
    }
)
CLOSURE_PURPOSES: Final = frozenset(
    {
        "failure-terminal-release",
        "formal-budget-terminal",
        "formal-closure-consumption",
        "formal-manifest",
        "recovery-disarm-terminal",
        "success-dual-lock-release",
    }
)

MAX_FRAME_BYTES: Final = 256 * 1024
MAX_RECEIVED_FDS: Final = 8
JOURNAL_MAX_BYTES: Final = 4096
_STAGING_PREFIX: Final = ".ab16-budget-runtime-stage-"
_READ_FLAGS: Final = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
_DIRECTORY_FLAGS: Final = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
_WRITE_FLAGS: Final = os.O_RDWR | os.O_CLOEXEC | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW


class BrokerProtocolError(RuntimeError):
    """A broker frame, identity, budget, or descriptor invariant failed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class DescriptorIdentity(TypedDict):
    device: int
    inode: int
    mode_octal: str
    size_bytes: int
    uid: int


class ParentIdentity(TypedDict):
    device: int
    inode: int
    mode_octal: str
    uid: int


class PreparedExtentRecord(TypedDict):
    schema_version: str
    artifact_class: str
    maximum_bytes: int
    parent_identity: ParentIdentity
    parent_path: str
    staging_identity: DescriptorIdentity
    staging_name: str
    target_name: str


class NativeHelperProtocol(Protocol):
    @property
    def final_seal_mask(self) -> int: ...

    def get_seals(self, descriptor: int) -> int: ...

    def close_range_allowlist(self, descriptors: Sequence[int]) -> None: ...

    def create_memfd(self, name: str) -> int: ...

    def has_writable_mapping(self, descriptor: int) -> bool: ...

    def install_no_filesystem_writes_landlock(self) -> None: ...

    def install_final_seals(self, descriptor: int) -> int: ...

    def landlock_abi(self) -> int: ...

    def recv_fd(self, socket_fd: int) -> int: ...

    def send_fd(self, socket_fd: int, descriptor: int) -> None: ...


class NativeHelperAuthorizationProtocol(Protocol):
    """Package-pinned ownership handle for one native helper instance."""

    @property
    def helper(self) -> NativeHelperProtocol: ...

    def retained_descriptors(self) -> tuple[int, ...]: ...

    def close(self) -> None: ...


class PackageRoleAuthorizationProtocol(Protocol):
    """Post-verifier gate supplied by the package bootstrap authority.

    The protocol deliberately names no bootstrap artifact fields.  Its real
    implementation must refuse until the independently verified package replay
    has passed and the requested role bytes are retained from that package.
    """

    def require_verified_role(self, role: str) -> None: ...

    def retained_descriptors(self) -> tuple[int, ...]: ...

    def role_descriptors(self) -> dict[str, int]: ...

    def load_verified_role(self, role: str) -> ModuleType: ...

    def selected_fd_transport(self) -> dict[str, object]: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class ReceivedFrame:
    record: dict[str, object]
    descriptors: tuple[int, ...]
    sha256: str
    peer: dict[str, int]


@dataclass(frozen=True)
class PreparedExtent:
    """One non-refundable preallocated inode and its absent target."""

    artifact_class: str
    maximum_bytes: int
    parent_identity: ParentIdentity
    parent_path: str
    staging_name: str
    target_name: str
    staging_identity: DescriptorIdentity

    def as_record(self) -> dict[str, object]:
        return {
            "schema_version": PREPARED_EXTENT_SCHEMA,
            "artifact_class": self.artifact_class,
            "maximum_bytes": self.maximum_bytes,
            "parent_identity": dict(self.parent_identity),
            "parent_path": self.parent_path,
            "staging_name": self.staging_name,
            "target_name": self.target_name,
            "staging_identity": dict(self.staging_identity),
        }


@dataclass(frozen=True)
class FixedDirectory:
    """One package-bound directory and its final access mode."""

    path: str
    mode: int

    def as_record(self) -> dict[str, object]:
        return {
            "mode_octal": f"{self.mode:04o}",
            "path": self.path,
        }


@dataclass(frozen=True)
class _FixedPublicationRule:
    artifact_class: str
    branch: str
    label: str
    maximum_bytes: int
    maximum_publications: int
    paths: frozenset[str]


@dataclass(frozen=True)
class _AppendPublicationRule:
    artifact_class: str
    channel: str
    label: str
    maximum_bytes: int
    maximum_segments: int
    parent_path: str


@dataclass(frozen=True)
class FixedPurposeSpec:
    """One package-bound physical reservation and its sole final target."""

    parent_path: str
    target_name: str
    artifact_class: str
    exact_maximum_bytes: int | None = None


@dataclass(frozen=True)
class _BrokerLiveness:
    actor: Mapping[str, object]
    pidfd: int


FIXED_PURPOSE_SPECS: Final = {
    "formal-budget-terminal": FixedPurposeSpec(
        "formal-closure",
        "budget-terminal.json",
        "closeout",
        64 * 1024,
    ),
    "formal-closure-consumption": FixedPurposeSpec(
        "locks",
        "formal-closure-consumption.json",
        "metadata",
        4096,
    ),
    "formal-manifest": FixedPurposeSpec(
        "formal-closure",
        "formal-manifest.json",
        "metadata",
        64 * 1024,
    ),
    "recovery-closeout": FixedPurposeSpec(
        "closeout",
        "formal-consumed-incomplete.json",
        "closeout",
    ),
    "recovery-disarm-terminal": FixedPurposeSpec(
        "formal-closure",
        "recovery-disarm-terminal.json",
        "closeout",
    ),
    "recovery-takeover-consumption": FixedPurposeSpec(
        "locks",
        "recovery-takeover-consumption.json",
        "metadata",
        4096,
    ),
}
OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE: Final = "formal-ab16/final-release"
OUTSIDE_FINAL_RELEASE_MAXIMUM_BYTES: Final = 4 * 1024 * 1024
OUTSIDE_FINAL_RELEASE_SPECS: Final = {
    "failure-terminal-release": "failure-terminal-release.json",
    "formal-root-replay-alternate-receipt": (
        "formal-root-replay-alternate.json"
    ),
    "formal-root-replay-primary-receipt": (
        "formal-root-replay-primary.json"
    ),
    "success-dual-lock-release": "dual-lock-release.json",
}


class FinalReleaseParentCapability:
    """The sole owner of the four outside-root replay/release extents."""

    def __init__(
        self,
        *,
        descriptor: int,
        directory_path: str,
        path: Path,
        purpose: str,
        owner_nonce: str,
        identity: Mapping[str, object],
        extent_descriptors: Mapping[str, int],
        extent_records: Mapping[str, Mapping[str, object]],
    ) -> None:
        self._descriptor = descriptor
        self._directory_path = directory_path
        self._path = Path(os.path.abspath(path))
        self._purpose = purpose
        self._owner_nonce = owner_nonce
        self._identity = dict(identity)
        self._extent_descriptors = dict(extent_descriptors)
        self._extent_records = {
            purpose_name: dict(record)
            for purpose_name, record in extent_records.items()
        }
        self._closed = False
        self._detached = False

    @property
    def path(self) -> Path:
        return self._path

    def retained_descriptors(self) -> tuple[int, ...]:
        self._require_live()
        return (
            self._descriptor,
            *(
                self._extent_descriptors[purpose]
                for purpose in sorted(OUTSIDE_FINAL_RELEASE_SPECS)
            ),
        )

    def record(self) -> dict[str, object]:
        self._require_live()
        return {
            "directory_identity": dict(self._identity),
            "directory_path": self._directory_path,
            "extent_records": {
                purpose: dict(self._extent_records[purpose])
                for purpose in sorted(OUTSIDE_FINAL_RELEASE_SPECS)
            },
            "owner_nonce": self._owner_nonce,
            "path": str(self._path),
            "purpose": self._purpose,
            "schema_version": OUTSIDE_FINAL_RELEASE_CAPABILITY_SCHEMA,
        }

    def detach_for_closure(
        self,
    ) -> tuple[int, dict[str, tuple[dict[str, object], int]]]:
        self._require_live()
        self._detached = True
        parent_fd = self._descriptor
        extents = {
            purpose: (
                dict(self._extent_records[purpose]),
                self._extent_descriptors[purpose],
            )
            for purpose in sorted(OUTSIDE_FINAL_RELEASE_SPECS)
        }
        self._descriptor = -1
        self._extent_descriptors.clear()
        return parent_fd, extents

    def _require_live(self) -> None:
        if self._closed or self._detached:
            raise BrokerProtocolError(
                "FINAL_RELEASE_CAPABILITY_CLOSED",
                "outside final-release capability is no longer live",
            )
        joined_fd = -1
        primary: BaseException | None = None
        try:
            joined_fd = budget._open_absolute_directory_no_symlinks(  # noqa: SLF001
                self._path
            )
            if (
                _parent_identity(self._descriptor) != self._identity
                or _parent_identity(joined_fd) != self._identity
            ):
                raise BrokerProtocolError(
                    "FINAL_RELEASE_PARENT_IDENTITY_DRIFT",
                    "outside final-release parent identity drifted",
                )
        except BaseException as exc:
            primary = exc
            raise
        finally:
            if joined_fd >= 0:
                try:
                    os.close(joined_fd)
                except BaseException as close_exc:
                    if primary is None:
                        raise
                    primary.add_note(
                        "outside final-release path-join FD close also failed: "
                        f"{type(close_exc).__name__}: {close_exc}"
                    )
        for purpose, descriptor in self._extent_descriptors.items():
            if _identity(descriptor) != self._extent_records[purpose]["staging_identity"]:
                raise BrokerProtocolError(
                    "FINAL_RELEASE_EXTENT_IDENTITY_DRIFT",
                    f"outside final-release extent {purpose!r} drifted",
                )

    def close(self) -> None:
        if self._closed:
            raise BrokerProtocolError(
                "FINAL_RELEASE_CAPABILITY_ALREADY_CLOSED",
                "outside final-release capability cannot close twice",
            )
        self._closed = True
        primary: BaseException | None = None
        parent_fd = self._descriptor
        extent_fds = tuple(self._extent_descriptors.values())
        for descriptor in extent_fds:
            try:
                os.fchmod(descriptor, 0o444)
                os.fsync(descriptor)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        "outside final-release staging seal also failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
        if parent_fd >= 0:
            try:
                os.fsync(parent_fd)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        "outside final-release parent fsync also failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
        descriptors = (() if parent_fd < 0 else (parent_fd,)) + extent_fds
        self._descriptor = -1
        self._extent_descriptors.clear()
        for descriptor in descriptors:
            try:
                os.close(descriptor)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        "outside final-release descriptor close also failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
        if primary is not None:
            raise primary

    def release_parent_copy(self) -> None:
        """Drop one post-fork parent copy after the child accepted ownership."""

        if self._closed or self._detached:
            raise BrokerProtocolError(
                "FINAL_RELEASE_CAPABILITY_CLOSED",
                "outside final-release parent copy cannot be released twice",
            )
        self._closed = True
        descriptors = (
            self._descriptor,
            *self._extent_descriptors.values(),
        )
        self._descriptor = -1
        self._extent_descriptors.clear()
        primary: BaseException | None = None
        for descriptor in descriptors:
            try:
                os.close(descriptor)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        "outside final-release parent-copy close also failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
        if primary is not None:
            raise primary


@dataclass(frozen=True)
class BrokerSessionGrant:
    """One exact-use peer credential bound to a supervisor or one arm."""

    role: str
    credential_sha256: str
    expected_peer: dict[str, int]
    arm_slot: str | None
    selection_identity: dict[str, object] | None
    allocation_identity: dict[str, object] | None

    def as_record(self) -> dict[str, object]:
        return {
            "schema_version": SESSION_GRANT_SCHEMA,
            "allocation_identity": self.allocation_identity,
            "arm_slot": self.arm_slot,
            "credential_sha256": self.credential_sha256,
            "expected_peer": dict(self.expected_peer),
            "role": self.role,
            "selection_identity": self.selection_identity,
        }


@dataclass
class _ManagerOpenFileGrant:
    credential_sha256: str
    manager_epoch_identity: dict[str, object]
    selection_path: str
    attempt_consumption_identity: dict[str, object]
    unit_name: str
    grant_kind: str = "formal-supervisor"
    arm_slot: str | None = None
    allocation_identity: dict[str, object] | None = None
    preregistered_selection_identity: dict[str, object] | None = None
    selection_identity: dict[str, object] | None = None
    application_peer: dict[str, int] | None = None
    guardian_ready_identity: dict[str, object] | None = None
    pidfd: int | None = None
    pidfd_method: str | None = None
    owner_credential_sha256: str | None = None
    owner_peer: dict[str, int] | None = None


def canonical_json_bytes(value: object) -> bytes:
    return budget.canonical_json_bytes(value)


def strict_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw,
            parse_constant=lambda token: (_ for _ in ()).throw(
                BrokerProtocolError("NONFINITE_JSON", f"{label} contains {token}")
            ),
        )
    except BrokerProtocolError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BrokerProtocolError("INVALID_JSON", f"{label} is not strict JSON") from exc
    if type(value) is not dict:
        raise BrokerProtocolError("INVALID_FRAME", f"{label} is not one object")
    if canonical_json_bytes(value) != raw:
        raise BrokerProtocolError("NONCANONICAL_FRAME", f"{label} is not canonical")
    return dict(value)


def _canonical_path_types(
    value: object,
    *,
    label: str,
) -> list[dict[str, str]]:
    if type(value) is not list:
        raise BrokerProtocolError(
            "ROOT_INVENTORY_DRIFT",
            f"{label} is not one path/type list",
        )
    result: list[dict[str, str]] = []
    for index, item in enumerate(cast(list[object], value)):
        if (
            type(item) is not dict
            or set(cast(dict[str, object], item)) != {"path", "type"}
            or cast(dict[str, object], item)["type"]
            not in {"directory", "regular"}
        ):
            raise BrokerProtocolError(
                "ROOT_INVENTORY_DRIFT",
                f"{label}[{index}] shape differs",
            )
        path_value = cast(dict[str, object], item)["path"]
        if (
            not isinstance(path_value, str)
            or not path_value
            or "\x00" in path_value
            or "\\" in path_value
        ):
            raise BrokerProtocolError(
                "ROOT_INVENTORY_DRIFT",
                f"{label}[{index}] path is invalid",
            )
        parsed = PurePosixPath(path_value)
        if parsed.is_absolute() or any(
            part in {"", ".", ".."} for part in parsed.parts
        ):
            raise BrokerProtocolError(
                "ROOT_INVENTORY_DRIFT",
                f"{label}[{index}] path is not relative",
            )
        path = str(parsed)
        result.append(
            {
                "path": path,
                "type": cast(str, cast(dict[str, object], item)["type"]),
            }
        )
    canonical = sorted(result, key=lambda item: (item["path"], item["type"]))
    if result != canonical or len({item["path"] for item in result}) != len(result):
        raise BrokerProtocolError(
            "ROOT_INVENTORY_DRIFT",
            f"{label} is not canonical or has duplicate paths",
        )
    return result


def _path_types_for_prefix(
    value: Sequence[Mapping[str, object]],
    *,
    prefix: str,
) -> list[dict[str, str]]:
    prefix_parts = PurePosixPath(prefix).parts
    result: list[dict[str, str]] = []
    for raw in value:
        path = cast(str, raw["path"])
        parts = PurePosixPath(path).parts
        if parts[: len(prefix_parts)] != prefix_parts:
            continue
        if len(parts) == len(prefix_parts):
            continue
        result.append(
            {
                "path": str(PurePosixPath(*parts)),
                "type": cast(str, raw["type"]),
            }
        )
    result.sort(key=lambda item: (item["path"], item["type"]))
    return result


def process_starttime(pid: int) -> int:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        suffix = raw.rsplit(")", 1)[1].split()
        value = int(suffix[19])
    except (OSError, IndexError, ValueError) as exc:
        raise BrokerProtocolError("PROCESS_IDENTITY_FAILED", f"cannot read PID {pid} starttime") from exc
    if value <= 0:
        raise BrokerProtocolError("PROCESS_IDENTITY_FAILED", f"PID {pid} starttime is invalid")
    return value


def process_identity(pid: int | None = None) -> dict[str, int]:
    observed = os.getpid() if pid is None else pid
    return {
        "pid": observed,
        "pid_starttime": process_starttime(observed),
        "uid": os.getuid(),
    }


def pidfd_reports_exit(descriptor: int) -> bool:
    poller = __import__("select").poll()
    poller.register(descriptor, __import__("select").POLLIN | __import__("select").POLLHUP)
    return bool(poller.poll(0))


def open_pidfd(pid: int) -> tuple[int, str]:
    """Open a pidfd without embedding an architecture-specific syscall number."""

    opener = getattr(os, "pidfd_open", None)
    if opener is not None:
        try:
            return int(opener(pid, 0)), "python-os.pidfd_open"
        except OSError as exc:
            raise BrokerProtocolError("PIDFD_OPEN_FAILED", f"cannot open pidfd for PID {pid}") from exc
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "pidfd_open", None)
    if function is None:
        raise BrokerProtocolError(
            "PIDFD_CAPABILITY_MISSING",
            "neither os.pidfd_open nor libc pidfd_open is available",
        )
    function.argtypes = [ctypes.c_int, ctypes.c_uint]
    function.restype = ctypes.c_int
    descriptor = int(function(pid, 0))
    if descriptor < 0:
        number = ctypes.get_errno()
        raise BrokerProtocolError(
            "PIDFD_OPEN_FAILED",
            f"libc pidfd_open failed for PID {pid}: errno={number}",
        )
    return descriptor, "libc-pidfd_open"


def preserve_spawn_cleanup_failure(
    primary: BaseException,
    *,
    label: str,
    cleanup: Callable[[], object],
) -> None:
    """Run one post-fork cleanup action without masking the original error."""

    try:
        cleanup()
    except BaseException as cleanup_error:
        primary.add_note(
            f"{label} cleanup also failed: "
            f"{type(cleanup_error).__name__}: {cleanup_error}"
        )


def terminate_and_reap_spawned_child(
    pid: int,
    *,
    primary: BaseException,
) -> None:
    """Force one exact post-fork child terminal and reap it before PID reuse."""

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except BaseException as cleanup_error:
        primary.add_note(
            "exact-child SIGKILL cleanup also failed: "
            f"{type(cleanup_error).__name__}: {cleanup_error}"
        )
    try:
        while True:
            try:
                reaped_pid, _status = os.waitpid(pid, 0)
                break
            except InterruptedError:
                continue
        if reaped_pid != pid:
            raise BrokerProtocolError(
                "SPAWN_CHILD_REAP_DRIFT",
                "post-fork cleanup reaped a different child",
            )
    except BaseException as cleanup_error:
        primary.add_note(
            "exact-child blocking reap also failed: "
            f"{type(cleanup_error).__name__}: {cleanup_error}"
        )


def pidfd_send_signal(descriptor: int, signum: int) -> str:
    """Signal the exact pidfd target without an architecture syscall number."""

    sender = getattr(signal, "pidfd_send_signal", None)
    if callable(sender):
        sender(descriptor, signum)
        return "python-signal.pidfd_send_signal"
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "pidfd_send_signal", None)
    if function is None:
        raise BrokerProtocolError(
            "PIDFD_SIGNAL_CAPABILITY_MISSING",
            "neither signal.pidfd_send_signal nor libc pidfd_send_signal is available",
        )
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    if function(descriptor, signum, None, 0) != 0:
        number = ctypes.get_errno()
        raise BrokerProtocolError(
            "PIDFD_SIGNAL_FAILED",
            f"libc pidfd_send_signal failed: errno={number}",
        )
    return "libc-pidfd_send_signal"


def _peer_identity(connection: socket.socket) -> dict[str, int]:
    size = __import__("struct").calcsize("3i")
    raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size)
    pid, uid, gid = __import__("struct").unpack("3i", raw)
    return {
        "gid": gid,
        "pid": pid,
        "pid_starttime": process_starttime(pid),
        "uid": uid,
    }


def _socket_type(connection: socket.socket) -> None:
    observed = connection.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
    if observed != socket.SOCK_SEQPACKET:
        raise BrokerProtocolError("WRONG_SOCKET_TYPE", "broker requires SOCK_SEQPACKET")


def _consume_socket_descriptor(
    descriptor: int,
    *,
    label: str,
) -> socket.socket:
    """Consume one caller FD on every path and return one owned socket."""

    if (
        isinstance(descriptor, bool)
        or not isinstance(descriptor, int)
        or descriptor < 0
    ):
        raise BrokerProtocolError(
            "SOCKET_DESCRIPTOR_INVALID",
            f"{label} is not one descriptor",
        )
    duplicate = -1
    try:
        duplicate = fcntl.fcntl(
            descriptor,
            fcntl.F_DUPFD_CLOEXEC,
            20,
        )
    except BaseException:
        try:
            os.close(descriptor)
        except BaseException:
            pass
        raise
    try:
        os.close(descriptor)
    except BaseException:
        try:
            os.close(duplicate)
        except BaseException:
            pass
        raise
    try:
        return socket.socket(fileno=duplicate)
    except BaseException as exc:
        try:
            os.close(duplicate)
        except BaseException as cleanup_error:
            exc.add_note(
                f"{label} duplicate cleanup failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
        raise


def send_frame(
    connection: socket.socket,
    record: Mapping[str, object],
    *,
    descriptors: Sequence[int] = (),
) -> str:
    _socket_type(connection)
    raw = canonical_json_bytes(dict(record))
    if len(raw) > MAX_FRAME_BYTES:
        raise BrokerProtocolError("FRAME_TOO_LARGE", "broker frame exceeds its fixed maximum")
    ancillary: list[tuple[int, int, bytes]] = []
    if descriptors:
        values = array("i", descriptors)
        ancillary.append((socket.SOL_SOCKET, socket.SCM_RIGHTS, values.tobytes()))
    written = connection.sendmsg([raw], ancillary)
    if written != len(raw):
        raise BrokerProtocolError("SHORT_FRAME_WRITE", "broker frame write was incomplete")
    return hashlib.sha256(raw).hexdigest()


def receive_frame(
    connection: socket.socket,
    *,
    expected_fd_counts: frozenset[int] = frozenset({0}),
    require_message_credentials: bool = False,
) -> ReceivedFrame:
    _socket_type(connection)
    if not expected_fd_counts or not expected_fd_counts <= frozenset(range(MAX_RECEIVED_FDS + 1)):
        raise BrokerProtocolError("INVALID_FD_EXPECTATION", "broker descriptor expectation is invalid")
    credential_size = struct.calcsize("3i")
    ancillary_size = socket.CMSG_SPACE(MAX_RECEIVED_FDS * array("i").itemsize)
    if require_message_credentials:
        if connection.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED) != 1:
            raise BrokerProtocolError(
                "MESSAGE_CREDENTIALS_DISABLED",
                "credential-bound frame requires SO_PASSCRED before any message is sent",
            )
        ancillary_size += socket.CMSG_SPACE(credential_size)
    raw, ancillary, flags, _address = connection.recvmsg(MAX_FRAME_BYTES + 1, ancillary_size)
    descriptors: list[int] = []
    credentials: tuple[int, int, int] | None = None
    try:
        if not raw:
            raise BrokerProtocolError("PEER_CLOSED", "broker peer closed")
        if len(raw) > MAX_FRAME_BYTES or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            raise BrokerProtocolError("TRUNCATED_FRAME", "broker frame was truncated")
        for level, kind, data in ancillary:
            if (
                level == socket.SOL_SOCKET
                and kind == socket.SCM_CREDENTIALS
            ):
                if credentials is not None or len(data) != credential_size:
                    raise BrokerProtocolError(
                        "INVALID_PEER_CREDENTIALS",
                        "broker peer credential frame is duplicated or malformed",
                    )
                credentials = struct.unpack("3i", data)
                continue
            if level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS:
                raise BrokerProtocolError("UNEXPECTED_ANCILLARY", "broker received unknown ancillary data")
            if len(data) % array("i").itemsize:
                raise BrokerProtocolError("INVALID_FD_FRAME", "broker descriptor frame is malformed")
            values = array("i")
            values.frombytes(data)
            descriptors.extend(values.tolist())
        if len(descriptors) not in expected_fd_counts:
            raise BrokerProtocolError(
                "FD_COUNT_MISMATCH",
                f"received {len(descriptors)} descriptors, expected {sorted(expected_fd_counts)}",
            )
        for descriptor in descriptors:
            fcntl.fcntl(descriptor, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
        if require_message_credentials and credentials is None:
            raise BrokerProtocolError(
                "PEER_CREDENTIALS_MISSING",
                "broker frame lacks kernel-supplied sender credentials",
            )
        if credentials is None:
            peer = _peer_identity(connection)
        else:
            pid, uid, gid = credentials
            peer = {
                "gid": gid,
                "pid": pid,
                "pid_starttime": process_starttime(pid),
                "uid": uid,
            }
        return ReceivedFrame(
            record=strict_canonical_object(raw, label="broker frame"),
            descriptors=tuple(descriptors),
            sha256=hashlib.sha256(raw).hexdigest(),
            peer=peer,
        )
    except BaseException:
        for descriptor in descriptors:
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise


def close_unlisted_descriptors(allowed: set[int]) -> None:
    """Close inherited descriptors and prove the post-fork allowlist exactly."""

    def open_descriptors() -> set[int]:
        result: set[int] = set()
        for name in os.listdir("/proc/self/fd"):
            if not name.isdecimal():
                continue
            descriptor = int(name)
            try:
                os.fstat(descriptor)
            except OSError:
                continue
            result.add(descriptor)
        return result

    keep = {0, 1, 2, *allowed}
    try:
        observed = open_descriptors()
    except OSError as exc:
        raise BrokerProtocolError("FD_ENUMERATION_FAILED", "cannot enumerate /proc/self/fd") from exc
    for descriptor in sorted(observed - keep):
        try:
            os.close(descriptor)
        except OSError as exc:
            if exc.errno != __import__("errno").EBADF:
                raise BrokerProtocolError("FD_CLEANUP_FAILED", f"cannot close inherited FD {descriptor}") from exc
    remaining = open_descriptors()
    leaked = {descriptor for descriptor in remaining if descriptor > 2 and descriptor not in allowed}
    if leaked:
        raise BrokerProtocolError("FD_ALLOWLIST_FAILED", f"unexpected retained descriptors: {sorted(leaked)}")


def _exact_keys(value: Mapping[str, object], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise BrokerProtocolError("FRAME_SHAPE_MISMATCH", f"{label} keys differ")


def _nonce(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise BrokerProtocolError("INVALID_NONCE", "broker nonce must be 32 canonical hex bytes")
    return value


def _sha256(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise BrokerProtocolError(
            "IDENTITY_SHAPE_MISMATCH",
            f"{label} is not one canonical SHA-256",
        )
    return value


def _claim_identity(
    value: object,
    *,
    label: str,
) -> dict[str, object]:
    if type(value) is not dict:
        raise BrokerProtocolError(
            "CLAIM_IDENTITY_DRIFT",
            f"{label} is not one object",
        )
    _exact_keys(
        value,
        {"schema_version", "seal_mask", "sha256", "size_bytes"},
        label=label,
    )
    if (
        value["schema_version"]
        != FORMAL_LAUNCH_OWNER_CLAIM_IDENTITY_SCHEMA
        or type(value["seal_mask"]) is not int
        or type(value["size_bytes"]) is not int
        or value["size_bytes"] != 64
    ):
        raise BrokerProtocolError(
            "CLAIM_IDENTITY_DRIFT",
            f"{label} metadata differs",
        )
    return {
        "schema_version": value["schema_version"],
        "seal_mask": value["seal_mask"],
        "sha256": _sha256(value["sha256"], label=f"{label} SHA-256"),
        "size_bytes": value["size_bytes"],
    }


def _sealed_claim_memfd(
    helper: NativeHelperProtocol,
    token: str,
) -> tuple[int, dict[str, object]]:
    raw = _nonce(token).encode("ascii")
    descriptor = helper.create_memfd("ab16-formal-launch-owner-claim")
    try:
        offset = 0
        while offset < len(raw):
            written = os.pwrite(descriptor, raw[offset:], offset)
            if written <= 0:
                raise BrokerProtocolError(
                    "CLAIM_MEMFD_WRITE_FAILED",
                    "formal-launch claim memfd write made no progress",
                )
            offset += written
        os.fsync(descriptor)
        if (
            os.fstat(descriptor).st_size != len(raw)
            or helper.has_writable_mapping(descriptor)
        ):
            raise BrokerProtocolError(
                "CLAIM_MEMFD_IDENTITY_DRIFT",
                "formal-launch claim memfd differs before sealing",
            )
        seals = helper.install_final_seals(descriptor)
        if (
            seals != helper.final_seal_mask
            or helper.get_seals(descriptor) != helper.final_seal_mask
        ):
            raise BrokerProtocolError(
                "CLAIM_MEMFD_SEAL_FAILED",
                "formal-launch claim memfd seal mask differs",
            )
        identity = {
            "schema_version": FORMAL_LAUNCH_OWNER_CLAIM_IDENTITY_SCHEMA,
            "seal_mask": seals,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        return descriptor, identity
    except BaseException:
        os.close(descriptor)
        raise


def _verify_claim_memfd(
    helper: NativeHelperProtocol,
    descriptor: int,
    expected: Mapping[str, object],
) -> None:
    identity = _claim_identity(
        expected,
        label="formal-launch owner claim",
    )
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 0
        or metadata.st_size != identity["size_bytes"]
        or helper.get_seals(descriptor) != identity["seal_mask"]
        or helper.has_writable_mapping(descriptor)
        or budget._sha256_descriptor(  # noqa: SLF001
            descriptor,
            size_bytes=cast(int, identity["size_bytes"]),
        )
        != identity["sha256"]
    ):
        raise BrokerProtocolError(
            "CLAIM_MEMFD_IDENTITY_DRIFT",
            "formal-launch owner claim memfd differs",
        )


def _message_identity(value: Mapping[str, object]) -> dict[str, object]:
    raw = canonical_json_bytes(dict(value))
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _package_role_source_identity(
    authorization: PackageRoleAuthorizationProtocol,
    role: str,
) -> dict[str, object]:
    authorization.require_verified_role(role)
    descriptors = authorization.role_descriptors()
    try:
        descriptor = descriptors[role]
    except KeyError as exc:
        raise BrokerProtocolError(
            "PACKAGE_ROLE_NOT_RETAINED",
            f"package role descriptor is absent: {role!r}",
        ) from exc
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size <= 0:
        raise BrokerProtocolError(
            "PACKAGE_ROLE_IDENTITY_DRIFT",
            f"package role descriptor is not one non-empty regular file: {role!r}",
        )
    return {
        "sha256": budget._sha256_descriptor(  # noqa: SLF001
            descriptor,
            size_bytes=metadata.st_size,
        ),
        "size_bytes": metadata.st_size,
    }


def _detached_identity(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict or set(value) != {"path", "sha256", "size_bytes"}:
        raise BrokerProtocolError(
            "IDENTITY_SHAPE_MISMATCH",
            f"{label} is not one detached identity",
        )
    path = value["path"]
    digest = value["sha256"]
    size = value["size_bytes"]
    if (
        not isinstance(path, str)
        or not Path(path).is_absolute()
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        or isinstance(size, bool)
        or not isinstance(size, int)
        or size < 0
    ):
        raise BrokerProtocolError(
            "IDENTITY_SHAPE_MISMATCH",
            f"{label} detached identity is invalid",
        )
    return dict(value)


def _content_identity(value: object, *, label: str) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value) != {"sha256", "size_bytes"}
        or not isinstance(value["sha256"], str)
        or len(value["sha256"]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value["sha256"]
        )
        or isinstance(value["size_bytes"], bool)
        or not isinstance(value["size_bytes"], int)
        or value["size_bytes"] <= 0
    ):
        raise BrokerProtocolError(
            "IDENTITY_SHAPE_MISMATCH",
            f"{label} is not one content identity",
        )
    return dict(value)


def _calibration_tool_content_identities(
    value: object,
) -> dict[str, dict[str, object]]:
    if type(value) is not dict or set(value) != CALIBRATION_TOOL_ROLES:
        raise BrokerProtocolError(
            "CALIBRATION_TOOL_IDENTITY_DRIFT",
            "calibration tool role set differs from the package cohort",
        )
    return {
        role: _content_identity(
            identity,
            label=f"calibration tool {role}",
        )
        for role, identity in sorted(value.items())
    }


def _resource_calibration_authorization_bundles(
    value: object,
) -> dict[str, dict[str, object]]:
    stages = {
        "FULL_PREFLIGHT",
        "GATE_B_QUALIFICATION",
        "FORMAL_ORGANIC_ARM",
    }
    if type(value) is not dict or set(value) != stages:
        raise BrokerProtocolError(
            "RESOURCE_CALIBRATION_BINDING_DRIFT",
            "resource calibration stage set differs",
        )
    checked: dict[str, dict[str, object]] = {}
    for stage, raw_entry in sorted(value.items()):
        if (
            type(raw_entry) is not dict
            or set(raw_entry) != {"identity", "record"}
            or type(raw_entry["record"]) is not dict
        ):
            raise BrokerProtocolError(
                "RESOURCE_CALIBRATION_BINDING_DRIFT",
                f"{stage} calibration envelope shape differs",
            )
        identity = _detached_identity(
            raw_entry["identity"],
            label=f"{stage} calibration bundle",
        )
        raw = canonical_json_bytes(raw_entry["record"])
        if (
            hashlib.sha256(raw).hexdigest() != identity["sha256"]
            or len(raw) != identity["size_bytes"]
        ):
            raise BrokerProtocolError(
                "RESOURCE_CALIBRATION_BINDING_DRIFT",
                f"{stage} calibration bundle content identity differs",
            )
        checked[stage] = {
            "identity": identity,
            "record": dict(raw_entry["record"]),
        }
    return checked


def _bootstrap_handoff_spec(value: object) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value)
        != {"artifact_class", "maximum_bytes", "relative_path"}
        or value["artifact_class"] != "metadata"
        or value["relative_path"] != BOOTSTRAP_HANDOFF_SPEC_PATH
        or isinstance(value["maximum_bytes"], bool)
        or not isinstance(value["maximum_bytes"], int)
        or value["maximum_bytes"] <= 0
    ):
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_SPEC_DRIFT",
            "bootstrap handoff requires its exact metadata target and positive extent",
        )
    return dict(value)


def _campaign_run_nonce(value: object) -> str:
    if (
        not isinstance(value, str)
        or CAMPAIGN_RUN_NONCE_RE.fullmatch(value) is None
    ):
        raise BrokerProtocolError(
            "CAMPAIGN_RUN_NONCE_DRIFT",
            "campaign run nonce is outside the bootstrap grammar",
        )
    return value


def _require_detached_bytes(
    value: object,
    *,
    expected_path: Path,
    label: str,
) -> dict[str, object]:
    identity = _detached_identity(value, label=label)
    if Path(cast(str, identity["path"])) != expected_path:
        raise BrokerProtocolError(
            "IDENTITY_PATH_MISMATCH",
            f"{label} names a different fixed path",
        )
    parent_fd = budget._open_absolute_directory_no_symlinks(  # noqa: SLF001
        expected_path.parent
    )
    descriptor = -1
    try:
        descriptor = os.open(
            expected_path.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size != identity["size_bytes"]
            or budget._sha256_descriptor(  # noqa: SLF001
                descriptor,
                size_bytes=metadata.st_size,
            )
            != identity["sha256"]
        ):
            raise BrokerProtocolError(
                "DETACHED_IDENTITY_DRIFT",
                f"{label} bytes differ",
            )
    except OSError as exc:
        raise BrokerProtocolError(
            "DETACHED_IDENTITY_DRIFT",
            f"{label} cannot be opened safely",
        ) from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)
    return identity


def _pidfd_target_pid(descriptor: int) -> int:
    try:
        lines = Path(f"/proc/self/fdinfo/{descriptor}").read_text(
            encoding="ascii"
        ).splitlines()
        raw = next(
            line.partition(":")[2].strip()
            for line in lines
            if line.startswith("Pid:")
        )
        pid = int(raw)
    except (OSError, StopIteration, ValueError) as exc:
        raise BrokerProtocolError(
            "PIDFD_IDENTITY_DRIFT",
            "pidfd target could not be identified",
        ) from exc
    if pid <= 0:
        raise BrokerProtocolError(
            "PIDFD_IDENTITY_DRIFT",
            "pidfd target is not a live positive PID",
        )
    return pid


def _peer_grant_identity(value: object, *, label: str) -> dict[str, int]:
    if type(value) is not dict or set(value) != {"pid", "pid_starttime", "uid"}:
        raise BrokerProtocolError(
            "PEER_IDENTITY_DRIFT",
            f"{label} peer identity shape differs",
        )
    checked: dict[str, int] = {}
    for field in ("pid", "pid_starttime", "uid"):
        item = value[field]
        if isinstance(item, bool) or not isinstance(item, int):
            raise BrokerProtocolError(
                "PEER_IDENTITY_DRIFT",
                f"{label} peer identity contains a non-integer",
            )
        checked[field] = item
    if checked["pid"] <= 0 or checked["pid_starttime"] <= 0 or checked["uid"] < 0:
        raise BrokerProtocolError(
            "PEER_IDENTITY_DRIFT",
            f"{label} peer identity is outside its valid range",
        )
    return checked


def build_session_grant(
    *,
    credential: str,
    expected_peer: Mapping[str, object],
    role: str,
    arm_slot: str | None = None,
    selection_identity: Mapping[str, object] | None = None,
    allocation_identity: Mapping[str, object] | None = None,
) -> BrokerSessionGrant:
    """Build one non-reusable authentication grant.

    The plaintext credential is transported out of band.  Only its SHA-256 is
    retained by the broker.  Arm grants additionally bind the selected formal
    attempt and the exact non-refundable arm allocation.
    """

    token = _nonce(credential)
    peer = _peer_grant_identity(dict(expected_peer), label="session grant")
    credential_sha256 = hashlib.sha256(token.encode("ascii")).hexdigest()
    if role in {
        "supervisor",
        "bootstrap-admin",
        "formal-closeout-owner",
        "formal-launch-owner",
        "formal-supervisor",
        "formal-worker",
    }:
        if (
            arm_slot is not None
            or selection_identity is not None
            or allocation_identity is not None
        ):
            raise BrokerProtocolError(
                "GRANT_SCOPE_DRIFT",
                f"{role} grant cannot carry arm bindings",
            )
        return BrokerSessionGrant(
            role=role,
            credential_sha256=credential_sha256,
            expected_peer=peer,
            arm_slot=None,
            selection_identity=None,
            allocation_identity=None,
        )
    if role != "arm" or not isinstance(arm_slot, str):
        raise BrokerProtocolError(
            "GRANT_SCOPE_DRIFT",
            "session grant role or arm slot is invalid",
        )
    try:
        slot = budget._safe_component(arm_slot, label="arm_slot")  # noqa: SLF001
    except budget.BudgetContractError as exc:
        raise BrokerProtocolError(
            "GRANT_SCOPE_DRIFT",
            "session grant arm slot is invalid",
        ) from exc
    selected = _detached_identity(
        selection_identity,
        label="session grant selection",
    )
    if (
        type(allocation_identity) is not dict
        or set(allocation_identity) != {"sha256", "size_bytes"}
        or not isinstance(allocation_identity["sha256"], str)
        or len(allocation_identity["sha256"]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in allocation_identity["sha256"]
        )
        or isinstance(allocation_identity["size_bytes"], bool)
        or not isinstance(allocation_identity["size_bytes"], int)
        or allocation_identity["size_bytes"] <= 0
    ):
        raise BrokerProtocolError(
            "GRANT_SCOPE_DRIFT",
            "session grant allocation identity is invalid",
        )
    return BrokerSessionGrant(
        role=role,
        credential_sha256=credential_sha256,
        expected_peer=peer,
        arm_slot=slot,
        selection_identity=selected,
        allocation_identity=dict(allocation_identity),
    )


def _positive_int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise BrokerProtocolError("INVALID_INTEGER", f"{label} must be a positive exact integer")
    return value


def _nonnegative_int(value: object, *, label: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise BrokerProtocolError(
            "PUBLICATION_CONTRACT_INVALID",
            f"{label} is not one nonnegative integer",
        )
    return value


def _contract_relative_path(value: object, *, label: str) -> str:
    if type(value) is not str:
        raise BrokerProtocolError(
            "PUBLICATION_CONTRACT_INVALID",
            f"{label} is not text",
        )
    try:
        parts = budget._relative_parts(  # noqa: SLF001
            value,
            allow_dot=False,
        )
    except Exception as exc:
        raise BrokerProtocolError(
            "PUBLICATION_CONTRACT_INVALID",
            f"{label} escaped the formal root",
        ) from exc
    return str(PurePosixPath(*parts))


def _fixed_paths_from_contract(
    value: object,
    *,
    label: str,
) -> frozenset[str]:
    if type(value) is not dict:
        raise BrokerProtocolError(
            "PUBLICATION_CONTRACT_INVALID",
            f"{label} path contract is not an object",
        )
    kind = value.get("kind")
    if kind == "fixed":
        _exact_keys(
            value,
            {"kind", "root", "root_relative_path"},
            label=f"{label} path contract",
        )
        if value["root"] != "formal-root":
            raise BrokerProtocolError(
                "PUBLICATION_CONTRACT_INVALID",
                f"{label} path root drifted",
            )
        return frozenset(
            {
                _contract_relative_path(
                    value["root_relative_path"],
                    label=f"{label} root_relative_path",
                )
            }
        )
    if kind == "indexed-template":
        _exact_keys(
            value,
            {
                "index_maximum",
                "index_minimum",
                "index_name",
                "kind",
                "root",
                "root_relative_path_template",
            },
            label=f"{label} path contract",
        )
        if (
            value["root"] != "formal-root"
            or value["index_name"] != "hook_id"
        ):
            raise BrokerProtocolError(
                "PUBLICATION_CONTRACT_INVALID",
                f"{label} indexed path identity drifted",
            )
        minimum = _nonnegative_int(
            value["index_minimum"],
            label=f"{label}.index_minimum",
        )
        maximum = _nonnegative_int(
            value["index_maximum"],
            label=f"{label}.index_maximum",
        )
        template = value["root_relative_path_template"]
        if type(template) is not str or minimum > maximum:
            raise BrokerProtocolError(
                "PUBLICATION_CONTRACT_INVALID",
                f"{label} indexed path range is invalid",
            )
        try:
            paths = {
                _contract_relative_path(
                    template.format(hook_id=index),
                    label=f"{label} indexed path",
                )
                for index in range(minimum, maximum + 1)
            }
        except (KeyError, ValueError) as exc:
            raise BrokerProtocolError(
                "PUBLICATION_CONTRACT_INVALID",
                f"{label} indexed template is invalid",
            ) from exc
        return frozenset(paths)
    if kind == "indexed-phase-template":
        _exact_keys(
            value,
            {
                "allowed_phases",
                "index_maximum",
                "index_minimum",
                "index_name",
                "kind",
                "root",
                "root_relative_path_template",
            },
            label=f"{label} path contract",
        )
        phases = value["allowed_phases"]
        if (
            value["root"] != "formal-root"
            or value["index_name"] != "hook_id"
            or phases != ["post", "pre"]
        ):
            raise BrokerProtocolError(
                "PUBLICATION_CONTRACT_INVALID",
                f"{label} indexed-phase identity drifted",
            )
        minimum = _nonnegative_int(
            value["index_minimum"],
            label=f"{label}.index_minimum",
        )
        maximum = _nonnegative_int(
            value["index_maximum"],
            label=f"{label}.index_maximum",
        )
        template = value["root_relative_path_template"]
        if type(template) is not str or minimum > maximum:
            raise BrokerProtocolError(
                "PUBLICATION_CONTRACT_INVALID",
                f"{label} indexed-phase range is invalid",
            )
        try:
            paths = {
                _contract_relative_path(
                    template.format(hook_id=index, phase=phase),
                    label=f"{label} indexed-phase path",
                )
                for index in range(minimum, maximum + 1)
                for phase in phases
            }
        except (KeyError, ValueError) as exc:
            raise BrokerProtocolError(
                "PUBLICATION_CONTRACT_INVALID",
                f"{label} indexed-phase template is invalid",
            ) from exc
        return frozenset(paths)
    if kind == "append-channel":
        _exact_keys(
            value,
            {"channel", "kind", "root"},
            label=f"{label} path contract",
        )
        if value["root"] != "formal-root" or type(value["channel"]) is not str:
            raise BrokerProtocolError(
                "PUBLICATION_CONTRACT_INVALID",
                f"{label} append path identity drifted",
            )
        return frozenset()
    raise BrokerProtocolError(
        "PUBLICATION_CONTRACT_INVALID",
        f"{label} path-contract kind is unsupported",
    )


def _validate_multiplicity_source(
    value: object,
    *,
    branch: str,
    maximum_publications: int,
    path_count: int,
    label: str,
) -> None:
    if type(value) is not dict or type(value.get("kind")) is not str:
        raise BrokerProtocolError(
            "PUBLICATION_CONTRACT_INVALID",
            f"{label} multiplicity source is malformed",
        )
    kind = value["kind"]
    if kind == "attach-hook":
        _exact_keys(
            value,
            {
                "kind",
                "maximum_attach_hooks",
                "publications_per_hook",
            },
            label=f"{label} multiplicity source",
        )
        hooks = _positive_int(
            value["maximum_attach_hooks"],
            label=f"{label}.maximum_attach_hooks",
        )
        per_hook = _positive_int(
            value["publications_per_hook"],
            label=f"{label}.publications_per_hook",
        )
        expected = hooks * per_hook
    elif kind == "append-channel-only":
        _exact_keys(
            value,
            {"kind", "maximum_fixed_publications"},
            label=f"{label} multiplicity source",
        )
        expected = _nonnegative_int(
            value["maximum_fixed_publications"],
            label=f"{label}.maximum_fixed_publications",
        )
    elif kind == "single-fixed-path":
        _exact_keys(
            value,
            {"kind", "maximum_fixed_publications"},
            label=f"{label} multiplicity source",
        )
        expected = _positive_int(
            value["maximum_fixed_publications"],
            label=f"{label}.maximum_fixed_publications",
        )
    elif kind == "terminal-branch-fixed-path":
        _exact_keys(
            value,
            {
                "kind",
                "maximum_fixed_publications",
                "terminal_branch",
            },
            label=f"{label} multiplicity source",
        )
        if value["terminal_branch"] != branch or branch not in {
            "success",
            "failure",
        }:
            raise BrokerProtocolError(
                "PUBLICATION_CONTRACT_INVALID",
                f"{label} terminal branch drifted",
            )
        expected = _positive_int(
            value["maximum_fixed_publications"],
            label=f"{label}.maximum_fixed_publications",
        )
    else:
        raise BrokerProtocolError(
            "PUBLICATION_CONTRACT_INVALID",
            f"{label} multiplicity-source kind is unsupported",
        )
    if (
        expected != maximum_publications
        or path_count != maximum_publications
    ):
        raise BrokerProtocolError(
            "PUBLICATION_CONTRACT_INVALID",
            f"{label} path/multiplicity cardinality drifted",
        )


class _PublicationPolicyState:
    """Broker-owned, non-refundable publication-count authority."""

    def __init__(
        self,
        *,
        formal_artifacts: Sequence[Mapping[str, object]],
        formal_channels: Sequence[Mapping[str, object]],
        arm_artifacts: Mapping[
            str, Mapping[str, Mapping[str, object]]
        ],
        arm_channels: Mapping[
            str, Sequence[Mapping[str, object]]
        ],
    ) -> None:
        fixed: dict[
            tuple[str | None, str], _FixedPublicationRule
        ] = {}
        channels: dict[
            tuple[str | None, str], _AppendPublicationRule
        ] = {}
        for index, raw in enumerate(formal_artifacts):
            item = dict(raw)
            _exact_keys(
                item,
                {
                    "artifact_class",
                    "label",
                    "maximum_bytes",
                    "path",
                    "required_on_success",
                },
                label=f"formal artifact[{index}]",
            )
            logical_label = item["label"]
            artifact_class = item["artifact_class"]
            if (
                type(logical_label) is not str
                or not logical_label
                or type(artifact_class) is not str
                or artifact_class not in budget.ARTIFACT_CLASSES
                or type(item["required_on_success"]) is not bool
            ):
                raise BrokerProtocolError(
                    "PUBLICATION_CONTRACT_INVALID",
                    "formal fixed-artifact identity is invalid",
                )
            key = (None, logical_label)
            if key in fixed:
                raise BrokerProtocolError(
                    "PUBLICATION_CONTRACT_INVALID",
                    "formal fixed-artifact label is duplicated",
                )
            fixed[key] = _FixedPublicationRule(
                artifact_class=artifact_class,
                branch="common",
                label=logical_label,
                maximum_bytes=_positive_int(
                    item["maximum_bytes"],
                    label=f"{logical_label}.maximum_bytes",
                ),
                maximum_publications=1,
                paths=frozenset(
                    {
                        _contract_relative_path(
                            item["path"],
                            label=f"{logical_label}.path",
                        )
                    }
                ),
            )
        self._parse_channels(
            formal_channels,
            arm_slot=None,
            result=channels,
        )
        if set(arm_artifacts) != set(arm_channels):
            raise BrokerProtocolError(
                "PUBLICATION_CONTRACT_INVALID",
                "arm publication/channel slot sets differ",
            )
        for raw_slot, raw_caps in sorted(arm_artifacts.items()):
            slot = budget._safe_component(  # noqa: SLF001
                raw_slot,
                label="arm_slot",
            )
            for logical_label, raw in sorted(raw_caps.items()):
                if type(raw) is not dict:
                    raise BrokerProtocolError(
                        "PUBLICATION_CONTRACT_INVALID",
                        f"{slot}.{logical_label} cap is not an object",
                    )
                _exact_keys(
                    raw,
                    {
                        "artifact_class",
                        "branch",
                        "maximum_bytes",
                        "maximum_publications",
                        "multiplicity_source",
                        "path_contract",
                    },
                    label=f"{slot}.{logical_label} cap",
                )
                artifact_class = raw["artifact_class"]
                branch = raw["branch"]
                if (
                    type(logical_label) is not str
                    or not logical_label
                    or type(artifact_class) is not str
                    or artifact_class not in budget.ARTIFACT_CLASSES
                    or branch not in {"common", "failure", "success"}
                ):
                    raise BrokerProtocolError(
                        "PUBLICATION_CONTRACT_INVALID",
                        f"{slot}.{logical_label} identity is invalid",
                    )
                maximum_publications = _nonnegative_int(
                    raw["maximum_publications"],
                    label=(
                        f"{slot}.{logical_label}.maximum_publications"
                    ),
                )
                paths = _fixed_paths_from_contract(
                    raw["path_contract"],
                    label=f"{slot}.{logical_label}",
                )
                _validate_multiplicity_source(
                    raw["multiplicity_source"],
                    branch=cast(str, branch),
                    maximum_publications=maximum_publications,
                    path_count=len(paths),
                    label=f"{slot}.{logical_label}",
                )
                key = (slot, logical_label)
                if key in fixed:
                    raise BrokerProtocolError(
                        "PUBLICATION_CONTRACT_INVALID",
                        f"{slot}.{logical_label} is duplicated",
                    )
                fixed[key] = _FixedPublicationRule(
                    artifact_class=cast(str, artifact_class),
                    branch=cast(str, branch),
                    label=logical_label,
                    maximum_bytes=_positive_int(
                        raw["maximum_bytes"],
                        label=f"{slot}.{logical_label}.maximum_bytes",
                    ),
                    maximum_publications=maximum_publications,
                    paths=paths,
                )
            self._parse_channels(
                arm_channels[slot],
                arm_slot=slot,
                result=channels,
            )
        for (slot, channel), rule in channels.items():
            if slot is None:
                continue
            fixed_rule = fixed.get((slot, rule.label))
            if (
                fixed_rule is None
                or fixed_rule.maximum_publications != 0
                or fixed_rule.paths
                or fixed_rule.artifact_class != rule.artifact_class
                or fixed_rule.maximum_bytes != rule.maximum_bytes
            ):
                raise BrokerProtocolError(
                    "PUBLICATION_CONTRACT_INVALID",
                    f"{slot}.{channel} lacks its append-only cap join",
                )
        fixed_path_owners: dict[tuple[str | None, str], str] = {}
        for (slot, logical_label), rule in fixed.items():
            for relative_path in rule.paths:
                path_key = (slot, relative_path)
                prior = fixed_path_owners.get(path_key)
                if prior is not None:
                    raise BrokerProtocolError(
                        "PUBLICATION_CONTRACT_INVALID",
                        (
                            f"{slot or 'formal'}.{relative_path} is assigned "
                            f"to both {prior!r} and {logical_label!r}"
                        ),
                    )
                fixed_path_owners[path_key] = logical_label
        self._fixed = fixed
        self._channels = channels
        self._counts = {key: 0 for key in fixed}
        self._segment_counts = {key: 0 for key in channels}
        self._arm_terminal_branch: dict[str, str] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _parse_channels(
        raw_channels: Sequence[Mapping[str, object]],
        *,
        arm_slot: str | None,
        result: dict[
            tuple[str | None, str], _AppendPublicationRule
        ],
    ) -> None:
        if not isinstance(raw_channels, Sequence) or isinstance(
            raw_channels,
            (str, bytes),
        ):
            raise BrokerProtocolError(
                "PUBLICATION_CONTRACT_INVALID",
                "append-channel table is not a sequence",
            )
        for index, raw in enumerate(raw_channels):
            if type(raw) is not dict:
                raise BrokerProtocolError(
                    "PUBLICATION_CONTRACT_INVALID",
                    "append-channel entry is not an object",
                )
            _exact_keys(
                raw,
                {
                    "artifact_class",
                    "channel",
                    "label",
                    "maximum_bytes",
                    "maximum_segments",
                    "multiplicity_derivation",
                    "parent_path",
                },
                label=f"append channel[{index}]",
            )
            channel = raw["channel"]
            logical_label = raw["label"]
            artifact_class = raw["artifact_class"]
            maximum_segments = _nonnegative_int(
                raw["maximum_segments"],
                label=f"{channel}.maximum_segments",
            )
            derivation = raw["multiplicity_derivation"]
            if (
                type(channel) is not str
                or not channel
                or type(logical_label) is not str
                or not logical_label
                or type(artifact_class) is not str
                or artifact_class not in budget.ARTIFACT_CLASSES
                or type(derivation) is not dict
                or derivation.get("result_maximum_segments")
                != maximum_segments
            ):
                raise BrokerProtocolError(
                    "PUBLICATION_CONTRACT_INVALID",
                    "append-channel identity or derivation drifted",
                )
            if arm_slot is None:
                if logical_label == "AB16 baseline cut segment":
                    _exact_keys(
                        derivation,
                        {
                            "basis",
                            "evidence_status",
                            "exhaustion",
                            "result_maximum_segments",
                        },
                        label=f"{channel}.multiplicity_derivation",
                    )
                    valid_derivation = (
                        derivation["basis"]
                        == "temporary unmeasured conservative baseline append cap"
                        and derivation["evidence_status"]
                        == "unmeasured-temporary"
                        and derivation["exhaustion"]
                        == "formal-consumed-incomplete"
                        and maximum_segments == 128
                    )
                elif logical_label == FORMAL_BUDGET_JOURNAL_LABEL:
                    _exact_keys(
                        derivation,
                        {
                            "basis",
                            "bootstrap_and_formal_control_allowance",
                            "derived_minimum_actions",
                            "evidence_status",
                            "exhaustion",
                            "formal_arm_count",
                            "maximum_segment_bytes",
                            "per_arm_append_maximum",
                            "per_arm_control_allowance",
                            "per_arm_fixed_publication_branch_maximum",
                            "retained_allocation_bytes",
                            "result_maximum_segments",
                            "segment_cap_basis",
                            "segment_count_rounding",
                            "sufficiency_claim",
                        },
                        label=f"{channel}.multiplicity_derivation",
                    )
                    derived_minimum = (
                        16 * (479 + 99 + 64) + 2048
                    )
                    valid_derivation = (
                        channel == "budget-journal"
                        and artifact_class == "metadata"
                        and raw["maximum_bytes"] == JOURNAL_MAX_BYTES
                        and raw["parent_path"] == "channels/budget-journal"
                        and derivation["basis"]
                        == (
                            "profile-derived data-plane maxima plus explicit "
                            "temporary control-plane allowances"
                        )
                        and derivation[
                            "bootstrap_and_formal_control_allowance"
                        ]
                        == 2048
                        and derivation["derived_minimum_actions"]
                        == derived_minimum
                        and derivation["evidence_status"]
                        == "unmeasured-temporary"
                        and derivation["exhaustion"]
                        == (
                            "fail before the next broker-journal append; "
                            "formal-consumed-incomplete"
                        )
                        and derivation["formal_arm_count"] == 16
                        and derivation["maximum_segment_bytes"]
                        == JOURNAL_MAX_BYTES
                        and derivation["per_arm_append_maximum"] == 479
                        and derivation["per_arm_control_allowance"] == 64
                        and derivation[
                            "per_arm_fixed_publication_branch_maximum"
                        ]
                        == 99
                        and derivation["retained_allocation_bytes"]
                        == JOURNAL_MAX_BYTES * 16_384
                        and derivation["result_maximum_segments"] == 16_384
                        and derivation["segment_cap_basis"]
                        == (
                            "policy-defined canonical action-record cap "
                            "pending comparable calibration"
                        )
                        and derivation["segment_count_rounding"]
                        == "next power of two above derived minimum actions"
                        and derivation["sufficiency_claim"] is False
                        and maximum_segments == 16_384
                    )
                else:
                    valid_derivation = False
                if not valid_derivation:
                    raise BrokerProtocolError(
                        "PUBLICATION_CONTRACT_INVALID",
                        "formal append-channel derivation drifted",
                    )
            else:
                _exact_keys(
                    derivation,
                    {
                        "formula",
                        "maximum_attach_hooks",
                        "maximum_generated_cuts",
                        "result_maximum_segments",
                    },
                    label=f"{channel}.multiplicity_derivation",
                )
                attach_hooks = _nonnegative_int(
                    derivation["maximum_attach_hooks"],
                    label=f"{channel}.maximum_attach_hooks",
                )
                generated_cuts = _nonnegative_int(
                    derivation["maximum_generated_cuts"],
                    label=f"{channel}.maximum_generated_cuts",
                )
                expected_by_label = {
                    "compile attach journal segment": (
                        "3 genesis/seal records + 3 records per attach hook + "
                        "at most one compiled-cut record per generated cut",
                        3 + 3 * attach_hooks + generated_cuts,
                    ),
                    "cut ledger segment": (
                        "2 genesis/seal records + at most one generated and one "
                        "terminal disposition record per generated cut",
                        2 + 2 * generated_cuts,
                    ),
                    "runtime cut segment": (
                        "certified_exact AB16 routes cut events through the cut "
                        "ledger; runtime-cut publication is forbidden",
                        0,
                    ),
                }
                expected = expected_by_label.get(logical_label)
                if (
                    attach_hooks != 30
                    or generated_cuts != 128
                    or expected is None
                    or derivation["formula"] != expected[0]
                    or maximum_segments != expected[1]
                ):
                    raise BrokerProtocolError(
                        "PUBLICATION_CONTRACT_INVALID",
                        "arm append-channel multiplicity derivation drifted",
                    )
            key = (arm_slot, channel)
            if key in result:
                raise BrokerProtocolError(
                    "PUBLICATION_CONTRACT_INVALID",
                    "append-channel identity is duplicated",
                )
            result[key] = _AppendPublicationRule(
                artifact_class=artifact_class,
                channel=channel,
                label=logical_label,
                maximum_bytes=_positive_int(
                    raw["maximum_bytes"],
                    label=f"{channel}.maximum_bytes",
                ),
                maximum_segments=maximum_segments,
                parent_path=_contract_relative_path(
                    raw["parent_path"],
                    label=f"{channel}.parent_path",
                ),
            )

    def authorize(
        self,
        *,
        arm_slot: str | None,
        artifact_class: str,
        channel: str | None,
        label: str,
        maximum_bytes: int,
        relative_path: str,
        sequence: int | None,
    ) -> None:
        with self._lock:
            self._authorize_locked(
                arm_slot=arm_slot,
                artifact_class=artifact_class,
                channel=channel,
                label=label,
                maximum_bytes=maximum_bytes,
                relative_path=relative_path,
                sequence=sequence,
            )

    def formal_fixed_spec(self, label: str) -> dict[str, object]:
        with self._lock:
            rule = self._fixed.get((None, label))
            if (
                rule is None
                or rule.branch != "common"
                or rule.maximum_publications != 1
                or len(rule.paths) != 1
            ):
                raise BrokerProtocolError(
                    "PUBLICATION_POLICY_DRIFT",
                    f"formal fixed publication is absent: {label!r}",
                )
            return {
                "artifact_class": rule.artifact_class,
                "label": rule.label,
                "maximum_bytes": rule.maximum_bytes,
                "relative_path": next(iter(rule.paths)),
            }

    def authorize_batch(
        self,
        publications: Sequence[Mapping[str, object]],
    ) -> None:
        """Atomically reserve a fixed batch before its first retained byte.

        A shape failure rolls back only the in-memory pre-publication check.
        Once this method returns, every count remains consumed even if a later
        descriptor transfer or no-replace publication fails.
        """

        with self._lock:
            counts_before = dict(self._counts)
            segment_counts_before = dict(self._segment_counts)
            branches_before = dict(self._arm_terminal_branch)
            try:
                for index, publication in enumerate(publications):
                    item = dict(publication)
                    _exact_keys(
                        item,
                        {
                            "arm_slot",
                            "artifact_class",
                            "channel",
                            "label",
                            "maximum_bytes",
                            "relative_path",
                            "sequence",
                        },
                        label=f"publication batch[{index}]",
                    )
                    self._authorize_locked(
                        arm_slot=cast(str | None, item["arm_slot"]),
                        artifact_class=cast(str, item["artifact_class"]),
                        channel=cast(str | None, item["channel"]),
                        label=cast(str, item["label"]),
                        maximum_bytes=cast(int, item["maximum_bytes"]),
                        relative_path=cast(str, item["relative_path"]),
                        sequence=cast(int | None, item["sequence"]),
                    )
            except BaseException:
                self._counts = counts_before
                self._segment_counts = segment_counts_before
                self._arm_terminal_branch = branches_before
                raise

    def _authorize_locked(
        self,
        *,
        arm_slot: str | None,
        artifact_class: str,
        channel: str | None,
        label: str,
        maximum_bytes: int,
        relative_path: str,
        sequence: int | None,
    ) -> None:
        if channel is None and sequence is None:
            key = (arm_slot, label)
            rule = self._fixed.get(key)
            if (
                rule is None
                or artifact_class != rule.artifact_class
                or maximum_bytes != rule.maximum_bytes
                or relative_path not in rule.paths
                or self._counts[key] >= rule.maximum_publications
            ):
                raise BrokerProtocolError(
                    "PUBLICATION_POLICY_DRIFT",
                    "fixed publication label/path/class/cap/count drifted",
                )
            if arm_slot is not None and rule.branch != "common":
                selected = self._arm_terminal_branch.get(arm_slot)
                if selected is not None and selected != rule.branch:
                    raise BrokerProtocolError(
                        "PUBLICATION_BRANCH_CONFLICT",
                        "success/failure publication branches were mixed",
                    )
                self._arm_terminal_branch[arm_slot] = rule.branch
            self._counts[key] += 1
            return
        if type(channel) is not str or type(sequence) is not int:
            raise BrokerProtocolError(
                "PUBLICATION_POLICY_DRIFT",
                "append publication lacks channel/sequence identity",
            )
        key = (arm_slot, channel)
        rule = self._channels.get(key)
        expected_sequence = self._segment_counts.get(key)
        if (
            rule is None
            or label != rule.label
            or artifact_class != rule.artifact_class
            or maximum_bytes != rule.maximum_bytes
            or sequence != expected_sequence
            or sequence >= rule.maximum_segments
            or relative_path
            != (
                f"{rule.parent_path}/"
                f"segment-{sequence:08d}.bin"
            )
        ):
            raise BrokerProtocolError(
                "PUBLICATION_POLICY_DRIFT",
                "append label/path/class/cap/segment-count drifted",
            )
        self._segment_counts[key] = sequence + 1


def _nonnegative_int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BrokerProtocolError(
            "INVALID_INTEGER",
            f"{label} must be a nonnegative exact integer",
        )
    return value


def _fixed_directories(
    value: Sequence[Mapping[str, object]],
    *,
    label: str,
) -> tuple[FixedDirectory, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise BrokerProtocolError("FIXED_LAYOUT_INVALID", f"{label} is not a directory sequence")
    result: list[FixedDirectory] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, Mapping) or set(item) != {"mode_octal", "path"}:
            raise BrokerProtocolError(
                "FIXED_LAYOUT_INVALID",
                f"{label}[{index}] is not one closed directory record",
            )
        path = item["path"]
        mode_octal = item["mode_octal"]
        if (
            not isinstance(path, str)
            or not isinstance(mode_octal, str)
            or mode_octal not in {"0500", "0700"}
        ):
            raise BrokerProtocolError(
                "FIXED_LAYOUT_INVALID",
                f"{label}[{index}] path or mode is invalid",
            )
        try:
            parts = budget._relative_parts(path, allow_dot=False)  # noqa: SLF001
        except budget.BudgetContractError as exc:
            raise BrokerProtocolError(
                "FIXED_LAYOUT_INVALID",
                f"{label}[{index}] is unsafe",
            ) from exc
        canonical = str(PurePosixPath(*parts))
        if canonical in seen:
            raise BrokerProtocolError(
                "FIXED_LAYOUT_INVALID",
                f"{label} contains a duplicate directory",
            )
        seen.add(canonical)
        result.append(FixedDirectory(path=canonical, mode=int(mode_octal, 8)))
    if result != sorted(
        result,
        key=lambda item: (item.path.count("/"), item.path.encode("utf-8")),
    ):
        raise BrokerProtocolError(
            "FIXED_LAYOUT_INVALID",
            f"{label} must be parent-first canonical order",
        )
    read_only = {
        spec.path
        for spec in result
        if spec.mode == 0o500
    }
    for spec in result:
        ancestors = PurePosixPath(spec.path).parents
        if any(
            str(ancestor) in read_only
            for ancestor in ancestors
            if str(ancestor) != "."
        ):
            raise BrokerProtocolError(
                "FIXED_LAYOUT_INVALID",
                f"{label} places a child below a sealed read-only directory",
            )
    return tuple(result)


def _identity(descriptor: int) -> DescriptorIdentity:
    metadata = os.fstat(descriptor)
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode_octal": f"{stat.S_IMODE(metadata.st_mode):04o}",
        "size_bytes": metadata.st_size,
        "uid": metadata.st_uid,
    }


def _parent_identity(descriptor: int) -> ParentIdentity:
    metadata = os.fstat(descriptor)
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode_octal": f"{stat.S_IMODE(metadata.st_mode):04o}",
        "uid": metadata.st_uid,
    }


def validate_prepared_extent(value: object) -> PreparedExtentRecord:
    if type(value) is not dict or set(value) != {
        "schema_version",
        "artifact_class",
        "maximum_bytes",
        "parent_identity",
        "parent_path",
        "staging_identity",
        "staging_name",
        "target_name",
    }:
        raise BrokerProtocolError("INVALID_PREPARED_EXTENT", "prepared extent shape differs")
    if value["schema_version"] != PREPARED_EXTENT_SCHEMA:
        raise BrokerProtocolError("INVALID_PREPARED_EXTENT", "prepared extent schema differs")
    if value["artifact_class"] not in budget.ARTIFACT_CLASSES:
        raise BrokerProtocolError("INVALID_PREPARED_EXTENT", "prepared extent class differs")
    _positive_int(value["maximum_bytes"], label="maximum_bytes")
    parent_identity = value["parent_identity"]
    if type(parent_identity) is not dict or set(parent_identity) != {
        "device",
        "inode",
        "mode_octal",
        "uid",
    }:
        raise BrokerProtocolError("INVALID_PREPARED_EXTENT", "parent_identity shape differs")
    staging_identity = value["staging_identity"]
    if type(staging_identity) is not dict or set(staging_identity) != {
            "device",
            "inode",
            "mode_octal",
            "size_bytes",
            "uid",
    }:
        raise BrokerProtocolError("INVALID_PREPARED_EXTENT", "staging_identity shape differs")
    for label in ("parent_path", "staging_name", "target_name"):
        if not isinstance(value[label], str) or not value[label]:
            raise BrokerProtocolError("INVALID_PREPARED_EXTENT", f"{label} is invalid")
    if "/" in value["staging_name"] or "/" in value["target_name"]:
        raise BrokerProtocolError("INVALID_PREPARED_EXTENT", "prepared leaf contains a slash")
    return cast(PreparedExtentRecord, dict(value))


def _prove_prepared_lock_released(
    account: budget.FormalBudgetBroker,
    extent_value: object,
) -> dict[str, object]:
    """Prove the retained recovery once-lock is no longer held."""

    extent = validate_prepared_extent(extent_value)
    parent_parts = budget._relative_parts(  # noqa: SLF001
        str(extent["parent_path"]),
        allow_dot=True,
    )
    parent_fd = budget._open_directory_parts(  # noqa: SLF001
        account._root_fd,  # noqa: SLF001
        parent_parts,
    )
    descriptor = -1
    try:
        if _parent_identity(parent_fd) != extent["parent_identity"]:
            raise BrokerProtocolError(
                "RECOVERY_LOCK_PARENT_DRIFT",
                "recovery once-lock parent differs after actor exit",
            )
        descriptor = os.open(
            str(extent["staging_name"]),
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        current = _identity(descriptor)
        expected = extent["staging_identity"]
        if (
            current["device"] != expected["device"]
            or current["inode"] != expected["inode"]
            or current["uid"] != expected["uid"]
        ):
            raise BrokerProtocolError(
                "RECOVERY_LOCK_IDENTITY_DRIFT",
                "recovery once-lock identity differs after actor exit",
            )
        try:
            fcntl.flock(
                descriptor,
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError as exc:
            raise BrokerProtocolError(
                "RECOVERY_LOCK_STILL_HELD",
                "recovery once-lock remains held after actor exit",
            ) from exc
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return {
            "identity": current,
            "state": "RECOVERY_TAKEOVER_LOCK_RELEASED",
        }
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def publish_preallocated_extent(
    extent_value: object,
    *,
    parent_fd: int,
    staging_fd: int,
    raw: bytes,
) -> dict[str, object]:
    """Fill an existing allocated inode and atomically publish it once."""

    extent = validate_prepared_extent(extent_value)
    if not isinstance(raw, bytes) or len(raw) > int(extent["maximum_bytes"]):
        raise BrokerProtocolError("EXTENT_OVERFLOW", "payload exceeds prepared extent")
    if _parent_identity(parent_fd) != extent["parent_identity"]:
        raise BrokerProtocolError("PARENT_IDENTITY_DRIFT", "prepared parent FD identity drifted")
    if _identity(staging_fd) != extent["staging_identity"]:
        raise BrokerProtocolError("STAGING_IDENTITY_DRIFT", "prepared staging FD identity drifted")
    budget._write_all_at(staging_fd, raw)  # noqa: SLF001
    os.fsync(staging_fd)
    os.ftruncate(staging_fd, len(raw))
    metadata = os.fstat(staging_fd)
    digest = budget._sha256_descriptor(staging_fd, size_bytes=len(raw))  # noqa: SLF001
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != len(raw):
        raise BrokerProtocolError("STAGING_IDENTITY_DRIFT", "prepared staging changed while writing")
    os.fchmod(staging_fd, 0o444)
    os.fsync(staging_fd)
    budget._rename_noreplace(  # noqa: SLF001
        parent_fd,
        str(extent["staging_name"]),
        str(extent["target_name"]),
    )
    os.fsync(parent_fd)
    replay = budget.FormalBudgetBroker._replay_published_at(  # noqa: SLF001
        parent_fd,
        str(extent["target_name"]),
        expected_size=len(raw),
        expected_sha256=digest,
    )
    return {
        "artifact_class": extent["artifact_class"],
        "maximum_bytes": extent["maximum_bytes"],
        "path": str(
            PurePosixPath(
                cast(str, extent["parent_path"]),
                cast(str, extent["target_name"]),
            )
        ),
        "sha256": replay["sha256"],
        "size_bytes": replay["size_bytes"],
    }


def consume_once_extent(
    extent_value: object,
    *,
    descriptor: int,
    record: Mapping[str, object],
) -> dict[str, object]:
    """Durably mark one lock extent consumed; an uncertain call is never retryable."""

    extent = validate_prepared_extent(extent_value)
    current = _identity(descriptor)
    expected = extent["staging_identity"]
    if (
        current["device"] != expected["device"]
        or current["inode"] != expected["inode"]
        or current["uid"] != expected["uid"]
    ):
        raise BrokerProtocolError("LOCK_IDENTITY_DRIFT", "once-lock staging identity drifted")
    maximum = int(extent["maximum_bytes"])
    if current["size_bytes"] != maximum or current["mode_octal"] != "0600":
        raise BrokerProtocolError("ONCE_LOCK_CONSUMED", "once-lock extent is already consumed")
    if os.pread(descriptor, maximum, 0) != b"\0" * maximum:
        raise BrokerProtocolError("ONCE_LOCK_CONSUMED", "once-lock extent is already consumed")
    raw = canonical_json_bytes(dict(record))
    if len(raw) > maximum:
        raise BrokerProtocolError("EXTENT_OVERFLOW", "once-lock record exceeds its extent")
    budget._write_all_at(descriptor, raw)  # noqa: SLF001
    os.fsync(descriptor)
    os.ftruncate(descriptor, len(raw))
    digest = budget._sha256_descriptor(descriptor, size_bytes=len(raw))  # noqa: SLF001
    os.fchmod(descriptor, 0o444)
    os.fsync(descriptor)
    return {
        "path": f"{extent['parent_path']}/{extent['staging_name']}",
        "sha256": digest,
        "size_bytes": len(raw),
    }


def _prepare_extent(
    account: budget.FormalBudgetBroker,
    *,
    parent_path: str,
    target_name: str,
    maximum_bytes: int,
    artifact_class: str,
) -> tuple[PreparedExtent, int, int]:
    """Reserve and preallocate one hidden inode without publishing its target."""

    maximum = _positive_int(maximum_bytes, label="maximum_bytes")
    target = PurePosixPath(target_name)
    if target.is_absolute() or len(target.parts) != 1 or target.parts[0] in {".", ".."}:
        raise BrokerProtocolError("INVALID_TARGET", "prepared target must be one relative leaf")
    account.register_directory(parent_path)
    parent_parts = budget._relative_parts(  # noqa: SLF001
        parent_path,
        allow_dot=True,
    )
    parent_fd = budget._open_directory_parts(  # noqa: SLF001
        account._root_fd,  # noqa: SLF001
        parent_parts,
    )
    staging_fd: int | None = None
    try:
        # This is the runtime half of the same package cohort as the primitive.
        # The private debit is kept under the primitive's own serialization lock.
        with account._lock:  # noqa: SLF001
            account._reserve(  # noqa: SLF001
                artifact_class=artifact_class,
                maximum_bytes=maximum,
                arm_slot=None,
            )
        staging_name = f"{_STAGING_PREFIX}{secrets.token_hex(16)}"
        staging_fd = os.open(staging_name, _WRITE_FLAGS, 0o600, dir_fd=parent_fd)
        staging_path = str(PurePosixPath(parent_path, staging_name))
        target_path = str(PurePosixPath(parent_path, target.parts[0]))
        with account._lock:  # noqa: SLF001
            account._register_staging_inode(  # noqa: SLF001
                staging_path=staging_path,
                target_path=target_path,
                descriptor=staging_fd,
                maximum_bytes=maximum,
                artifact_class=artifact_class,
                arm_slot=None,
                purpose=f"prepared-{target.parts[0]}",
            )
        os.posix_fallocate(staging_fd, 0, maximum)
        os.fsync(staging_fd)
        os.fsync(parent_fd)
        extent = PreparedExtent(
            artifact_class=artifact_class,
            maximum_bytes=maximum,
            parent_identity=_parent_identity(parent_fd),
            parent_path=parent_path,
            staging_name=staging_name,
            target_name=target.parts[0],
            staging_identity=_identity(staging_fd),
        )
        result = (extent, parent_fd, staging_fd)
        parent_fd = -1
        staging_fd = None
        return result
    finally:
        if staging_fd is not None:
            try:
                os.fchmod(staging_fd, 0o444)
                os.fsync(staging_fd)
            except OSError:
                pass
            os.close(staging_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def _prepare_once_lock(
    account: budget.FormalBudgetBroker,
    *,
    target_name: str,
) -> tuple[PreparedExtent, int]:
    extent, parent_fd, descriptor = _prepare_extent(
        account,
        parent_path="control",
        target_name=target_name,
        maximum_bytes=4096,
        artifact_class="metadata",
    )
    os.close(parent_fd)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BaseException:
        os.close(descriptor)
        raise
    return extent, descriptor


def _bootstrap_sha256(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_IDENTITY_DRIFT",
            f"{label} is not one SHA-256",
        )
    return value


def _bootstrap_transfer_nonce(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 32
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_IDENTITY_DRIFT",
            f"{label} is not one transfer nonce",
        )
    return value


def _bootstrap_base_identity(
    value: object,
    *,
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "device",
        "inode",
        "mode_octal",
        "uid",
    }:
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_IDENTITY_DRIFT",
            f"{label} identity shape differs",
        )
    identity = dict(value)
    if (
        any(
            isinstance(identity[key], bool)
            or not isinstance(identity[key], int)
            or cast(int, identity[key]) < 0
            for key in ("device", "inode", "uid")
        )
        or identity["mode_octal"] not in {"0600", "0700"}
    ):
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_IDENTITY_DRIFT",
            f"{label} identity values differ",
        )
    return identity


def _bootstrap_observed_identity(descriptor: int) -> dict[str, object]:
    metadata = os.fstat(descriptor)
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode_octal": f"{stat.S_IMODE(metadata.st_mode):04o}",
        "uid": metadata.st_uid,
    }


def _require_bootstrap_owner_binding(
    record: Mapping[str, object],
    *,
    expected_owner_nonce: str,
    label: str,
) -> None:
    source_owner = record["from_owner_nonce"]
    if (
        not isinstance(source_owner, str)
        or not source_owner
        or record["from_owner_nonce_sha256"]
        != hashlib.sha256(source_owner.encode("ascii")).hexdigest()
        or record["to_owner_nonce"] != expected_owner_nonce
        or record["to_owner_nonce_sha256"]
        != hashlib.sha256(expected_owner_nonce.encode("ascii")).hexdigest()
    ):
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_OWNER_DRIFT",
            f"{label} owner binding differs",
        )
    _bootstrap_transfer_nonce(
        record["transfer_nonce"],
        label=f"{label}.transfer_nonce",
    )


def _bootstrap_directory_record(
    value: object,
    *,
    expected_owner_nonce: str,
    expected_directory_path: str,
    expected_purpose: str,
    descriptor: int,
    label: str,
) -> dict[str, object]:
    expected = {
        "directory_path",
        "from_owner_nonce",
        "from_owner_nonce_sha256",
        "identity",
        "path",
        "purpose",
        "schema_version",
        "to_owner_nonce",
        "to_owner_nonce_sha256",
        "transfer_nonce",
    }
    if type(value) is not dict or set(value) != expected:
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_SHAPE_MISMATCH",
            f"{label} shape differs",
        )
    record = dict(value)
    _require_bootstrap_owner_binding(
        record,
        expected_owner_nonce=expected_owner_nonce,
        label=label,
    )
    identity = _bootstrap_base_identity(
        record["identity"],
        label=label,
    )
    path_value = record["path"]
    if (
        record["schema_version"]
        != BOOTSTRAP_RETAINED_DIRECTORY_HANDOFF_SCHEMA
        or record["directory_path"] != expected_directory_path
        or record["purpose"] != expected_purpose
        or not isinstance(path_value, str)
        or path_value != os.path.abspath(path_value)
        or identity["mode_octal"] != "0700"
        or identity != _bootstrap_observed_identity(descriptor)
    ):
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_IDENTITY_DRIFT",
            f"{label} identity differs",
        )
    joined_fd = -1
    try:
        joined_fd = budget._open_absolute_directory_no_symlinks(  # noqa: SLF001
            Path(path_value)
        )
        if _bootstrap_observed_identity(joined_fd) != identity:
            raise BrokerProtocolError(
                "BOOTSTRAP_HANDOFF_PATH_DRIFT",
                f"{label} absolute path differs from its retained FD",
            )
    finally:
        if joined_fd >= 0:
            os.close(joined_fd)
    return record


def _bootstrap_staging_record(
    value: object,
    *,
    expected_owner_nonce: str,
    expected_purpose: str,
    expected_shared_parent: bool,
    parent_fd: int,
    staging_fd: int,
) -> dict[str, object]:
    expected = {
        "artifact_class",
        "from_owner_nonce",
        "from_owner_nonce_sha256",
        "maximum_bytes",
        "parent_identity",
        "parent_path",
        "purpose",
        "schema_version",
        "shared_parent_fd",
        "staging_identity",
        "staging_name",
        "to_owner_nonce",
        "to_owner_nonce_sha256",
        "transfer_nonce",
    }
    if type(value) is not dict or set(value) != expected:
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_SHAPE_MISMATCH",
            f"bootstrap staging {expected_purpose!r} shape differs",
        )
    record = dict(value)
    _require_bootstrap_owner_binding(
        record,
        expected_owner_nonce=expected_owner_nonce,
        label=f"bootstrap staging {expected_purpose!r}",
    )
    parent_identity = _bootstrap_base_identity(
        record["parent_identity"],
        label=f"{expected_purpose}.parent",
    )
    staging_identity = _bootstrap_base_identity(
        record["staging_identity"],
        label=f"{expected_purpose}.staging",
    )
    maximum = record["maximum_bytes"]
    staging_name = record["staging_name"]
    parent_path = record["parent_path"]
    staging_metadata = os.fstat(staging_fd)
    if (
        record["schema_version"] != BOOTSTRAP_STAGING_HANDOFF_SCHEMA
        or record["purpose"] != expected_purpose
        or record["shared_parent_fd"] is not expected_shared_parent
        or record["artifact_class"] not in budget.ARTIFACT_CLASSES
        or isinstance(maximum, bool)
        or not isinstance(maximum, int)
        or maximum <= 0
        or not isinstance(staging_name, str)
        or len(PurePosixPath(staging_name).parts) != 1
        or staging_name in {"", ".", ".."}
        or not staging_name.startswith(".ab16-budget-staging-")
        or not isinstance(parent_path, str)
        or parent_path != os.path.abspath(parent_path)
        or parent_identity["mode_octal"] != "0700"
        or staging_identity["mode_octal"] != "0600"
        or parent_identity != _bootstrap_observed_identity(parent_fd)
        or staging_identity != _bootstrap_observed_identity(staging_fd)
        or not stat.S_ISDIR(os.fstat(parent_fd).st_mode)
        or not stat.S_ISREG(staging_metadata.st_mode)
        or staging_metadata.st_nlink != 1
        or staging_metadata.st_size != maximum
    ):
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_IDENTITY_DRIFT",
            f"bootstrap staging {expected_purpose!r} identity differs",
        )
    try:
        named = os.stat(
            staging_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_PATH_DRIFT",
            f"bootstrap staging {expected_purpose!r} is not named by its parent",
        ) from exc
    if (
        named.st_dev != staging_metadata.st_dev
        or named.st_ino != staging_metadata.st_ino
        or stat.S_IFMT(named.st_mode) != stat.S_IFREG
    ):
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_PATH_DRIFT",
            f"bootstrap staging {expected_purpose!r} named identity differs",
        )
    joined_fd = -1
    try:
        joined_fd = budget._open_absolute_directory_no_symlinks(  # noqa: SLF001
            Path(parent_path)
        )
        if _bootstrap_observed_identity(joined_fd) != parent_identity:
            raise BrokerProtocolError(
                "BOOTSTRAP_HANDOFF_PATH_DRIFT",
                f"bootstrap staging {expected_purpose!r} parent path differs",
            )
    finally:
        if joined_fd >= 0:
            os.close(joined_fd)
    return record


def _native_directory_handoff(
    capability: budget.RetainedDirectoryCapability,
    source: Mapping[str, object],
    *,
    expected_owner_nonce: str,
) -> dict[str, object]:
    current = capability.record()
    source_record = {
        **current,
        "owner_nonce": source["from_owner_nonce"],
    }
    return {
        "schema_version": budget.BUDGET_OWNERSHIP_HANDOFF_SCHEMA,
        "account_kind": "retained-directory",
        "directory_path": current["directory_path"],
        "from_owner_nonce": source["from_owner_nonce"],
        "root_path": current["root_path"],
        "source_record_sha256": hashlib.sha256(
            canonical_json_bytes(source_record)
        ).hexdigest(),
        "to_owner_nonce": expected_owner_nonce,
        "transfer_nonce": source["transfer_nonce"],
    }


def adopt_bootstrap_structural_handoff(
    structural_handoff: Mapping[str, object],
    inherited_descriptors: Sequence[int],
    *,
    expected_owner_nonce: str,
) -> Mapping[str, object]:
    """Adopt the sole bootstrap-native 19-FD cohort without reopening paths."""

    owner_nonce = _nonce(expected_owner_nonce)
    top_fields = {
        "account",
        "control_parent",
        "fd_count",
        "fd_roles",
        "outside_final_release_parent",
        "reservations",
        "schema_version",
        "to_owner_nonce_sha256",
    }
    if type(structural_handoff) is not dict or set(structural_handoff) != top_fields:
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_SHAPE_MISMATCH",
            "bootstrap structural handoff shape differs",
        )
    top = dict(structural_handoff)
    formal_purposes = tuple(sorted(FIXED_PURPOSE_SPECS))
    outside_purposes = tuple(sorted(OUTSIDE_FINAL_RELEASE_SPECS))
    expected_roles = ["formal-account:root"]
    for purpose in formal_purposes:
        expected_roles.extend(
            (
                f"reservation:{purpose}:parent",
                f"reservation:{purpose}:staging",
            )
        )
    expected_roles.append("outside-final-release:parent")
    expected_roles.extend(
        f"reservation:{purpose}:staging"
        for purpose in outside_purposes
    )
    expected_roles.append("formal-control:parent")
    raw_fds = tuple(inherited_descriptors)
    if (
        top["schema_version"] != BOOTSTRAP_STRUCTURAL_HANDOFF_SCHEMA
        or top["fd_count"] != 19
        or top["fd_roles"] != expected_roles
        or top["to_owner_nonce_sha256"]
        != hashlib.sha256(owner_nonce.encode("ascii")).hexdigest()
        or len(raw_fds) != 19
        or len(set(raw_fds)) != 19
        or any(
            isinstance(descriptor, bool)
            or not isinstance(descriptor, int)
            or descriptor < 0
            for descriptor in raw_fds
        )
    ):
        raise BrokerProtocolError(
            "BOOTSTRAP_HANDOFF_FD_COHORT_DRIFT",
            "bootstrap structural handoff FD cohort differs",
        )
    duplicates: list[int] = []
    account: budget.FormalBudgetBroker | None = None
    reservations: dict[str, budget.RetainedStagingReservation] = {}
    control: budget.RetainedDirectoryCapability | None = None
    final_release: FinalReleaseParentCapability | None = None
    try:
        for descriptor in raw_fds:
            duplicates.append(os.dup(descriptor))
        cursor = 0
        root_fd = duplicates[cursor]
        cursor += 1
        formal_fd_pairs: dict[str, tuple[int, int]] = {}
        for purpose in formal_purposes:
            formal_fd_pairs[purpose] = (
                duplicates[cursor],
                duplicates[cursor + 1],
            )
            cursor += 2
        outside_parent_fd = duplicates[cursor]
        cursor += 1
        outside_staging_fds: dict[str, int] = {}
        for purpose in outside_purposes:
            outside_staging_fds[purpose] = duplicates[cursor]
            cursor += 1
        control_fd = duplicates[cursor]
        cursor += 1
        assert cursor == 19

        account_fields = {
            "arm_allocations",
            "arm_debits",
            "category_debits",
            "category_limits",
            "from_owner_nonce",
            "from_owner_nonce_sha256",
            "root_identity",
            "root_path",
            "schema_version",
            "to_owner_nonce",
            "to_owner_nonce_sha256",
            "transfer_nonce",
        }
        raw_account = top["account"]
        if type(raw_account) is not dict or set(raw_account) != account_fields:
            raise BrokerProtocolError(
                "BOOTSTRAP_HANDOFF_SHAPE_MISMATCH",
                "bootstrap formal account handoff shape differs",
            )
        account_record = dict(raw_account)
        _require_bootstrap_owner_binding(
            account_record,
            expected_owner_nonce=owner_nonce,
            label="bootstrap formal account",
        )
        root_identity = _bootstrap_base_identity(
            account_record["root_identity"],
            label="bootstrap formal root",
        )
        root_path_value = account_record["root_path"]
        if (
            account_record["schema_version"]
            != BOOTSTRAP_BUDGET_ACCOUNT_HANDOFF_SCHEMA
            or not isinstance(root_path_value, str)
            or root_path_value != os.path.abspath(root_path_value)
            or root_identity["mode_octal"] != "0700"
            or root_identity != _bootstrap_observed_identity(root_fd)
            or not stat.S_ISDIR(os.fstat(root_fd).st_mode)
        ):
            raise BrokerProtocolError(
                "BOOTSTRAP_HANDOFF_IDENTITY_DRIFT",
                "bootstrap formal account identity differs",
            )
        joined_root_fd = -1
        try:
            joined_root_fd = budget._open_absolute_directory_no_symlinks(  # noqa: SLF001
                Path(root_path_value)
            )
            if _bootstrap_observed_identity(joined_root_fd) != root_identity:
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_PATH_DRIFT",
                    "bootstrap formal root path differs from retained FD",
                )
        finally:
            if joined_root_fd >= 0:
                os.close(joined_root_fd)

        limits = budget._validated_categories(  # noqa: SLF001
            account_record["category_limits"],
            label="bootstrap category_limits",
        )
        debits = budget._validated_categories(  # noqa: SLF001
            account_record["category_debits"],
            label="bootstrap category_debits",
            allow_zero_total=True,
        )
        raw_allocations = account_record["arm_allocations"]
        raw_arm_debits = account_record["arm_debits"]
        if (
            type(raw_allocations) is not dict
            or type(raw_arm_debits) is not dict
            or set(raw_allocations) != set(raw_arm_debits)
        ):
            raise BrokerProtocolError(
                "BOOTSTRAP_HANDOFF_ARITHMETIC_DRIFT",
                "bootstrap arm allocation/debit sets differ",
            )
        arm_accounts: dict[str, budget._ArmAccount] = {}  # noqa: SLF001
        allocation_totals = {category: 0 for category in limits}
        arm_debit_totals = {category: 0 for category in limits}
        for raw_slot in sorted(raw_allocations):
            slot = budget._safe_component(raw_slot, label="arm_slot")  # noqa: SLF001
            allocation = budget._validated_categories(  # noqa: SLF001
                raw_allocations[raw_slot],
                label=f"bootstrap arm {slot} allocation",
            )
            arm_debit = budget._validated_categories(  # noqa: SLF001
                raw_arm_debits[raw_slot],
                label=f"bootstrap arm {slot} debits",
                allow_zero_total=True,
            )
            if set(allocation) != set(arm_debit) or any(
                arm_debit[category] > allocation[category]
                for category in allocation
            ):
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_ARITHMETIC_DRIFT",
                    f"bootstrap arm {slot!r} arithmetic differs",
                )
            for category in allocation:
                allocation_totals[category] += allocation[category]
                arm_debit_totals[category] += arm_debit[category]
            arm_accounts[slot] = budget._ArmAccount(  # noqa: SLF001
                category_limits=dict(allocation),
                category_remaining={
                    category: allocation[category] - arm_debit[category]
                    for category in allocation
                },
                total_bytes=sum(allocation.values()),
            )
        root_remaining: dict[str, int] = {}
        for category, limit in limits.items():
            direct_debit = debits[category] - arm_debit_totals[category]
            remaining = limit - allocation_totals[category] - direct_debit
            if direct_debit < 0 or remaining < 0:
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_ARITHMETIC_DRIFT",
                    f"bootstrap {category!r} hierarchy overcommits the formal root",
                )
            root_remaining[category] = remaining

        raw_reservations = top["reservations"]
        if (
            type(raw_reservations) is not dict
            or set(raw_reservations)
            != set(formal_purposes) | set(outside_purposes)
        ):
            raise BrokerProtocolError(
                "BOOTSTRAP_HANDOFF_SHAPE_MISMATCH",
                "bootstrap reservation set differs",
            )
        checked_formal_records: dict[str, dict[str, object]] = {}
        root_path = Path(root_path_value)
        for purpose in formal_purposes:
            parent_fd, staging_fd = formal_fd_pairs[purpose]
            checked = _bootstrap_staging_record(
                raw_reservations[purpose],
                expected_owner_nonce=owner_nonce,
                expected_purpose=purpose,
                expected_shared_parent=False,
                parent_fd=parent_fd,
                staging_fd=staging_fd,
            )
            spec = FIXED_PURPOSE_SPECS[purpose]
            try:
                parent_relative = Path(cast(str, checked["parent_path"])).relative_to(
                    root_path
                )
            except ValueError as exc:
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_PATH_DRIFT",
                    f"formal reservation {purpose!r} parent escaped the formal root",
                ) from exc
            relative = "." if not parent_relative.parts else parent_relative.as_posix()
            if (
                relative != spec.parent_path
                or checked["artifact_class"] != spec.artifact_class
                or (
                    spec.exact_maximum_bytes is not None
                    and checked["maximum_bytes"] != spec.exact_maximum_bytes
                )
            ):
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_IDENTITY_DRIFT",
                    f"formal reservation {purpose!r} differs from its fixed spec",
                )
            try:
                os.stat(
                    spec.target_name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_TARGET_COLLISION",
                    f"formal reservation target {purpose!r} already exists",
                )
            checked_formal_records[purpose] = checked

        outside_record = _bootstrap_directory_record(
            top["outside_final_release_parent"],
            expected_owner_nonce=owner_nonce,
            expected_directory_path=OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE,
            expected_purpose="outside-formal-root-final-release-parent",
            descriptor=outside_parent_fd,
            label="outside final-release parent",
        )
        outside_records: dict[str, dict[str, object]] = {}
        for purpose in outside_purposes:
            checked = _bootstrap_staging_record(
                raw_reservations[purpose],
                expected_owner_nonce=owner_nonce,
                expected_purpose=purpose,
                expected_shared_parent=True,
                parent_fd=outside_parent_fd,
                staging_fd=outside_staging_fds[purpose],
            )
            if (
                checked["parent_path"] != outside_record["path"]
                or checked["artifact_class"] != "closeout"
                or checked["maximum_bytes"]
                != OUTSIDE_FINAL_RELEASE_MAXIMUM_BYTES
            ):
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_IDENTITY_DRIFT",
                    f"outside final-release reservation {purpose!r} differs",
                )
            try:
                os.stat(
                    OUTSIDE_FINAL_RELEASE_SPECS[purpose],
                    dir_fd=outside_parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                pass
            else:
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_TARGET_COLLISION",
                    f"outside final-release target {purpose!r} already exists",
                )
            outside_records[purpose] = checked

        control_record = _bootstrap_directory_record(
            top["control_parent"],
            expected_owner_nonce=owner_nonce,
            expected_directory_path="formal-ab16/control",
            expected_purpose="formal-control-parent",
            descriptor=control_fd,
            label="formal control parent",
        )

        account = budget.FormalBudgetBroker(
            root=root_path,
            root_fd=root_fd,
            root_identity=budget._path_identity(os.fstat(root_fd)),  # noqa: SLF001
            category_limits=limits,
            owner_nonce=owner_nonce,
        )
        duplicates[0] = -1
        account._root_remaining = root_remaining  # noqa: SLF001
        account._arms = arm_accounts  # noqa: SLF001
        account._arm_states = {slot: "ACTIVE" for slot in arm_accounts}  # noqa: SLF001
        registered = {()}
        registered_modes = {(): 0o700}
        for purpose in formal_purposes:
            spec = FIXED_PURPOSE_SPECS[purpose]
            parts = budget._relative_parts(  # noqa: SLF001
                spec.parent_path,
                allow_dot=True,
            )
            for length in range(1, len(parts) + 1):
                current = parts[:length]
                registered.add(current)
                registered_modes[current] = 0o700
            parent_fd, staging_fd = formal_fd_pairs[purpose]
            checked = checked_formal_records[purpose]
            staging_path = str(
                PurePosixPath(
                    *parts,
                    cast(str, checked["staging_name"]),
                )
            )
            target_path = str(PurePosixPath(*parts, spec.target_name))
            account._register_staging_inode(  # noqa: SLF001
                staging_path=staging_path,
                target_path=target_path,
                descriptor=staging_fd,
                maximum_bytes=cast(int, checked["maximum_bytes"]),
                artifact_class=cast(str, checked["artifact_class"]),
                arm_slot=None,
                purpose=purpose,
            )
            reservation = budget.RetainedStagingReservation(
                root=root_path,
                parent_fd=parent_fd,
                descriptor=staging_fd,
                staging_path=staging_path,
                maximum_bytes=cast(int, checked["maximum_bytes"]),
                artifact_class=cast(str, checked["artifact_class"]),
                arm_slot=None,
                purpose=purpose,
                owner_nonce=owner_nonce,
            )
            reservations[purpose] = reservation
            parent_index = raw_fds.index(raw_fds[1 + formal_purposes.index(purpose) * 2])
            duplicates[parent_index] = -1
            duplicates[parent_index + 1] = -1
        account._registered_directories = registered  # noqa: SLF001
        account._registered_directory_modes = registered_modes  # noqa: SLF001

        control = budget.RetainedDirectoryCapability(
            root=Path(cast(str, control_record["path"])).parents[1],
            descriptor=control_fd,
            relative_path=cast(str, control_record["directory_path"]),
            purpose=cast(str, control_record["purpose"]),
            owner_nonce=owner_nonce,
            identity=budget._path_identity(os.fstat(control_fd)),  # noqa: SLF001
        )
        duplicates[-1] = -1
        outside_extent_records = {
            purpose: PreparedExtent(
                artifact_class="closeout",
                maximum_bytes=OUTSIDE_FINAL_RELEASE_MAXIMUM_BYTES,
                parent_identity=_parent_identity(outside_parent_fd),
                parent_path=OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE,
                staging_name=cast(str, outside_records[purpose]["staging_name"]),
                target_name=OUTSIDE_FINAL_RELEASE_SPECS[purpose],
                staging_identity=_identity(outside_staging_fds[purpose]),
            ).as_record()
            for purpose in outside_purposes
        }
        final_release = FinalReleaseParentCapability(
            descriptor=outside_parent_fd,
            directory_path=cast(str, outside_record["directory_path"]),
            path=Path(cast(str, outside_record["path"])),
            purpose=cast(str, outside_record["purpose"]),
            owner_nonce=owner_nonce,
            identity=_parent_identity(outside_parent_fd),
            extent_descriptors=outside_staging_fds,
            extent_records=outside_extent_records,
        )
        outside_parent_index = 1 + 2 * len(formal_purposes)
        duplicates[outside_parent_index] = -1
        for offset in range(len(outside_purposes)):
            duplicates[outside_parent_index + 1 + offset] = -1

        account_handoff = {
            "schema_version": budget.BUDGET_OWNERSHIP_HANDOFF_SCHEMA,
            "account_kind": "formal-root",
            "account_record_sha256": hashlib.sha256(
                canonical_json_bytes(account.contract_record())
            ).hexdigest(),
            "from_owner_nonce": account_record["from_owner_nonce"],
            "root_path": str(root_path),
            "root_signature": list(budget._signature(os.fstat(account._root_fd))),  # noqa: SLF001
            "to_owner_nonce": owner_nonce,
            "transfer_nonce": account_record["transfer_nonce"],
        }
        reservation_handoffs = {
            purpose: {
                "schema_version": budget.BUDGET_OWNERSHIP_HANDOFF_SCHEMA,
                "account_kind": "retained-staging",
                "from_owner_nonce": checked_formal_records[purpose][
                    "from_owner_nonce"
                ],
                "root_path": str(root_path),
                "source_record_sha256": hashlib.sha256(
                    canonical_json_bytes(
                        {
                            **reservations[purpose].record(),
                            "owner_nonce": checked_formal_records[purpose][
                                "from_owner_nonce"
                            ],
                        }
                    )
                ).hexdigest(),
                "staging_path": reservations[purpose].record()["staging_path"],
                "to_owner_nonce": owner_nonce,
                "transfer_nonce": checked_formal_records[purpose][
                    "transfer_nonce"
                ],
            }
            for purpose in formal_purposes
        }
        control_handoff = _native_directory_handoff(
            control,
            control_record,
            expected_owner_nonce=owner_nonce,
        )
        final_release_handoff = {
            "schema_version": FINAL_RELEASE_PARENT_HANDOFF_SCHEMA,
            "directory_handoff": outside_record,
            "reservation_handoffs": {
                purpose: outside_records[purpose]
                for purpose in outside_purposes
            },
            "to_owner_nonce": owner_nonce,
        }
        return {
            "account": account,
            "account_handoff": account_handoff,
            "reservations": reservations,
            "reservation_handoffs": reservation_handoffs,
            "control_parent": control,
            "control_parent_handoff": control_handoff,
            "final_release_parent": final_release,
            "final_release_parent_handoff": final_release_handoff,
        }
    except BaseException:
        for reservation in reservations.values():
            try:
                reservation.close()
            except BaseException:
                pass
        if control is not None:
            try:
                control.close()
            except BaseException:
                pass
        if final_release is not None:
            try:
                final_release.close()
            except BaseException:
                pass
        if account is not None:
            try:
                account.close()
            except BaseException:
                pass
        for descriptor in duplicates:
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except BaseException:
                    pass
        raise


def validate_transferred_account(
    account: budget.FormalBudgetBroker,
    ownership_handoff: object,
    *,
    expected_owner_nonce: str,
) -> dict[str, object]:
    """Join an already-transferred account without creating a parallel root."""

    owner_nonce = budget._safe_component(  # noqa: SLF001
        expected_owner_nonce,
        label="expected_owner_nonce",
    )
    expected_fields = {
        "account_kind",
        "account_record_sha256",
        "from_owner_nonce",
        "root_path",
        "root_signature",
        "schema_version",
        "to_owner_nonce",
        "transfer_nonce",
    }
    if type(ownership_handoff) is not dict or set(ownership_handoff) != expected_fields:
        raise BrokerProtocolError(
            "HANDOFF_SHAPE_MISMATCH",
            "formal-root ownership handoff shape differs",
        )
    record = dict(ownership_handoff)
    try:
        account._require_open()  # noqa: SLF001
        account._require_root_identity()  # noqa: SLF001
        metadata = os.fstat(account._root_fd)  # noqa: SLF001
        contract = account.contract_record()
    except budget.BudgetContractError as exc:
        raise BrokerProtocolError(
            "HANDOFF_ACCOUNT_INVALID",
            "transferred formal-root account is not live",
        ) from exc
    digest = hashlib.sha256(canonical_json_bytes(contract)).hexdigest()
    signature = list(budget._signature(metadata))  # noqa: SLF001
    if (
        record["schema_version"] != budget.BUDGET_OWNERSHIP_HANDOFF_SCHEMA
        or record["account_kind"] != "formal-root"
        or record["account_record_sha256"] != digest
        or record["root_path"] != str(account.root)
        or record["root_signature"] != signature
        or record["to_owner_nonce"] != owner_nonce
        or account._owner_nonce != owner_nonce  # noqa: SLF001
        or not isinstance(record["from_owner_nonce"], str)
        or not isinstance(record["transfer_nonce"], str)
        or len(record["transfer_nonce"]) != 32
        or any(
            character not in "0123456789abcdef"
            for character in record["transfer_nonce"]
        )
    ):
        raise BrokerProtocolError(
            "HANDOFF_IDENTITY_DRIFT",
            "formal-root ownership handoff differs from the retained account",
        )
    return record


def validate_transferred_reservations(
    account: budget.FormalBudgetBroker,
    reservations: Mapping[str, budget.RetainedStagingReservation],
    ownership_handoffs: Mapping[str, Mapping[str, object]],
    *,
    expected_owner_nonce: str,
) -> dict[str, dict[str, object]]:
    """Join the closed package-bound reservation cohort to the artifact root."""

    expected_purposes = set(FIXED_PURPOSE_SPECS)
    if set(reservations) != expected_purposes or set(ownership_handoffs) != expected_purposes:
        raise BrokerProtocolError(
            "FIXED_RESERVATION_SET_DRIFT",
            "fixed-purpose reservation or handoff set differs",
        )
    owner_nonce = budget._safe_component(  # noqa: SLF001
        expected_owner_nonce,
        label="expected_owner_nonce",
    )
    checked: dict[str, dict[str, object]] = {}
    handoff_fields = {
        "account_kind",
        "from_owner_nonce",
        "root_path",
        "schema_version",
        "source_record_sha256",
        "staging_path",
        "to_owner_nonce",
        "transfer_nonce",
    }
    record_fields = {
        "arm_slot",
        "artifact_class",
        "maximum_bytes",
        "owner_nonce",
        "purpose",
        "root_path",
        "schema_version",
        "staging_path",
        "staging_signature",
    }
    for purpose in sorted(expected_purposes):
        reservation = reservations[purpose]
        handoff = ownership_handoffs[purpose]
        try:
            record = reservation.record()
        except budget.BudgetContractError as exc:
            raise BrokerProtocolError(
                "FIXED_RESERVATION_INVALID",
                f"fixed reservation {purpose!r} is not live",
            ) from exc
        if set(record) != record_fields or set(handoff) != handoff_fields:
            raise BrokerProtocolError(
                "FIXED_RESERVATION_SHAPE_DRIFT",
                f"fixed reservation {purpose!r} shape differs",
            )
        spec = FIXED_PURPOSE_SPECS[purpose]
        staging_path = PurePosixPath(cast(str, record["staging_path"]))
        parent_path = str(staging_path.parent)
        maximum = record["maximum_bytes"]
        if (
            record["schema_version"]
            != budget.BUDGET_RETAINED_STAGING_SCHEMA
            or record["purpose"] != purpose
            or record["artifact_class"] != spec.artifact_class
            or record["arm_slot"] is not None
            or record["root_path"] != str(account.root)
            or record["owner_nonce"] != owner_nonce
            or parent_path != spec.parent_path
            or isinstance(maximum, bool)
            or not isinstance(maximum, int)
            or maximum <= 0
            or (
                spec.exact_maximum_bytes is not None
                and maximum != spec.exact_maximum_bytes
            )
        ):
            raise BrokerProtocolError(
                "FIXED_RESERVATION_IDENTITY_DRIFT",
                f"fixed reservation {purpose!r} differs from its package spec",
            )
        source_record = {
            **record,
            "owner_nonce": handoff["from_owner_nonce"],
        }
        transfer_nonce = handoff["transfer_nonce"]
        if (
            handoff["schema_version"]
            != budget.BUDGET_OWNERSHIP_HANDOFF_SCHEMA
            or handoff["account_kind"] != "retained-staging"
            or handoff["root_path"] != str(account.root)
            or handoff["staging_path"] != record["staging_path"]
            or handoff["to_owner_nonce"] != owner_nonce
            or handoff["source_record_sha256"]
            != hashlib.sha256(canonical_json_bytes(source_record)).hexdigest()
            or not isinstance(handoff["from_owner_nonce"], str)
            or not isinstance(transfer_nonce, str)
            or len(transfer_nonce) != 32
            or any(
                character not in "0123456789abcdef"
                for character in transfer_nonce
            )
        ):
            raise BrokerProtocolError(
                "FIXED_RESERVATION_HANDOFF_DRIFT",
                f"fixed reservation {purpose!r} handoff differs",
            )
        parent_parts = budget._relative_parts(  # noqa: SLF001
            spec.parent_path,
            allow_dot=True,
        )
        account_parent_fd = budget._open_directory_parts(  # noqa: SLF001
            account._root_fd,  # noqa: SLF001
            parent_parts,
        )
        try:
            if (
                budget._signature(os.fstat(account_parent_fd))  # noqa: SLF001
                != budget._signature(  # noqa: SLF001
                    os.fstat(reservation._parent_fd)  # noqa: SLF001
                )
                or list(
                    budget._signature(  # noqa: SLF001
                        os.fstat(reservation._descriptor)  # noqa: SLF001
                    )
                )
                != record["staging_signature"]
            ):
                raise BrokerProtocolError(
                    "FIXED_RESERVATION_IDENTITY_DRIFT",
                    f"fixed reservation {purpose!r} descriptors differ",
                )
        finally:
            os.close(account_parent_fd)
        checked[purpose] = dict(record)
    return checked


def validate_transferred_control_parent(
    account: budget.FormalBudgetBroker,
    capability: budget.RetainedDirectoryCapability,
    ownership_handoff: Mapping[str, object],
    *,
    expected_owner_nonce: str,
    endpoint_path: Path,
) -> dict[str, object]:
    """Bind the out-of-artifact control directory to one broker endpoint."""

    owner_nonce = budget._safe_component(  # noqa: SLF001
        expected_owner_nonce,
        label="expected_owner_nonce",
    )
    record = capability.record()
    expected_record_fields = {
        "directory_identity",
        "directory_path",
        "owner_nonce",
        "purpose",
        "root_path",
        "schema_version",
    }
    expected_handoff_fields = {
        "account_kind",
        "directory_path",
        "from_owner_nonce",
        "root_path",
        "schema_version",
        "source_record_sha256",
        "to_owner_nonce",
        "transfer_nonce",
    }
    if (
        set(record) != expected_record_fields
        or set(ownership_handoff) != expected_handoff_fields
    ):
        raise BrokerProtocolError(
            "CONTROL_PARENT_HANDOFF_SHAPE_DRIFT",
            "control-parent capability or handoff shape differs",
        )
    absolute_endpoint = Path(os.path.abspath(endpoint_path))
    expected_parent = (
        Path(cast(str, record["root_path"]))
        / cast(str, record["directory_path"])
    )
    try:
        absolute_endpoint.relative_to(account.root)
    except ValueError:
        pass
    else:
        raise BrokerProtocolError(
            "ENDPOINT_INSIDE_ARTIFACT_ROOT",
            "broker endpoint cannot be a manifest-root descendant",
        )
    source_record = {
        **record,
        "owner_nonce": ownership_handoff["from_owner_nonce"],
    }
    transfer_nonce = ownership_handoff["transfer_nonce"]
    if (
        record["schema_version"]
        != budget.BUDGET_RETAINED_DIRECTORY_SCHEMA
        or record["purpose"] != "formal-control-parent"
        or record["owner_nonce"] != owner_nonce
        or absolute_endpoint.parent != expected_parent
        or absolute_endpoint.name != "budget-broker.sock"
        or ownership_handoff["schema_version"]
        != budget.BUDGET_OWNERSHIP_HANDOFF_SCHEMA
        or ownership_handoff["account_kind"] != "retained-directory"
        or ownership_handoff["directory_path"]
        != record["directory_path"]
        or ownership_handoff["root_path"] != record["root_path"]
        or ownership_handoff["to_owner_nonce"] != owner_nonce
        or ownership_handoff["source_record_sha256"]
        != hashlib.sha256(canonical_json_bytes(source_record)).hexdigest()
        or not isinstance(ownership_handoff["from_owner_nonce"], str)
        or not isinstance(transfer_nonce, str)
        or len(transfer_nonce) != 32
        or any(
            character not in "0123456789abcdef"
            for character in transfer_nonce
        )
    ):
        raise BrokerProtocolError(
            "CONTROL_PARENT_HANDOFF_IDENTITY_DRIFT",
            "control-parent capability or endpoint identity differs",
        )
    return dict(record)


def validate_transferred_final_release_parent(
    account: budget.FormalBudgetBroker,
    capability: FinalReleaseParentCapability,
    ownership_handoff: Mapping[str, object],
    *,
    expected_owner_nonce: str,
    expected_parent_path: Path,
) -> dict[str, object]:
    """Bind the two outside-root terminal extents to their sole retained parent."""

    owner_nonce = _nonce(expected_owner_nonce)
    expected_handoff_fields = {
        "directory_handoff",
        "reservation_handoffs",
        "schema_version",
        "to_owner_nonce",
    }
    if type(ownership_handoff) is not dict or set(ownership_handoff) != expected_handoff_fields:
        raise BrokerProtocolError(
            "FINAL_RELEASE_HANDOFF_SHAPE_DRIFT",
            "outside final-release handoff shape differs",
        )
    record = capability.record()
    absolute_parent = Path(os.path.abspath(expected_parent_path))
    try:
        absolute_parent.relative_to(account.root)
    except ValueError:
        pass
    else:
        raise BrokerProtocolError(
            "FINAL_RELEASE_PARENT_INSIDE_FORMAL_ROOT",
            "outside final-release parent is inside the formal artifact root",
        )
    directory_handoff = ownership_handoff["directory_handoff"]
    reservation_handoffs = ownership_handoff["reservation_handoffs"]
    if (
        ownership_handoff["schema_version"] != FINAL_RELEASE_PARENT_HANDOFF_SCHEMA
        or ownership_handoff["to_owner_nonce"] != owner_nonce
        or record["owner_nonce"] != owner_nonce
        or record["directory_path"] != OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE
        or record["path"] != str(absolute_parent)
        or capability.path != absolute_parent
        or type(directory_handoff) is not dict
        or directory_handoff.get("path") != str(absolute_parent)
        or directory_handoff.get("directory_path")
        != OUTSIDE_FINAL_RELEASE_PARENT_RELATIVE
        or directory_handoff.get("to_owner_nonce") != owner_nonce
        or type(reservation_handoffs) is not dict
        or set(reservation_handoffs) != set(OUTSIDE_FINAL_RELEASE_SPECS)
        or any(
            type(reservation_handoffs[purpose]) is not dict
            or reservation_handoffs[purpose].get("purpose") != purpose
            or reservation_handoffs[purpose].get("to_owner_nonce")
            != owner_nonce
            or reservation_handoffs[purpose].get("shared_parent_fd") is not True
            or reservation_handoffs[purpose].get("parent_path")
            != str(absolute_parent)
            for purpose in OUTSIDE_FINAL_RELEASE_SPECS
        )
    ):
        raise BrokerProtocolError(
            "FINAL_RELEASE_HANDOFF_IDENTITY_DRIFT",
            "outside final-release capability or handoff identity differs",
        )
    return record


def _prepared_fixed_reservation(
    account: budget.FormalBudgetBroker,
    purpose: str,
    reservation: budget.RetainedStagingReservation,
    *,
    to_owner_nonce: str,
) -> tuple[dict[str, object], int, int]:
    """Detach one exact-purpose reservation for one SCM_RIGHTS response."""

    spec = FIXED_PURPOSE_SPECS[purpose]
    reservation_record = reservation.record()
    staging_path = cast(str, reservation_record["staging_path"])
    target_path = str(
        PurePosixPath(spec.parent_path, spec.target_name)
    )
    account.bind_retained_staging_target(
        staging_path=staging_path,
        target_path=target_path,
    )
    parent_fd, staging_fd, successor, handoff = (
        reservation.detach_for_scm_rights(
            to_owner_nonce=to_owner_nonce,
        )
    )
    try:
        staged = PurePosixPath(cast(str, successor["staging_path"]))
        extent = PreparedExtent(
            artifact_class=cast(str, successor["artifact_class"]),
            maximum_bytes=cast(int, successor["maximum_bytes"]),
            parent_identity=_parent_identity(parent_fd),
            parent_path=spec.parent_path,
            staging_name=staged.name,
            target_name=spec.target_name,
            staging_identity=_identity(staging_fd),
        )
        return (
            {
                "extent": extent.as_record(),
                "ownership_handoff": handoff,
                "reservation_record": successor,
            },
            parent_fd,
            staging_fd,
        )
    except BaseException:
        os.close(parent_fd)
        os.close(staging_fd)
        raise


def _seal_abandoned_reservation(
    purpose: str,
    reservation: budget.RetainedStagingReservation,
    *,
    reason: str,
) -> dict[str, object]:
    """Make an untransferred failure extent immutable without refund or reuse."""

    spec = FIXED_PURPOSE_SPECS[purpose]
    record = reservation.record()
    extent = PreparedExtent(
        artifact_class=cast(str, record["artifact_class"]),
        maximum_bytes=cast(int, record["maximum_bytes"]),
        parent_identity=_parent_identity(reservation._parent_fd),  # noqa: SLF001
        parent_path=spec.parent_path,
        staging_name=PurePosixPath(cast(str, record["staging_path"])).name,
        target_name=spec.target_name,
        staging_identity=_identity(reservation._descriptor),  # noqa: SLF001
    )
    primary: BaseException | None = None
    try:
        return consume_once_extent(
            extent.as_record(),
            descriptor=reservation._descriptor,  # noqa: SLF001
            record={
                "schema_version": ABANDONED_RESERVATION_SCHEMA,
                "purpose": purpose,
                "reason": reason,
                "state": "SEALED_UNPUBLISHED_INCOMPLETE",
            },
        )
    except BaseException as exc:
        primary = exc
        try:
            os.fchmod(reservation._descriptor, 0o444)  # noqa: SLF001
            os.fsync(reservation._descriptor)  # noqa: SLF001
        except BaseException as cleanup_error:
            exc.add_note(
                "abandoned reservation sealing also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
        raise
    finally:
        try:
            reservation.close()
        except BaseException as cleanup_error:
            if primary is None:
                raise
            primary.add_note(
                "abandoned reservation descriptor cleanup also failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )


class _BoundBrokerEndpoint:
    """Thin adapter over the hardened guardian control-listener primitive."""

    def __init__(
        self,
        *,
        control_parent: budget.RetainedDirectoryCapability,
        absolute_path: Path,
        retired_absolute_path: Path,
    ) -> None:
        self.absolute_path = Path(os.path.abspath(absolute_path))
        self.retired_absolute_path = Path(
            os.path.abspath(retired_absolute_path)
        )
        if (
            self.absolute_path.parent != self.retired_absolute_path.parent
            or self.absolute_path.name != "budget-broker.sock"
            or self.retired_absolute_path.name
            != "budget-broker.sock.retired"
        ):
            raise BrokerProtocolError(
                "ENDPOINT_PATH_INVALID",
                "broker endpoint and retirement paths are not the fixed sibling pair",
            )
        self.control_parent: budget.RetainedDirectoryCapability | None = (
            control_parent
        )
        listener: guardian.GuardianControlListener | None = None
        try:
            listener = guardian.GuardianControlListener(
                self.absolute_path,
                retirement_path=self.retired_absolute_path,
            )
            retained_parent = os.fstat(control_parent.fileno())
            listener_parent = os.fstat(listener.parent.descriptor)
            if (
                not stat.S_ISDIR(retained_parent.st_mode)
                or (
                    retained_parent.st_dev,
                    retained_parent.st_ino,
                    retained_parent.st_uid,
                )
                != (
                    listener_parent.st_dev,
                    listener_parent.st_ino,
                    listener_parent.st_uid,
                )
            ):
                raise BrokerProtocolError(
                    "ENDPOINT_PARENT_IDENTITY_DRIFT",
                    "guardian listener parent differs from retained control capability",
                )
            self.listener = listener
            self.endpoint_identity = dict(listener.identity)
            listener = None
        except BaseException as exc:
            if listener is not None:
                self._close_listener_preserving(listener, exc)
            try:
                control_parent.close()
            except BaseException as cleanup_error:
                exc.add_note(
                    "broker control-parent close failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
            self.control_parent = None
            raise

    @staticmethod
    def _close_listener_preserving(
        listener: guardian.GuardianControlListener,
        primary: BaseException,
    ) -> None:
        if not listener.closed:
            try:
                listener.close_once()
            except BaseException as cleanup_error:
                primary.add_note(
                    "broker guardian-listener close failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        if listener.bound and not listener.remove_attempted:
            try:
                listener.remove_path_once()
            except BaseException as cleanup_error:
                primary.add_note(
                    "broker guardian-listener retirement failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        elif listener.parent_owned:
            try:
                listener.abandon_parent_once()
            except BaseException as cleanup_error:
                primary.add_note(
                    "broker guardian-listener parent release failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )

    def _close_descriptors_preserving(self, primary: BaseException) -> None:
        listener = getattr(self, "listener", None)
        if listener is not None:
            self.listener = None
            self._close_listener_preserving(listener, primary)
        control_parent = self.control_parent
        if control_parent is not None:
            self.control_parent = None
            try:
                control_parent.close()
            except BaseException as cleanup_error:
                primary.add_note(
                    "broker retained control-parent close failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )

    def retained_descriptors(self) -> set[int]:
        listener = self.listener
        control_parent = self.control_parent
        if (
            listener is None
            or listener.closed
            or not listener.parent_owned
            or control_parent is None
        ):
            raise BrokerProtocolError(
                "ENDPOINT_CLOSED",
                "broker endpoint is not live",
            )
        return {
            listener.socket.fileno(),
            listener.parent.descriptor,
            control_parent.fileno(),
        }

    def settimeout(self, value: float) -> None:
        listener = self.listener
        if listener is None or listener.closed:
            raise BrokerProtocolError(
                "ENDPOINT_CLOSED",
                "broker endpoint is not live",
            )
        listener.socket.settimeout(value)

    def accept(self) -> socket.socket:
        listener = self.listener
        control_parent = self.control_parent
        if (
            listener is None
            or listener.closed
            or control_parent is None
        ):
            raise BrokerProtocolError(
                "ENDPOINT_CLOSED",
                "broker endpoint is not live",
            )
        retained = os.fstat(control_parent.fileno())
        joined = listener._require_parent_join()  # noqa: SLF001
        observed = guardian._control_socket_identity_at(  # noqa: SLF001
            listener.parent.descriptor,
            listener.path,
        )
        listener_parent = os.fstat(listener.parent.descriptor)
        if (
            observed != listener.identity
            or (
                retained.st_dev,
                retained.st_ino,
                retained.st_uid,
            )
            != (
                listener_parent.st_dev,
                listener_parent.st_ino,
                listener_parent.st_uid,
            )
        ):
            raise BrokerProtocolError(
                "ENDPOINT_IDENTITY_DRIFT",
                "broker endpoint identity drifted before accept",
            )
        del joined
        connection, _address = listener.socket.accept()
        return connection

    def retire(self) -> dict[str, object]:
        """Use the guardian primitive's final-join/watch retirement."""

        listener = self.listener
        control_parent = self.control_parent
        if (
            listener is None
            or listener.closed
            or control_parent is None
        ):
            raise BrokerProtocolError(
                "ENDPOINT_CLOSED",
                "broker endpoint cannot be retired twice",
            )
        listener.close_once()
        try:
            retired = listener.remove_path_once()
        except BaseException as exc:
            self.listener = None
            try:
                control_parent.close()
            except BaseException as cleanup_error:
                exc.add_note(
                    "broker control-parent close also failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
            self.control_parent = None
            raise BrokerProtocolError(
                "ENDPOINT_RETIREMENT_FAILED",
                "guardian endpoint retirement failed closed",
            ) from exc
        retired_identity = retired.get("retired_identity")
        if (
            retired.get("absent") is not True
            or retired.get("retired_path") != str(self.retired_absolute_path)
            or type(retired_identity) is not dict
            or retired_identity.get("device")
            != self.endpoint_identity["device"]
            or retired_identity.get("inode")
            != self.endpoint_identity["inode"]
            or retired_identity.get("mode") != 0o600
            or retired_identity.get("uid") != self.endpoint_identity["uid"]
        ):
            primary = BrokerProtocolError(
                "ENDPOINT_RETIREMENT_FAILED",
                "guardian endpoint retirement identity differs",
            )
            try:
                control_parent.close()
            except BaseException as cleanup_error:
                primary.add_note(
                    "broker control-parent close also failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
            self.listener = None
            self.control_parent = None
            raise primary
        try:
            control_parent.close()
        except BaseException as exc:
            self.listener = None
            self.control_parent = None
            raise BrokerProtocolError(
                "ENDPOINT_RETIREMENT_FAILED",
                "retained control-parent close failed after retirement",
            ) from exc
        self.listener = None
        self.control_parent = None
        return cast(dict[str, object], retired_identity)

class _SharedBrokerRuntime:
    """Cross-session grant, allocation, journal, and shutdown state."""

    def __init__(
        self,
        *,
        actor: Mapping[str, object],
        nonce: str,
        supervisor_grant: BrokerSessionGrant,
        bootstrap_handoff_spec: Mapping[str, object],
        bootstrap_handoff_base: Mapping[str, object],
        bootstrap_failure_closeout_path: Path,
        control_endpoint_path: Path,
        retired_endpoint_path: Path,
        formal_artifact_contracts: Sequence[Mapping[str, object]],
        formal_append_contracts: Sequence[Mapping[str, object]],
        arm_artifact_contracts: Mapping[
            str, Mapping[str, Mapping[str, object]]
        ],
        arm_append_contracts: Mapping[
            str, Sequence[Mapping[str, object]]
        ],
    ) -> None:
        if supervisor_grant.role not in {"bootstrap-admin", "supervisor"}:
            raise BrokerProtocolError(
                "GRANT_SCOPE_DRIFT",
                "persistent broker requires one bootstrap-admin or legacy supervisor grant",
            )
        self.actor = dict(actor)
        self.nonce = _nonce(nonce)
        self._bootstrap_admin_required = (
            supervisor_grant.role == "bootstrap-admin"
        )
        self._bootstrap_handoff_spec = _bootstrap_handoff_spec(
            bootstrap_handoff_spec
        )
        self._bootstrap_handoff_base = dict(bootstrap_handoff_base)
        self._bootstrap_failure_closeout_path = Path(
            os.path.abspath(bootstrap_failure_closeout_path)
        )
        self._control_endpoint_path = Path(
            os.path.abspath(control_endpoint_path)
        )
        self._retired_endpoint_path = Path(
            os.path.abspath(retired_endpoint_path)
        )
        self.publication_policy = _PublicationPolicyState(
            formal_artifacts=formal_artifact_contracts,
            formal_channels=formal_append_contracts,
            arm_artifacts=arm_artifact_contracts,
            arm_channels=arm_append_contracts,
        )
        if not self._bootstrap_failure_closeout_path.is_absolute():
            raise BrokerProtocolError(
                "BOOTSTRAP_FAILURE_PATH_DRIFT",
                "bootstrap failure closeout path is not absolute",
            )
        self._bootstrap_handoff_state = "PENDING"
        self._bootstrap_handoff_identity: dict[str, object] | None = None
        self._bootstrap_abort_terminal: dict[str, object] | None = None
        self._lock = threading.RLock()
        self._grant_changed = threading.Condition(self._lock)
        self._grants = {
            supervisor_grant.credential_sha256: supervisor_grant,
        }
        self._manager_openfile_grants: dict[
            str,
            _ManagerOpenFileGrant,
        ] = {}
        self._journal_sequence = 0
        self._allocations: dict[str, dict[str, object]] = {}
        self._pending_arm_response: dict[str, object] | None = None
        self._accepted_arm_responses: dict[
            str, dict[str, object]
        ] = {}
        self._arm_post_seal_reservations: dict[
            str,
            dict[str, dict[str, object]],
        ] = {}
        self._selection_identity: dict[str, object] | None = None
        self._active_roles: dict[int, str] = {}
        self._active_nonarm_grants: dict[
            int, dict[str, object]
        ] = {}
        self._formal_launch_owner_process: Any | None = None
        self._formal_launch_owner_handoff: dict[str, object] | None = None
        self._formal_launch_claim_identity: dict[str, object] | None = None
        self._formal_launch_claim_peer: dict[str, int] | None = None
        self._formal_launch_claim_state = "ABSENT"
        self._recovery_pid: int | None = None
        self._recovery_process: Any | None = None
        self._recovery_handoff: dict[str, object] | None = None
        self._recovery_lock_extent: dict[str, object] | None = None
        self._recovery_operation_in_progress = False
        self._recovery_disarm_intent: dict[str, object] | None = None
        self._recovery_terminal: dict[str, object] | None = None
        self._closure_handoff: dict[str, object] | None = None
        self._release_parent_fd: int | None = None
        self._release_extents: dict[
            str,
            tuple[dict[str, object], int],
        ] = {}
        self._release_operation_in_progress = False
        self._release_terminal: dict[str, object] | None = None
        self.exit_requested = threading.Event()
        self.fatal_error: BaseException | None = None

    def closure_control_endpoint_paths(self) -> list[str]:
        """Return the exact four ephemeral endpoint paths for final absence."""

        parent = self._control_endpoint_path.parent
        if (
            self._control_endpoint_path.name != "budget-broker.sock"
            or self._retired_endpoint_path.name
            != "budget-broker.sock.retired"
            or self._retired_endpoint_path.parent != parent
        ):
            raise BrokerProtocolError(
                "CONTROL_ENDPOINT_PATH_DRIFT",
                "broker control endpoint topology differs",
            )
        return [
            str(self._control_endpoint_path),
            str(self._retired_endpoint_path),
            str(parent / "guardian-control.sock"),
            str(parent / "guardian-control.sock.retired"),
        ]

    def claim_bootstrap_handoff(
        self,
        record: Mapping[str, object],
    ) -> dict[str, object]:
        with self._lock:
            if not self._bootstrap_admin_required:
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_NOT_APPLICABLE",
                    "legacy supervisor mode has no bootstrap-admin publication",
                )
            if self._bootstrap_handoff_state != "PENDING":
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_ALREADY_ATTEMPTED",
                    "bootstrap handoff publication cannot be retried",
                )
            if self._recovery_handoff is None:
                raise BrokerProtocolError(
                    "RECOVERY_OWNER_NOT_READY",
                    "bootstrap handoff requires the persistent recovery owner",
                )
            expected = {
                **dict(self._bootstrap_handoff_base),
                "recovery_owner_observation": {
                    **dict(self._recovery_handoff),
                    "control_owner": "persistent-budget-broker",
                    "state": "BROKER_RETAINED_CONTROL",
                },
            }
            if dict(record) != expected:
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_RECORD_DRIFT",
                    "bootstrap handoff record differs from live retained authority",
                )
            self._bootstrap_handoff_state = "PUBLICATION_IN_PROGRESS"
            return dict(self._bootstrap_handoff_spec)

    def commit_bootstrap_handoff(
        self,
        identity: Mapping[str, object],
    ) -> None:
        checked = _detached_identity(
            identity,
            label="formal-root budget handoff",
        )
        with self._lock:
            if self._bootstrap_handoff_state != "PUBLICATION_IN_PROGRESS":
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_STATE_DRIFT",
                    "bootstrap handoff commit lacks its sole publication attempt",
                )
            self._bootstrap_handoff_identity = checked
            self._bootstrap_handoff_state = "PUBLISHED"

    def begin_bootstrap_abort(
        self,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        _exact_keys(
            payload,
            {
                "bootstrap_failure_identity",
                "reason_sha256",
                "state",
            },
            label="bootstrap abort",
        )
        reason = payload["reason_sha256"]
        if (
            payload["state"] != "markerless-incomplete"
            or not isinstance(reason, str)
            or len(reason) != 64
            or any(character not in "0123456789abcdef" for character in reason)
        ):
            raise BrokerProtocolError(
                "BOOTSTRAP_ABORT_RECORD_DRIFT",
                "bootstrap abort classification or reason differs",
            )
        failure_identity = _require_detached_bytes(
            payload["bootstrap_failure_identity"],
            expected_path=self._bootstrap_failure_closeout_path,
            label="bootstrap package failure closeout",
        )
        with self._lock:
            if (
                not self._bootstrap_admin_required
                or self._bootstrap_abort_terminal is not None
                or self._bootstrap_handoff_state
                not in {"PENDING", "PUBLISHED"}
            ):
                raise BrokerProtocolError(
                    "BOOTSTRAP_ABORT_STATE_DRIFT",
                    "bootstrap abort is duplicate or crosses an uncertain publication",
                )
            prior_handoff_state = self._bootstrap_handoff_state
            self._bootstrap_handoff_state = "ABORT_IN_PROGRESS"
        return {
            "bootstrap_failure_identity": failure_identity,
            "prior_handoff_state": prior_handoff_state,
            "reason_sha256": reason,
            "state": "markerless-incomplete",
        }

    def finish_bootstrap_abort(
        self,
        result: Mapping[str, object],
    ) -> None:
        with self._lock:
            if self._bootstrap_handoff_state != "ABORT_IN_PROGRESS":
                raise BrokerProtocolError(
                    "BOOTSTRAP_ABORT_STATE_DRIFT",
                    "bootstrap abort terminal lacks its sole begin transition",
                )
            self._bootstrap_abort_terminal = dict(result)
            self._bootstrap_handoff_state = "ABORTED"
            self.exit_requested.set()

    def next_journal_sequence(self) -> int:
        with self._lock:
            sequence = self._journal_sequence
            self._journal_sequence += 1
            return sequence

    def authenticate(self, frame: ReceivedFrame) -> BrokerSessionGrant:
        record = frame.record
        _exact_keys(
            record,
            {
                "allocation_identity",
                "arm_slot",
                "credential",
                "nonce",
                "role",
                "schema_version",
                "selection_identity",
            },
            label="broker authentication",
        )
        credential = _nonce(record["credential"])
        if (
            record["schema_version"] != AUTHENTICATION_SCHEMA
            or _nonce(record["nonce"]) != self.nonce
        ):
            raise BrokerProtocolError(
                "AUTHENTICATION_IDENTITY_DRIFT",
                "broker authentication schema or nonce drifted",
            )
        digest = hashlib.sha256(credential.encode("ascii")).hexdigest()
        with self._lock:
            try:
                grant = self._grants.pop(digest)
            except KeyError as exc:
                raise BrokerProtocolError(
                    "CREDENTIAL_ALREADY_CONSUMED_OR_UNKNOWN",
                    "broker credential is unknown or was already consumed",
                ) from exc
            observed_peer = {
                field: frame.peer[field]
                for field in ("pid", "pid_starttime", "uid")
            }
            if (
                observed_peer != grant.expected_peer
                or record["role"] != grant.role
                or record["arm_slot"] != grant.arm_slot
                or record["selection_identity"] != grant.selection_identity
                or record["allocation_identity"] != grant.allocation_identity
            ):
                raise BrokerProtocolError(
                    "AUTHENTICATION_IDENTITY_DRIFT",
                    "broker authentication differs from its exact grant",
                )
            self._active_roles[frame.peer["pid"]] = grant.role
            if grant.role in {
                "formal-closeout-owner",
                "formal-launch-owner",
                "formal-worker",
            }:
                self._active_nonarm_grants[frame.peer["pid"]] = {
                    "credential_sha256": grant.credential_sha256,
                    "expected_peer": dict(grant.expected_peer),
                    "role": grant.role,
                }
            return grant

    def release_session(self, peer_pid: int) -> None:
        with self._lock:
            self._active_roles.pop(peer_pid, None)
            self._active_nonarm_grants.pop(peer_pid, None)
            if (
                self._formal_launch_claim_peer is not None
                and self._formal_launch_claim_peer["pid"] == peer_pid
                and self._formal_launch_claim_state
                in {"AUTHENTICATED", "CONTROL_TRANSFER_IN_PROGRESS"}
            ):
                self._formal_launch_claim_state = (
                    "CONSUMED_INCOMPLETE_NO_RETRY"
                )

    def confirm_bound_nonarm_session(
        self,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        """Prove the exact registered owner consumed and holds its grant."""

        _exact_keys(
            payload,
            {"credential_sha256", "expected_peer", "role"},
            label="confirm bound non-arm session",
        )
        peer = _peer_grant_identity(
            payload["expected_peer"],
            label="confirmed bound non-arm session",
        )
        role = payload["role"]
        digest = payload["credential_sha256"]
        if (
            role not in {
                "formal-closeout-owner",
                "formal-launch-owner",
                "formal-worker",
            }
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise BrokerProtocolError(
                "GRANT_SCOPE_DRIFT",
                "confirmed non-arm grant discriminator is invalid",
            )
        with self._lock:
            observed = self._active_nonarm_grants.get(peer["pid"])
            if (
                observed
                != {
                    "credential_sha256": digest,
                    "expected_peer": peer,
                    "role": role,
                }
                or digest in self._grants
                or process_starttime(peer["pid"]) != peer["pid_starttime"]
            ):
                raise BrokerProtocolError(
                    "BOUND_NONARM_SESSION_NOT_LIVE",
                    "registered non-arm owner has not consumed its exact grant",
                )
            return {
                "credential_sha256": digest,
                "expected_peer": peer,
                "role": role,
                "state": "EXACT_OWNER_SESSION_LIVE",
            }

    def retain_formal_launch_owner(
        self,
        *,
        process: Any,
        handoff: Mapping[str, object],
        claim_identity: Mapping[str, object],
    ) -> None:
        """Retain the package actor and broker-hosted relay past admin close."""

        checked_claim = _claim_identity(
            claim_identity,
            label="retained formal-launch owner claim",
        )
        with self._lock:
            if (
                self._formal_launch_owner_process is not None
                or self._formal_launch_owner_handoff is not None
                or self._formal_launch_claim_state != "ABSENT"
            ):
                raise BrokerProtocolError(
                    "FORMAL_LAUNCH_OWNER_ALREADY_RETAINED",
                    "formal-launch owner cannot be replaced or retried",
                )
            self._formal_launch_owner_process = process
            self._formal_launch_owner_handoff = dict(handoff)
            self._formal_launch_claim_identity = checked_claim
            self._formal_launch_claim_state = "ISSUED"

    def register_formal_launch_claimant(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
    ) -> dict[str, object]:
        _exact_keys(
            payload,
            {"claim_identity", "expected_peer"},
            label="formal-launch owner claimant registration",
        )
        claim = _claim_identity(
            payload["claim_identity"],
            label="formal-launch owner claimant registration claim",
        )
        peer = _peer_grant_identity(
            payload["expected_peer"],
            label="formal-launch owner claimant",
        )
        if (
            _pidfd_target_pid(pidfd) != peer["pid"]
            or pidfd_reports_exit(pidfd)
            or process_starttime(peer["pid"]) != peer["pid_starttime"]
            or peer["uid"] != os.getuid()
        ):
            raise BrokerProtocolError(
                "PIDFD_IDENTITY_DRIFT",
                "formal-launch owner claimant pidfd differs",
            )
        with self._lock:
            if (
                self._formal_launch_claim_state != "ISSUED"
                or claim != self._formal_launch_claim_identity
                or self._formal_launch_claim_peer is not None
            ):
                raise BrokerProtocolError(
                    "FORMAL_LAUNCH_CLAIM_STATE_DRIFT",
                    "formal-launch owner claimant cannot be registered",
                )
            self._formal_launch_claim_peer = peer
            self._formal_launch_claim_state = "CLAIMANT_REGISTERED"
        return {
            "claim_identity": claim,
            "expected_peer": peer,
            "state": "CLAIMANT_REGISTERED",
        }

    def authenticate_formal_launch_claim(
        self,
        frame: ReceivedFrame,
        *,
        native_helper: NativeHelperProtocol,
    ) -> BrokerSessionGrant:
        _exact_keys(
            frame.record,
            {"claim_identity", "nonce", "role", "schema_version"},
            label="formal-launch owner claim authentication",
        )
        if (
            frame.record["schema_version"]
            != FORMAL_LAUNCH_OWNER_CLAIM_AUTHENTICATION_SCHEMA
            or frame.record["nonce"] != self.nonce
            or frame.record["role"] != "formal-launch-claimant"
            or len(frame.descriptors) != 1
        ):
            raise BrokerProtocolError(
                "FORMAL_LAUNCH_CLAIM_AUTHENTICATION_DRIFT",
                "formal-launch owner claim authentication differs",
            )
        claim = _claim_identity(
            frame.record["claim_identity"],
            label="formal-launch owner claim authentication identity",
        )
        descriptor = frame.descriptors[0]
        try:
            _verify_claim_memfd(native_helper, descriptor, claim)
        finally:
            os.close(descriptor)
        peer = {
            key: frame.peer[key]
            for key in ("pid", "pid_starttime", "uid")
        }
        with self._lock:
            if (
                self._formal_launch_claim_state != "CLAIMANT_REGISTERED"
                or claim != self._formal_launch_claim_identity
                or peer != self._formal_launch_claim_peer
            ):
                raise BrokerProtocolError(
                    "FORMAL_LAUNCH_CLAIM_STATE_DRIFT",
                    "formal-launch owner claim is unknown, consumed, or misbound",
                )
            self._formal_launch_claim_state = "AUTHENTICATED"
            self._active_roles[peer["pid"]] = "formal-launch-claimant"
        return BrokerSessionGrant(
            role="formal-launch-claimant",
            credential_sha256=cast(str, claim["sha256"]),
            expected_peer=peer,
            arm_slot=None,
            selection_identity=None,
            allocation_identity=None,
        )

    def transfer_formal_launch_owner_control(
        self,
        *,
        peer: Mapping[str, int],
    ) -> tuple[dict[str, object], int]:
        claimant = {
            key: peer[key]
            for key in ("pid", "pid_starttime", "uid")
        }
        with self._lock:
            process = self._formal_launch_owner_process
            if (
                process is None
                or self._formal_launch_owner_handoff is None
                or self._formal_launch_claim_state != "AUTHENTICATED"
                or self._formal_launch_claim_peer != claimant
            ):
                raise BrokerProtocolError(
                    "FORMAL_LAUNCH_CLAIM_STATE_DRIFT",
                    "formal-launch owner control cannot be transferred",
                )
            self._formal_launch_claim_state = "CONTROL_TRANSFER_IN_PROGRESS"
            descriptor = process.detach_control_descriptor()
            return (
                {
                    "claim_identity": dict(
                        cast(
                            Mapping[str, object],
                            self._formal_launch_claim_identity,
                        )
                    ),
                    "owner_actor": dict(process.actor),
                    "owner_handoff_identity": _message_identity(
                        self._formal_launch_owner_handoff
                    ),
                    "state": "CONTROL_FD_TRANSFERRED_PENDING_ACK",
                },
                descriptor,
            )

    def acknowledge_formal_launch_owner_control(
        self,
        *,
        peer: Mapping[str, int],
    ) -> dict[str, object]:
        claimant = {
            key: peer[key]
            for key in ("pid", "pid_starttime", "uid")
        }
        with self._lock:
            if (
                self._formal_launch_claim_state
                != "CONTROL_TRANSFER_IN_PROGRESS"
                or self._formal_launch_claim_peer != claimant
            ):
                raise BrokerProtocolError(
                    "FORMAL_LAUNCH_CLAIM_STATE_DRIFT",
                    "formal-launch owner control ACK is late or duplicated",
                )
            self._formal_launch_claim_state = "CLAIMED"
            return {
                "claim_identity": dict(
                    cast(
                        Mapping[str, object],
                        self._formal_launch_claim_identity,
                    )
                ),
                "state": "CONTROL_FD_CLAIM_ACKNOWLEDGED",
            }

    def formal_launch_owner_handoff(self) -> dict[str, object]:
        with self._lock:
            if (
                self._formal_launch_owner_process is None
                or self._formal_launch_owner_handoff is None
            ):
                raise BrokerProtocolError(
                    "FORMAL_LAUNCH_OWNER_NOT_RETAINED",
                    "formal-launch owner is absent",
                )
            return dict(self._formal_launch_owner_handoff)

    def deliver_formal_launch_owner_context(
        self,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        _exact_keys(
            payload,
            {"context"},
            label="formal-launch owner delayed context",
        )
        with self._lock:
            process = self._formal_launch_owner_process
            if (
                process is None
                or self._formal_launch_owner_handoff is None
                or self._formal_launch_owner_handoff.get("context_state")
                != "AWAITING_DELAYED_CONTEXT"
            ):
                raise BrokerProtocolError(
                    "FORMAL_LAUNCH_OWNER_CONTEXT_STATE_DRIFT",
                    "formal-launch owner context is duplicate or owner absent",
                )
            self._formal_launch_owner_handoff[
                "context_state"
            ] = "DELIVERY_IN_PROGRESS"
        result = process.deliver_context(
            cast(Mapping[str, object], payload["context"])
        )
        with self._lock:
            self._formal_launch_owner_handoff[
                "context_state"
            ] = "CONTEXT_RETAINED"
            self._formal_launch_owner_handoff[
                "context_acknowledgement"
            ] = dict(result)
        return dict(result)

    def abandon_formal_launch_owner(self) -> None:
        """Close retained parent handles; the owner treats relay EOF as failure."""

        with self._lock:
            process = self._formal_launch_owner_process
            self._formal_launch_owner_process = None
        if process is not None:
            process.close()

    def bind_selection(self, value: object) -> dict[str, object]:
        selected = _detached_identity(value, label="formal selection")
        with self._lock:
            if self._selection_identity is not None:
                raise BrokerProtocolError(
                    "SELECTION_ALREADY_BOUND",
                    "formal selection cannot be rebound",
                )
            self._selection_identity = selected
            return dict(selected)

    def remember_allocation(
        self,
        arm_slot: str,
        result: Mapping[str, object],
    ) -> dict[str, object]:
        identity = _message_identity(result)
        with self._lock:
            if arm_slot in self._allocations:
                raise BrokerProtocolError(
                    "ALLOCATION_ALREADY_BOUND",
                    "arm allocation identity cannot be rebound",
                )
            self._allocations[arm_slot] = identity
            return dict(identity)

    def require_allocation(
        self,
        arm_slot: str,
        allocation_identity: object,
    ) -> dict[str, object]:
        slot = budget._safe_component(arm_slot, label="arm_slot")  # noqa: SLF001
        if type(allocation_identity) is not dict:
            raise BrokerProtocolError(
                "FRAME_SHAPE_MISMATCH",
                "arm allocation identity is not one object",
            )
        raw_identity = cast(dict[str, object], allocation_identity)
        _exact_keys(
            raw_identity,
            {"sha256", "size_bytes"},
            label="arm allocation identity",
        )
        checked = {
            "sha256": _sha256(
                raw_identity["sha256"],
                label="arm allocation identity sha256",
            ),
            "size_bytes": _positive_int(
                raw_identity["size_bytes"],
                label="arm allocation identity size_bytes",
            ),
        }
        with self._lock:
            expected = self._allocations.get(slot)
            if expected is None or checked != expected:
                raise BrokerProtocolError(
                    "ALLOCATION_IDENTITY_DRIFT",
                    "arm seal allocation identity differs from the durable allocation",
                )
            return dict(expected)

    def register_pending_arm_response(
        self,
        *,
        arm_slot: str,
        arm_attempt_prefix: str,
        manifest_identity: Mapping[str, object],
        terminal_identity: Mapping[str, object],
        response_nonce: str,
        response_sequence: int,
        response_sha256: str,
        session_connection_identity: Sequence[int],
        session_grant: Mapping[str, object],
        session_instance_id: str,
        session_peer: Mapping[str, object],
        session_peer_pidfd_method: str,
    ) -> dict[str, object]:
        if (
            not isinstance(session_peer_pidfd_method, str)
            or not session_peer_pidfd_method
        ):
            raise BrokerProtocolError(
                "PIDFD_METHOD_DRIFT",
                "arm seal session pidfd method is absent",
            )
        pending: dict[str, object] = {
            "arm_attempt_prefix": arm_attempt_prefix,
            "arm_slot": budget._safe_component(  # noqa: SLF001
                arm_slot,
                label="arm_slot",
            ),
            "manifest_identity": _detached_identity(
                manifest_identity,
                label="arm manifest",
            ),
            "response_authentication": {
                "nonce": _nonce(response_nonce),
                "response_sequence": _positive_int(
                    response_sequence,
                    label="response_sequence",
                ),
                "response_sha256": _sha256(
                    response_sha256,
                    label="response_sha256",
                ),
            },
            "session_connection_identity": [
                _nonnegative_int(
                    item,
                    label="session connection identity",
                )
                for item in session_connection_identity
            ],
            "session_grant": dict(session_grant),
            "session_instance_id": _nonce(session_instance_id),
            "session_peer": _peer_grant_identity(
                session_peer,
                label="arm seal session peer",
            ),
            "session_peer_pidfd_method": session_peer_pidfd_method,
            "terminal_identity": _detached_identity(
                terminal_identity,
                label="arm budget terminal",
            ),
        }
        with self._lock:
            if self._pending_arm_response is not None:
                raise BrokerProtocolError(
                    "PRIOR_RESPONSE_UNACKNOWLEDGED",
                    "another arm seal response still awaits successor acceptance",
                )
            self._pending_arm_response = pending
            return dict(pending)

    def pending_arm_response(self) -> dict[str, object] | None:
        with self._lock:
            return (
                None
                if self._pending_arm_response is None
                else dict(self._pending_arm_response)
            )

    def claim_pending_arm_response(
        self,
        payload: Mapping[str, object],
        *,
        session_connection_identity: Sequence[int],
        session_grant: Mapping[str, object],
        session_instance_id: str,
        session_peer: Mapping[str, object],
        session_peer_pidfd_method: str,
    ) -> dict[str, object]:
        _exact_keys(
            payload,
            {
                "continuation",
                "prior_response_authentication",
                "successor_arm_slot",
            },
            label="prior arm response acceptance",
        )
        continuation = payload["continuation"]
        successor = payload["successor_arm_slot"]
        if continuation == "next-arm":
            if not isinstance(successor, str):
                raise BrokerProtocolError(
                    "PRIOR_RESPONSE_ACCEPTANCE_DRIFT",
                    "next-arm acceptance lacks its exact successor slot",
                )
            successor = budget._safe_component(  # noqa: SLF001
                successor,
                label="successor_arm_slot",
            )
        elif continuation == "formal-finalize":
            if successor is not None:
                raise BrokerProtocolError(
                    "PRIOR_RESPONSE_ACCEPTANCE_DRIFT",
                    "formal-finalize acceptance cannot name another arm",
                )
        else:
            raise BrokerProtocolError(
                "PRIOR_RESPONSE_ACCEPTANCE_DRIFT",
                "prior response continuation differs",
            )
        raw_authentication = payload["prior_response_authentication"]
        if type(raw_authentication) is not dict:
            raise BrokerProtocolError(
                "FRAME_SHAPE_MISMATCH",
                "prior response authentication is not one object",
            )
        authentication = cast(dict[str, object], raw_authentication)
        _exact_keys(
            authentication,
            {"nonce", "response_sequence", "response_sha256"},
            label="prior response authentication",
        )
        checked_authentication = {
            "nonce": _nonce(authentication["nonce"]),
            "response_sequence": _positive_int(
                authentication["response_sequence"],
                label="response_sequence",
            ),
            "response_sha256": _sha256(
                authentication["response_sha256"],
                label="response_sha256",
            ),
        }
        with self._lock:
            pending = self._pending_arm_response
            if (
                pending is None
                or pending["response_authentication"]
                != checked_authentication
                or pending["session_instance_id"]
                != _nonce(session_instance_id)
                or pending["session_connection_identity"]
                != [
                    _nonnegative_int(
                        item,
                        label="accepting session connection identity",
                    )
                    for item in session_connection_identity
                ]
                or pending["session_grant"] != dict(session_grant)
                or pending["session_peer"]
                != _peer_grant_identity(
                    session_peer,
                    label="arm seal accepting peer",
                )
                or pending["session_peer_pidfd_method"]
                != session_peer_pidfd_method
                or (
                    continuation == "next-arm"
                    and successor == pending["arm_slot"]
                )
            ):
                raise BrokerProtocolError(
                    "PRIOR_RESPONSE_ACCEPTANCE_DRIFT",
                    "successor request does not bind the pending seal response",
                )
            return {
                **dict(pending),
                "continuation": continuation,
                "successor_arm_slot": successor,
            }

    def commit_pending_arm_response(
        self,
        accepted: Mapping[str, object],
        *,
        acceptance_identity: Mapping[str, object],
    ) -> None:
        checked_acceptance = _detached_identity(
            acceptance_identity,
            label="prior-response-accepted journal",
        )
        with self._lock:
            if (
                self._pending_arm_response is None
                or any(
                    accepted.get(key) != self._pending_arm_response.get(key)
                    for key in (
                        "arm_attempt_prefix",
                        "arm_slot",
                        "manifest_identity",
                        "response_authentication",
                        "terminal_identity",
                    )
                )
            ):
                raise BrokerProtocolError(
                    "PRIOR_RESPONSE_ACCEPTANCE_DRIFT",
                    "durable acceptance no longer names the pending seal",
                )
            slot = cast(str, self._pending_arm_response["arm_slot"])
            if slot in self._accepted_arm_responses:
                raise BrokerProtocolError(
                    "PRIOR_RESPONSE_ACCEPTANCE_DRIFT",
                    "arm acceptance identity is already committed",
                )
            self._accepted_arm_responses[slot] = {
                **dict(accepted),
                "prior_response_accepted_identity": checked_acceptance,
                "post_seal_state": "AWAITING_REPLAY",
            }
            self._pending_arm_response = None

    def register_arm_post_seal_reservations(
        self,
        arm_slot: str,
        *,
        replay: budget.RetainedStagingReservation,
        replay_target_path: str,
        consumption: budget.RetainedStagingReservation,
        consumption_target_path: str,
    ) -> None:
        slot = budget._safe_component(arm_slot, label="arm_slot")  # noqa: SLF001
        records = {
            "replay": {
                "reservation": replay,
                "record": replay.record(),
                "target_path": replay_target_path,
            },
            "consumption": {
                "reservation": consumption,
                "record": consumption.record(),
                "target_path": consumption_target_path,
            },
        }
        with self._lock:
            if slot in self._arm_post_seal_reservations:
                raise BrokerProtocolError(
                    "ARM_POST_SEAL_STATE_DRIFT",
                    "arm post-seal extents are already registered",
                )
            for kind, entry in records.items():
                record = cast(dict[str, object], entry["record"])
                if (
                    record.get("arm_slot") != slot
                    or record.get("artifact_class") != "closeout"
                    or type(entry["target_path"]) is not str
                ):
                    raise BrokerProtocolError(
                        "ARM_POST_SEAL_STATE_DRIFT",
                        f"{kind} post-seal extent identity differs",
                    )
            self._arm_post_seal_reservations[slot] = records

    def claim_arm_post_seal_reservation(
        self,
        arm_slot: str,
        *,
        kind: str,
        allocation_identity: object,
        prior_response_accepted_identity: object,
        prerequisite_identity: object | None,
        session_connection_identity: Sequence[int],
        session_grant: Mapping[str, object],
        session_instance_id: str,
    ) -> tuple[
        budget.RetainedStagingReservation,
        dict[str, object],
    ]:
        slot = budget._safe_component(arm_slot, label="arm_slot")  # noqa: SLF001
        if kind not in {"replay", "consumption"}:
            raise BrokerProtocolError(
                "ARM_POST_SEAL_STATE_DRIFT",
                "unknown post-seal artifact kind",
            )
        checked_allocation = self.require_allocation(
            slot,
            allocation_identity,
        )
        checked_acceptance = _detached_identity(
            prior_response_accepted_identity,
            label="prior-response-accepted journal",
        )
        with self._lock:
            accepted = self._accepted_arm_responses.get(slot)
            reservations = self._arm_post_seal_reservations.get(slot)
            expected_state = (
                "AWAITING_REPLAY"
                if kind == "replay"
                else "AWAITING_CONSUMPTION"
            )
            if (
                accepted is None
                or reservations is None
                or accepted.get("post_seal_state") != expected_state
                or accepted.get("prior_response_accepted_identity")
                != checked_acceptance
                or accepted.get("session_connection_identity")
                != list(session_connection_identity)
                or accepted.get("session_grant") != dict(session_grant)
                or accepted.get("session_instance_id")
                != _nonce(session_instance_id)
                or (
                    kind == "replay"
                    and prerequisite_identity is not None
                )
                or (
                    kind == "consumption"
                    and _detached_identity(
                        prerequisite_identity,
                        label="arm root replay",
                    )
                    != accepted.get("replay_identity")
                )
            ):
                raise BrokerProtocolError(
                    "ARM_POST_SEAL_STATE_DRIFT",
                    "post-seal publication does not bind its accepted arm",
                )
            entry = reservations[kind]
            reservation = entry.get("reservation")
            if not isinstance(
                reservation,
                budget.RetainedStagingReservation,
            ):
                raise BrokerProtocolError(
                    "ARM_POST_SEAL_STATE_DRIFT",
                    "post-seal extent was already consumed or is uncertain",
                )
            entry["reservation"] = None
            accepted["post_seal_state"] = f"{kind.upper()}_IN_PROGRESS"
            return reservation, {
                "allocation_identity": checked_allocation,
                "reservation_record": dict(
                    cast(dict[str, object], entry["record"])
                ),
                "target_path": entry["target_path"],
            }

    def commit_arm_post_seal_publication(
        self,
        arm_slot: str,
        *,
        kind: str,
        publication_identity: Mapping[str, object],
        journal_identity: Mapping[str, object],
    ) -> None:
        slot = budget._safe_component(arm_slot, label="arm_slot")  # noqa: SLF001
        publication = _detached_identity(
            publication_identity,
            label=f"arm post-seal {kind}",
        )
        journal = _detached_identity(
            journal_identity,
            label=f"arm post-seal {kind} journal",
        )
        with self._lock:
            accepted = self._accepted_arm_responses.get(slot)
            if (
                accepted is None
                or accepted.get("post_seal_state")
                != f"{kind.upper()}_IN_PROGRESS"
            ):
                raise BrokerProtocolError(
                    "ARM_POST_SEAL_STATE_DRIFT",
                    "post-seal commit lacks its sole in-progress extent",
                )
            accepted[f"{kind}_identity"] = publication
            accepted[f"{kind}_journal_identity"] = journal
            accepted["post_seal_state"] = (
                "AWAITING_CONSUMPTION"
                if kind == "replay"
                else "CLOSED"
            )

    def fail_arm_post_seal_publication(
        self,
        arm_slot: str,
    ) -> None:
        slot = budget._safe_component(arm_slot, label="arm_slot")  # noqa: SLF001
        with self._lock:
            accepted = self._accepted_arm_responses.get(slot)
            if accepted is not None:
                accepted["post_seal_state"] = "INCOMPLETE"

    def fail_pending_arm_response(self, arm_slot: str) -> None:
        slot = budget._safe_component(arm_slot, label="arm_slot")  # noqa: SLF001
        with self._lock:
            if (
                self._pending_arm_response is None
                or self._pending_arm_response.get("arm_slot") != slot
            ):
                raise BrokerProtocolError(
                    "PRIOR_RESPONSE_ACCEPTANCE_DRIFT",
                    "failed seal response no longer names the pending arm",
                )
            self._pending_arm_response = None

    def fail_pending_arm_response_for_session(
        self,
        session_instance_id: str,
    ) -> str | None:
        checked_session = _nonce(session_instance_id)
        with self._lock:
            pending = self._pending_arm_response
            if (
                pending is None
                or pending.get("session_instance_id") != checked_session
            ):
                return None
            slot = cast(str, pending["arm_slot"])
            self._pending_arm_response = None
            return slot

    def register_bound_arm_grant(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
    ) -> dict[str, object]:
        """Register one arm credential against the exact live pidfd target."""

        _exact_keys(
            payload,
            {
                "allocation_identity",
                "arm_slot",
                "credential",
                "expected_peer",
                "role",
                "selection_identity",
            },
            label="register bound arm grant",
        )
        peer = _peer_grant_identity(
            payload["expected_peer"],
            label="bound arm grant",
        )
        role = payload["role"]
        if role not in {"arm", "arm-authority", "arm-supervisor"}:
            raise BrokerProtocolError(
                "GRANT_SCOPE_DRIFT",
                "bound arm grant role is not permitted",
            )
        if (
            _pidfd_target_pid(pidfd) != peer["pid"]
            or pidfd_reports_exit(pidfd)
            or process_starttime(peer["pid"]) != peer["pid_starttime"]
            or peer["uid"] != os.getuid()
        ):
            raise BrokerProtocolError(
                "PIDFD_IDENTITY_DRIFT",
                "bound arm grant pidfd differs from its live peer",
            )
        grant = build_session_grant(
            credential=cast(str, payload["credential"]),
            expected_peer=peer,
            role=cast(str, role),
            arm_slot=cast(str, payload["arm_slot"]),
            selection_identity=cast(
                Mapping[str, object],
                payload["selection_identity"],
            ),
            allocation_identity=cast(
                Mapping[str, object],
                payload["allocation_identity"],
            ),
        )
        with self._lock:
            if (
                self._selection_identity is None
                or grant.selection_identity != self._selection_identity
                or self._allocations.get(cast(str, grant.arm_slot))
                != grant.allocation_identity
            ):
                raise BrokerProtocolError(
                    "GRANT_BINDING_DRIFT",
                    "arm grant does not bind the current selection and allocation",
                )
            if grant.credential_sha256 in self._grants:
                raise BrokerProtocolError(
                    "GRANT_ALREADY_REGISTERED",
                    "arm credential hash is already registered",
                )
            self._grants[grant.credential_sha256] = grant
            return grant.as_record()

    def register_bound_nonarm_grant(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
    ) -> dict[str, object]:
        """Register one live later actor without pre-knowing it at bootstrap."""

        _exact_keys(
            payload,
            {"credential", "expected_peer", "role"},
            label="register bound non-arm grant",
        )
        role = payload["role"]
        if role not in {
            "formal-closeout-owner",
            "formal-launch-owner",
            "formal-supervisor",
            "formal-worker",
        }:
            raise BrokerProtocolError(
                "GRANT_SCOPE_DRIFT",
                "bound non-arm grant role is not permitted",
            )
        peer = _peer_grant_identity(
            payload["expected_peer"],
            label="bound non-arm grant",
        )
        if (
            _pidfd_target_pid(pidfd) != peer["pid"]
            or pidfd_reports_exit(pidfd)
            or process_starttime(peer["pid"]) != peer["pid_starttime"]
            or peer["uid"] != os.getuid()
        ):
            raise BrokerProtocolError(
                "PIDFD_IDENTITY_DRIFT",
                "bound non-arm grant pidfd differs from its live peer",
            )
        grant = build_session_grant(
            credential=cast(str, payload["credential"]),
            expected_peer=peer,
            role=cast(str, role),
        )
        with self._lock:
            if (
                grant.credential_sha256 in self._grants
                or grant.credential_sha256
                in self._manager_openfile_grants
            ):
                raise BrokerProtocolError(
                    "GRANT_ALREADY_REGISTERED",
                    "bound non-arm credential is already registered",
                )
            self._grants[grant.credential_sha256] = grant
        return grant.as_record()

    def preregister_manager_openfile_grant(
        self,
        payload: Mapping[str, object],
        *,
        owner_grant: BrokerSessionGrant,
    ) -> dict[str, object]:
        _exact_keys(
            payload,
            {
                "attempt_consumption_identity",
                "credential",
                "manager_epoch_identity",
                "selection_path",
                "unit_name",
            },
            label="preregister manager OpenFile grant",
        )
        token = _nonce(payload["credential"])
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        selection_path = payload["selection_path"]
        if (
            not isinstance(selection_path, str)
            or not Path(selection_path).is_absolute()
        ):
            raise BrokerProtocolError(
                "GRANT_BINDING_DRIFT",
                "manager OpenFile selection path is invalid",
            )
        attempt = _detached_identity(
            payload["attempt_consumption_identity"],
            label="manager OpenFile attempt consumption",
        )
        manager_epoch = _content_identity(
            payload["manager_epoch_identity"],
            label="manager OpenFile epoch",
        )
        unit_name = payload["unit_name"]
        if (
            not isinstance(unit_name, str)
            or not unit_name.endswith(".service")
            or "/" in unit_name
            or len(unit_name) > 255
        ):
            raise BrokerProtocolError(
                "UNIT_IDENTITY_DRIFT",
                "manager OpenFile unit name is invalid",
            )
        if owner_grant.role not in {"formal-launch-owner", "supervisor"}:
            raise BrokerProtocolError(
                "GRANT_SCOPE_DRIFT",
                "manager OpenFile preregistration owner role is invalid",
            )
        with self._grant_changed:
            if (
                digest in self._manager_openfile_grants
                or digest in self._grants
            ):
                raise BrokerProtocolError(
                    "GRANT_ALREADY_REGISTERED",
                    "manager OpenFile credential is already registered",
                )
            grant = _ManagerOpenFileGrant(
                credential_sha256=digest,
                manager_epoch_identity=manager_epoch,
                selection_path=selection_path,
                attempt_consumption_identity=attempt,
                unit_name=unit_name,
                owner_credential_sha256=(
                    owner_grant.credential_sha256
                ),
                owner_peer=dict(owner_grant.expected_peer),
            )
            self._manager_openfile_grants[digest] = grant
            return {
                "schema_version": MANAGER_OPENFILE_GRANT_SCHEMA,
                "attempt_consumption_identity": attempt,
                "credential_sha256": digest,
                "manager_epoch_identity": manager_epoch,
                "owner_credential_sha256": (
                    owner_grant.credential_sha256
                ),
                "owner_peer": dict(owner_grant.expected_peer),
                "selection_path": selection_path,
                "state": "UNBOUND",
                "unit_name": unit_name,
            }

    def bind_manager_openfile_selection(
        self,
        payload: Mapping[str, object],
        *,
        owner_grant: BrokerSessionGrant,
    ) -> dict[str, object]:
        """Bind the exact prepared selection before its no-replace commit.

        This is deliberately distinct from the later systemd MainPID binding:
        the formal-launch owner first prepares canonical bytes, binds their
        identity to the already-preregistered one-use credential, and only
        then may publish those unchanged bytes.  No selection byte contains
        this out-of-band receipt, avoiding a self-reference.
        """

        _exact_keys(
            payload,
            {"credential", "selection_identity"},
            label="bind manager OpenFile prepared selection",
        )
        token = _nonce(payload["credential"])
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        selection = _detached_identity(
            payload["selection_identity"],
            label="prepared formal selection",
        )
        if owner_grant.role not in {"formal-launch-owner", "supervisor"}:
            raise BrokerProtocolError(
                "GRANT_SCOPE_DRIFT",
                "prepared selection binding owner role is invalid",
            )
        with self._grant_changed:
            try:
                grant = self._manager_openfile_grants[digest]
            except KeyError as exc:
                raise BrokerProtocolError(
                    "CREDENTIAL_ALREADY_CONSUMED_OR_UNKNOWN",
                    "manager OpenFile credential is absent",
                ) from exc
            if (
                grant.grant_kind != "formal-supervisor"
                or grant.application_peer is not None
                or grant.preregistered_selection_identity is not None
                or selection["path"] != grant.selection_path
                or grant.owner_credential_sha256
                != owner_grant.credential_sha256
                or grant.owner_peer != owner_grant.expected_peer
            ):
                raise BrokerProtocolError(
                    "GRANT_BINDING_DRIFT",
                    "prepared selection binding differs from its owner or grant",
                )
            grant.preregistered_selection_identity = selection
            return {
                "schema_version": (
                    MANAGER_OPENFILE_SELECTION_BINDING_SCHEMA
                ),
                "credential_sha256": digest,
                "manager_epoch_identity": dict(
                    grant.manager_epoch_identity
                ),
                "owner_credential_sha256": (
                    owner_grant.credential_sha256
                ),
                "owner_peer": dict(owner_grant.expected_peer),
                "selection_identity": dict(selection),
                "state": "PREPARED_SELECTION_BOUND",
                "unit_name": grant.unit_name,
            }

    def preregister_manager_openfile_arm_grant(
        self,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        """Preregister one manager-mediated organic-supervisor FD8 grant."""

        _exact_keys(
            payload,
            {
                "allocation_identity",
                "arm_slot",
                "attempt_consumption_identity",
                "credential",
                "manager_epoch_identity",
                "selection_identity",
                "unit_name",
            },
            label="preregister manager OpenFile arm grant",
        )
        token = _nonce(payload["credential"])
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        slot = budget._safe_component(  # noqa: SLF001
            payload["arm_slot"],
            label="arm_slot",
        )
        allocation = _content_identity(
            payload["allocation_identity"],
            label="manager OpenFile arm allocation",
        )
        selection = _detached_identity(
            payload["selection_identity"],
            label="manager OpenFile arm selection",
        )
        attempt = _detached_identity(
            payload["attempt_consumption_identity"],
            label="manager OpenFile arm attempt consumption",
        )
        manager_epoch = _content_identity(
            payload["manager_epoch_identity"],
            label="manager OpenFile arm epoch",
        )
        unit_name = payload["unit_name"]
        if (
            not isinstance(unit_name, str)
            or not unit_name.endswith(".service")
            or "/" in unit_name
            or len(unit_name) > 255
        ):
            raise BrokerProtocolError(
                "UNIT_IDENTITY_DRIFT",
                "manager OpenFile arm unit name is invalid",
            )
        with self._grant_changed:
            if (
                self._selection_identity != selection
                or self._allocations.get(slot) != allocation
            ):
                raise BrokerProtocolError(
                    "GRANT_BINDING_DRIFT",
                    "manager OpenFile arm grant differs from current selection/allocation",
                )
            if (
                digest in self._manager_openfile_grants
                or digest in self._grants
            ):
                raise BrokerProtocolError(
                    "GRANT_ALREADY_REGISTERED",
                    "manager OpenFile arm credential is already registered",
                )
            self._manager_openfile_grants[digest] = _ManagerOpenFileGrant(
                credential_sha256=digest,
                manager_epoch_identity=manager_epoch,
                selection_path=cast(str, selection["path"]),
                attempt_consumption_identity=attempt,
                unit_name=unit_name,
                grant_kind="arm-supervisor",
                arm_slot=slot,
                allocation_identity=allocation,
                preregistered_selection_identity=selection,
            )
        return {
            "schema_version": MANAGER_OPENFILE_ARM_GRANT_SCHEMA,
            "allocation_identity": allocation,
            "arm_slot": slot,
            "attempt_consumption_identity": attempt,
            "credential_sha256": digest,
            "manager_epoch_identity": manager_epoch,
            "selection_identity": selection,
            "state": "UNBOUND",
            "unit_name": unit_name,
        }

    def bind_manager_openfile_grant(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
        owner_grant: BrokerSessionGrant,
    ) -> dict[str, object]:
        _exact_keys(
            payload,
            {
                "application_peer",
                "attempt_consumption_identity",
                "credential",
                "guardian_ready_identity",
                "pidfd_method",
                "selection_identity",
            },
            label="bind manager OpenFile grant",
        )
        token = _nonce(payload["credential"])
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        application_peer = _peer_grant_identity(
            payload["application_peer"],
            label="manager OpenFile application",
        )
        guardian_ready = _detached_identity(
            payload["guardian_ready_identity"],
            label="manager OpenFile guardian-ready",
        )
        attempt = _detached_identity(
            payload["attempt_consumption_identity"],
            label="manager OpenFile attempt consumption",
        )
        selection = _detached_identity(
            payload["selection_identity"],
            label="manager OpenFile selection",
        )
        pidfd_method = payload["pidfd_method"]
        if (
            not isinstance(pidfd_method, str)
            or not pidfd_method
            or _pidfd_target_pid(pidfd) != application_peer["pid"]
            or pidfd_reports_exit(pidfd)
            or process_starttime(application_peer["pid"])
            != application_peer["pid_starttime"]
            or application_peer["uid"] != os.getuid()
        ):
            raise BrokerProtocolError(
                "PIDFD_IDENTITY_DRIFT",
                "manager OpenFile application pidfd differs",
            )
        if owner_grant.role not in {"formal-launch-owner", "supervisor"}:
            raise BrokerProtocolError(
                "GRANT_SCOPE_DRIFT",
                "manager OpenFile binding owner role is invalid",
            )
        with self._grant_changed:
            try:
                grant = self._manager_openfile_grants[digest]
            except KeyError as exc:
                raise BrokerProtocolError(
                    "CREDENTIAL_ALREADY_CONSUMED_OR_UNKNOWN",
                    "manager OpenFile credential is absent",
                ) from exc
            if (
                grant.application_peer is not None
                or attempt != grant.attempt_consumption_identity
                or grant.preregistered_selection_identity is None
                or selection
                != grant.preregistered_selection_identity
                or grant.owner_credential_sha256
                != owner_grant.credential_sha256
                or grant.owner_peer
                != owner_grant.expected_peer
            ):
                raise BrokerProtocolError(
                    "GRANT_BINDING_DRIFT",
                    "manager OpenFile grant is already bound or attempt drifted",
                )
            grant.application_peer = application_peer
            grant.selection_identity = selection
            grant.guardian_ready_identity = guardian_ready
            grant.pidfd = pidfd
            grant.pidfd_method = pidfd_method
            self._grant_changed.notify_all()
            return {
                "schema_version": MANAGER_OPENFILE_GRANT_SCHEMA,
                "application_peer": application_peer,
                "attempt_consumption_identity": attempt,
                "credential_sha256": digest,
                "guardian_ready_identity": guardian_ready,
                "manager_epoch_identity": grant.manager_epoch_identity,
                "pidfd_method": pidfd_method,
                "selection_identity": selection,
                "state": "BOUND",
                "unit_name": grant.unit_name,
            }

    def bind_manager_openfile_arm_grant(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
    ) -> dict[str, object]:
        _exact_keys(
            payload,
            {
                "allocation_identity",
                "application_peer",
                "arm_slot",
                "attempt_consumption_identity",
                "credential",
                "guardian_ready_identity",
                "pidfd_method",
                "selection_identity",
            },
            label="bind manager OpenFile arm grant",
        )
        token = _nonce(payload["credential"])
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        application_peer = _peer_grant_identity(
            payload["application_peer"],
            label="manager OpenFile arm application",
        )
        guardian_ready = _detached_identity(
            payload["guardian_ready_identity"],
            label="manager OpenFile arm guardian-ready",
        )
        attempt = _detached_identity(
            payload["attempt_consumption_identity"],
            label="manager OpenFile arm attempt consumption",
        )
        selection = _detached_identity(
            payload["selection_identity"],
            label="manager OpenFile arm selection",
        )
        allocation = _content_identity(
            payload["allocation_identity"],
            label="manager OpenFile arm allocation",
        )
        slot = budget._safe_component(  # noqa: SLF001
            payload["arm_slot"],
            label="arm_slot",
        )
        pidfd_method = payload["pidfd_method"]
        if (
            not isinstance(pidfd_method, str)
            or not pidfd_method
            or _pidfd_target_pid(pidfd) != application_peer["pid"]
            or pidfd_reports_exit(pidfd)
            or process_starttime(application_peer["pid"])
            != application_peer["pid_starttime"]
            or application_peer["uid"] != os.getuid()
        ):
            raise BrokerProtocolError(
                "PIDFD_IDENTITY_DRIFT",
                "manager OpenFile arm application pidfd differs",
            )
        with self._grant_changed:
            try:
                grant = self._manager_openfile_grants[digest]
            except KeyError as exc:
                raise BrokerProtocolError(
                    "CREDENTIAL_ALREADY_CONSUMED_OR_UNKNOWN",
                    "manager OpenFile arm credential is absent",
                ) from exc
            if (
                grant.grant_kind != "arm-supervisor"
                or grant.application_peer is not None
                or grant.arm_slot != slot
                or grant.allocation_identity != allocation
                or grant.preregistered_selection_identity != selection
                or attempt != grant.attempt_consumption_identity
            ):
                raise BrokerProtocolError(
                    "GRANT_BINDING_DRIFT",
                    "manager OpenFile arm grant is already bound or identity drifted",
                )
            grant.application_peer = application_peer
            grant.selection_identity = selection
            grant.guardian_ready_identity = guardian_ready
            grant.pidfd = pidfd
            grant.pidfd_method = pidfd_method
            self._grant_changed.notify_all()
            return {
                "schema_version": MANAGER_OPENFILE_ARM_GRANT_SCHEMA,
                "allocation_identity": allocation,
                "application_peer": application_peer,
                "arm_slot": slot,
                "attempt_consumption_identity": attempt,
                "credential_sha256": digest,
                "guardian_ready_identity": guardian_ready,
                "manager_epoch_identity": grant.manager_epoch_identity,
                "pidfd_method": pidfd_method,
                "selection_identity": selection,
                "state": "BOUND",
                "unit_name": grant.unit_name,
            }

    def authenticate_manager_openfile(
        self,
        frame: ReceivedFrame,
    ) -> tuple[BrokerSessionGrant, dict[str, object]]:
        record = frame.record
        _exact_keys(
            record,
            {
                "application_peer",
                "attempt_consumption_identity",
                "credential",
                "manager_epoch_identity",
                "nonce",
                "schema_version",
                "selection_identity",
                "unit_name",
            },
            label="manager OpenFile authentication",
        )
        if (
            record["schema_version"]
            != MANAGER_OPENFILE_AUTHENTICATION_SCHEMA
            or _nonce(record["nonce"]) != self.nonce
        ):
            raise BrokerProtocolError(
                "AUTHENTICATION_IDENTITY_DRIFT",
                "manager OpenFile authentication schema or nonce drifted",
            )
        token = _nonce(record["credential"])
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        application_peer = _peer_grant_identity(
            record["application_peer"],
            label="manager OpenFile application",
        )
        selection = _detached_identity(
            record["selection_identity"],
            label="manager OpenFile selection",
        )
        attempt = _detached_identity(
            record["attempt_consumption_identity"],
            label="manager OpenFile attempt consumption",
        )
        manager_epoch = _content_identity(
            record["manager_epoch_identity"],
            label="manager OpenFile epoch",
        )
        with self._grant_changed:
            grant = self._manager_openfile_grants.get(digest)
            if grant is None:
                raise BrokerProtocolError(
                    "CREDENTIAL_ALREADY_CONSUMED_OR_UNKNOWN",
                    "manager OpenFile credential is absent",
                )
            if grant.application_peer is None:
                if not self._grant_changed.wait_for(
                    lambda: grant.application_peer is not None
                    or self.exit_requested.is_set(),
                    timeout=120.0,
                ):
                    self._manager_openfile_grants.pop(digest, None)
                    raise BrokerProtocolError(
                        "OPENFILE_GRANT_BIND_TIMEOUT",
                        "manager OpenFile grant was never bound",
                    )
            self._manager_openfile_grants.pop(digest, None)
            if (
                grant.application_peer is None
                or grant.guardian_ready_identity is None
                or grant.selection_identity is None
                or grant.pidfd is None
                or grant.pidfd_method is None
                or application_peer != grant.application_peer
                or selection != grant.selection_identity
                or attempt != grant.attempt_consumption_identity
                or manager_epoch != grant.manager_epoch_identity
                or record["unit_name"] != grant.unit_name
                or frame.peer["uid"] != application_peer["uid"]
                or pidfd_reports_exit(grant.pidfd)
                or process_starttime(application_peer["pid"])
                != application_peer["pid_starttime"]
            ):
                if grant.pidfd is not None:
                    os.close(grant.pidfd)
                    grant.pidfd = None
                raise BrokerProtocolError(
                    "GRANT_BINDING_DRIFT",
                    "manager OpenFile authentication differs from bound grant",
                )
            os.close(grant.pidfd)
            grant.pidfd = None
            connector = {
                key: frame.peer[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            session = BrokerSessionGrant(
                role="supervisor",
                credential_sha256=digest,
                expected_peer=connector,
                arm_slot=None,
                selection_identity=None,
                allocation_identity=None,
            )
            self._active_roles[frame.peer["pid"]] = "supervisor"
            ready: dict[str, object] = {
                "schema_version": MANAGER_OPENFILE_GRANT_SCHEMA,
                "application_peer": application_peer,
                "attempt_consumption_identity": attempt,
                "connector_peer": connector,
                "credential_sha256": digest,
                "guardian_ready_identity": grant.guardian_ready_identity,
                "manager_epoch_identity": manager_epoch,
                "pidfd_method": grant.pidfd_method,
                "selection_identity": selection,
                "state": "AUTHENTICATED",
                "unit_name": grant.unit_name,
            }
            return session, ready

    def authenticate_manager_openfile_arm(
        self,
        frame: ReceivedFrame,
    ) -> tuple[BrokerSessionGrant, dict[str, object]]:
        """Consume one bound manager-mediated arm-supervisor credential."""

        record = frame.record
        _exact_keys(
            record,
            {
                "allocation_identity",
                "application_peer",
                "arm_slot",
                "attempt_consumption_identity",
                "credential",
                "manager_epoch_identity",
                "nonce",
                "schema_version",
                "selection_identity",
                "unit_name",
            },
            label="manager OpenFile arm authentication",
        )
        if (
            record["schema_version"]
            != MANAGER_OPENFILE_ARM_AUTHENTICATION_SCHEMA
            or _nonce(record["nonce"]) != self.nonce
        ):
            raise BrokerProtocolError(
                "AUTHENTICATION_IDENTITY_DRIFT",
                "manager OpenFile arm authentication schema or nonce drifted",
            )
        token = _nonce(record["credential"])
        digest = hashlib.sha256(token.encode("ascii")).hexdigest()
        application_peer = _peer_grant_identity(
            record["application_peer"],
            label="manager OpenFile arm application",
        )
        selection = _detached_identity(
            record["selection_identity"],
            label="manager OpenFile arm selection",
        )
        allocation = _content_identity(
            record["allocation_identity"],
            label="manager OpenFile arm allocation",
        )
        attempt = _detached_identity(
            record["attempt_consumption_identity"],
            label="manager OpenFile arm attempt consumption",
        )
        manager_epoch = _content_identity(
            record["manager_epoch_identity"],
            label="manager OpenFile arm epoch",
        )
        slot = budget._safe_component(  # noqa: SLF001
            record["arm_slot"],
            label="arm_slot",
        )
        with self._grant_changed:
            grant = self._manager_openfile_grants.get(digest)
            if grant is None:
                raise BrokerProtocolError(
                    "CREDENTIAL_ALREADY_CONSUMED_OR_UNKNOWN",
                    "manager OpenFile arm credential is absent",
                )
            if grant.application_peer is None:
                if not self._grant_changed.wait_for(
                    lambda: grant.application_peer is not None
                    or self.exit_requested.is_set(),
                    timeout=120.0,
                ):
                    self._manager_openfile_grants.pop(digest, None)
                    raise BrokerProtocolError(
                        "OPENFILE_GRANT_BIND_TIMEOUT",
                        "manager OpenFile arm grant was never bound",
                    )
            self._manager_openfile_grants.pop(digest, None)
            if (
                grant.grant_kind != "arm-supervisor"
                or grant.application_peer is None
                or grant.guardian_ready_identity is None
                or grant.selection_identity is None
                or grant.allocation_identity is None
                or grant.arm_slot is None
                or grant.pidfd is None
                or grant.pidfd_method is None
                or application_peer != grant.application_peer
                or selection != grant.selection_identity
                or selection != grant.preregistered_selection_identity
                or allocation != grant.allocation_identity
                or slot != grant.arm_slot
                or attempt != grant.attempt_consumption_identity
                or manager_epoch != grant.manager_epoch_identity
                or record["unit_name"] != grant.unit_name
                or frame.peer["uid"] != application_peer["uid"]
                or pidfd_reports_exit(grant.pidfd)
                or process_starttime(application_peer["pid"])
                != application_peer["pid_starttime"]
            ):
                if grant.pidfd is not None:
                    os.close(grant.pidfd)
                    grant.pidfd = None
                raise BrokerProtocolError(
                    "GRANT_BINDING_DRIFT",
                    "manager OpenFile arm authentication differs from bound grant",
                )
            os.close(grant.pidfd)
            grant.pidfd = None
            connector = {
                key: frame.peer[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            session = BrokerSessionGrant(
                role="arm-supervisor",
                credential_sha256=digest,
                expected_peer=connector,
                arm_slot=slot,
                selection_identity=selection,
                allocation_identity=allocation,
            )
            self._active_roles[frame.peer["pid"]] = "arm-supervisor"
            ready: dict[str, object] = {
                "schema_version": MANAGER_OPENFILE_ARM_GRANT_SCHEMA,
                "allocation_identity": allocation,
                "application_peer": application_peer,
                "arm_slot": slot,
                "attempt_consumption_identity": attempt,
                "connector_peer": connector,
                "credential_sha256": digest,
                "guardian_ready_identity": grant.guardian_ready_identity,
                "manager_epoch_identity": manager_epoch,
                "pidfd_method": grant.pidfd_method,
                "selection_identity": selection,
                "state": "AUTHENTICATED",
                "unit_name": grant.unit_name,
            }
            return session, ready

    def request_exit(self) -> None:
        with self._lock:
            if self._pending_arm_response is not None:
                raise BrokerProtocolError(
                    "PRIOR_RESPONSE_UNACKNOWLEDGED",
                    "formal broker cannot exit before the last arm response is durably accepted",
                )
            if (
                self._bootstrap_admin_required
                and self._bootstrap_handoff_state != "PUBLISHED"
            ):
                raise BrokerProtocolError(
                    "BOOTSTRAP_HANDOFF_MISSING",
                    "formal broker cannot exit without its committed bootstrap handoff",
                )
            active_arms = [
                pid
                for pid, role in self._active_roles.items()
                if role == "arm"
            ]
            if active_arms:
                raise BrokerProtocolError(
                    "ACTIVE_ARM_SESSION",
                    "broker cannot exit with an active arm session",
                )
            if (
                self._recovery_pid is not None
                or self._recovery_process is not None
                or self._recovery_operation_in_progress
            ):
                raise BrokerProtocolError(
                    "RECOVERY_ACTOR_NOT_DISARMED",
                    "broker cannot exit before mediated recovery disarm and exit proof",
                )
            if self._recovery_terminal is None:
                raise BrokerProtocolError(
                    "RECOVERY_TERMINAL_MISSING",
                    "broker cannot exit before recording recovery terminal evidence",
                )
            if self._closure_handoff is None:
                raise BrokerProtocolError(
                    "CLOSURE_CONTROL_NOT_TRANSFERRED",
                    "broker cannot exit before transferring dormant closure control",
                )
            if (
                self._release_terminal is None
                or self._release_operation_in_progress
                or self._release_parent_fd is not None
                or self._release_extents
            ):
                raise BrokerProtocolError(
                    "RELEASE_TERMINAL_MISSING",
                    "broker cannot exit before the selected release terminal and unused reserve seal",
                )
            self.exit_requested.set()

    def register_recovery_actor(
        self,
        process: Any,
        *,
        handoff: Mapping[str, object],
        lock_extent: Mapping[str, object],
    ) -> dict[str, object]:
        with self._lock:
            if (
                self._recovery_pid is not None
                or self._recovery_process is not None
                or self._recovery_handoff is not None
            ):
                raise BrokerProtocolError(
                    "RECOVERY_ACTOR_ALREADY_REGISTERED",
                    "persistent broker cannot register recovery twice",
                )
            actor = handoff.get("actor")
            if (
                type(actor) is not dict
                or process.pid != actor.get("pid")
                or process.actor != actor
                or process.pidfd < 0
                or process.connection.fileno() < 0
                or pidfd_reports_exit(process.pidfd)
            ):
                raise BrokerProtocolError(
                    "RECOVERY_ACTOR_IDENTITY_DRIFT",
                    "persistent recovery owner differs from its live process handles",
                )
            self._recovery_pid = process.pid
            self._recovery_process = process
            self._recovery_handoff = dict(handoff)
            self._recovery_lock_extent = dict(lock_extent)
            return {
                **dict(handoff),
                "control_owner": "persistent-budget-broker",
                "state": "BROKER_RETAINED_CONTROL",
            }

    def disarm_recovery(
        self,
        payload: Mapping[str, object],
    ) -> tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ]:
        _exact_keys(
            payload,
            {"disarm_intent_sha256"},
            label="mediated recovery disarm",
        )
        with self._lock:
            if (
                self._recovery_disarm_intent is None
                or payload["disarm_intent_sha256"]
                != _message_identity(
                    self._recovery_disarm_intent
                )["sha256"]
                or self._recovery_process is None
                or self._recovery_handoff is None
                or self._recovery_lock_extent is None
                or self._recovery_operation_in_progress
                or self._recovery_terminal is not None
            ):
                raise BrokerProtocolError(
                    "RECOVERY_DISARM_STATE_INVALID",
                    "persistent recovery is absent, terminal, or already in transition",
                )
            process = self._recovery_process
            handoff = dict(self._recovery_handoff)
            lock_extent = dict(self._recovery_lock_extent)
            self._recovery_operation_in_progress = True
        try:
            terminal_result = process.terminal(
                "DISARM",
                dict(payload),
            )
            exit_code = process.wait()
            if exit_code != 0 or not pidfd_reports_exit(process.pidfd):
                raise BrokerProtocolError(
                    "RECOVERY_ACTOR_EXIT_DRIFT",
                    "mediated recovery did not reach exact terminal exit",
                )
            process.close()
        except BaseException:
            # The recovery control protocol crossed its sole disarm attempt.
            # A lost PREPARED response or uncertain ACK must never become a
            # retry: keep the transition latched until the broker is killed,
            # at which point the still-armed recovery actor publishes the
            # strict-once consumed-incomplete closeout.
            raise
        terminal = {
            "actor": dict(
                cast(Mapping[str, object], handoff["actor"])
            ),
            "exit_code": 0,
            "pidfd_exit_proved": True,
            "state": "DISARMED_AND_EXIT_PROVED",
            "terminal_result": dict(terminal_result),
        }
        with self._lock:
            self._recovery_pid = None
            self._recovery_process = None
            self._recovery_operation_in_progress = False
            self._recovery_terminal = dict(terminal)
        return terminal, lock_extent, handoff

    def register_recovery_disarm_intent(
        self,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        _exact_keys(
            payload,
            {"terminal_join_sha256"},
            label="recovery disarm intent",
        )
        terminal_join = _sha256(
            payload["terminal_join_sha256"],
            label="terminal_join_sha256",
        )
        with self._lock:
            if (
                self._recovery_disarm_intent is not None
                or self._recovery_process is None
                or self._recovery_handoff is None
                or self._recovery_terminal is not None
                or self._recovery_operation_in_progress
            ):
                raise BrokerProtocolError(
                    "RECOVERY_DISARM_INTENT_STATE_INVALID",
                    "recovery disarm intent is duplicate or lacks a live recovery owner",
                )
            intent: dict[str, object] = {
                "broker_actor": dict(self.actor),
                "recovery_actor": dict(
                    cast(
                        Mapping[str, object],
                        self._recovery_handoff["actor"],
                    )
                ),
                "schema_version": RECOVERY_DISARM_INTENT_SCHEMA,
                "state": "RECOVERY_DISARM_INTENT_PUBLISHED",
                "terminal_join_sha256": terminal_join,
            }
            self._recovery_disarm_intent = dict(intent)
            return intent

    def abort_recovery(
        self,
        *,
        reason_sha256: str,
    ) -> tuple[
        dict[str, object],
        dict[str, object] | None,
        dict[str, object] | None,
    ]:
        with self._lock:
            absent = (
                self._recovery_process is None
                and self._recovery_handoff is None
                and self._recovery_lock_extent is None
            )
        if absent:
            return (
                {
                    "state": "RECOVERY_NOT_STARTED_BEFORE_BOOTSTRAP_ABORT",
                },
                None,
                None,
            )
        disarm_intent = self.register_recovery_disarm_intent(
            {"terminal_join_sha256": reason_sha256}
        )
        return self.disarm_recovery(
            {
                "disarm_intent_sha256": _message_identity(
                    disarm_intent
                )["sha256"]
            }
        )

    def recovery_closure_inputs(
        self,
    ) -> tuple[dict[str, object], int, dict[str, object]]:
        with self._lock:
            process = self._recovery_process
            if (
                process is None
                or self._recovery_handoff is None
                or self._recovery_lock_extent is None
                or self._recovery_terminal is not None
                or self._recovery_operation_in_progress
            ):
                raise BrokerProtocolError(
                    "RECOVERY_CLOSURE_BINDING_UNAVAILABLE",
                    "dormant closure must bind the still-live recovery actor",
                )
            return (
                dict(process.actor),
                process.pidfd,
                dict(self._recovery_lock_extent),
            )

    def register_closure_transfer(
        self,
        *,
        handoff: Mapping[str, object],
        release_parent_fd: int | None = None,
        release_extents: Mapping[
            str,
            tuple[Mapping[str, object], int],
        ] | None = None,
        final_release_handoff: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        expected_purposes = {
            "failure-terminal-release",
            "formal-root-replay-alternate-receipt",
            "formal-root-replay-primary-receipt",
            "success-dual-lock-release",
        }
        legacy_purposes = {
            "failure-terminal-release",
            "success-dual-lock-release",
        }
        with self._lock:
            if (
                self._closure_handoff is not None
                or self._release_parent_fd is not None
                or self._release_extents
                or self._release_terminal is not None
            ):
                raise BrokerProtocolError(
                    "CLOSURE_ALREADY_PREPARED",
                    "persistent closure control cannot be prepared twice",
                )
            if final_release_handoff is not None:
                final_release_identity = _message_identity(
                    final_release_handoff
                )
                if (
                    release_parent_fd is not None
                    or (
                        release_extents is not None
                        and bool(release_extents)
                    )
                    or type(final_release_handoff) is not dict
                    or not final_release_handoff
                    or handoff.get("final_release_actor")
                    != final_release_handoff.get("actor")
                    or handoff.get(
                        "final_release_handoff_identity"
                    )
                    != final_release_identity
                    or handoff.get("final_release_pidfd_method")
                    != final_release_handoff.get("pidfd_method")
                ):
                    raise BrokerProtocolError(
                        "RELEASE_EXTENT_SET_DRIFT",
                        "detached final-release control mixed raw release FDs",
                    )
                self._closure_handoff = dict(handoff)
                self._release_terminal = {
                    "final_release_handoff_identity": (
                        final_release_identity
                    ),
                    "state": "FINAL_RELEASE_CONTROL_TRANSFERRED",
                }
                return {
                    "closure_handoff_identity": _message_identity(handoff),
                    "final_release_handoff_identity": _message_identity(
                        final_release_handoff
                    ),
                    "release_purposes": sorted(expected_purposes),
                    "state": (
                        "CLOSURE_AND_FINAL_RELEASE_CONTROL_TRANSFERRED"
                    ),
                }
            if (
                release_parent_fd is None
                or release_extents is None
                or set(release_extents) != legacy_purposes
            ):
                raise BrokerProtocolError(
                    "RELEASE_EXTENT_SET_DRIFT",
                    "release terminal extent set differs",
                )
            parent_identity = _parent_identity(release_parent_fd)
            checked: dict[
                str,
                tuple[dict[str, object], int],
            ] = {}
            for purpose, (raw_extent, descriptor) in (
                release_extents.items()
            ):
                extent = validate_prepared_extent(raw_extent)
                if (
                    extent["parent_identity"] != parent_identity
                    or _identity(descriptor)
                    != extent["staging_identity"]
                ):
                    raise BrokerProtocolError(
                        "RELEASE_EXTENT_IDENTITY_DRIFT",
                        f"{purpose} release extent differs",
                    )
                checked[purpose] = (dict(extent), descriptor)
            self._closure_handoff = dict(handoff)
            self._release_parent_fd = release_parent_fd
            self._release_extents = checked
            return {
                "closure_handoff_identity": _message_identity(handoff),
                "release_purposes": sorted(legacy_purposes),
                "state": "CLOSURE_CONTROL_TRANSFERRED_RELEASE_PENDING",
            }

    def publish_release_terminal(
        self,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        _exact_keys(
            payload,
            {"purpose", "record"},
            label="release terminal publication",
        )
        purpose = payload["purpose"]
        record = payload["record"]
        if (
            purpose
            not in {
                "failure-terminal-release",
                "success-dual-lock-release",
            }
            or type(record) is not dict
        ):
            raise BrokerProtocolError(
                "RELEASE_TERMINAL_SHAPE_DRIFT",
                "release terminal purpose or record differs",
            )
        with self._lock:
            if (
                self._closure_handoff is None
                or self._release_parent_fd is None
                or set(self._release_extents)
                != {
                    "failure-terminal-release",
                    "success-dual-lock-release",
                }
                or self._release_terminal is not None
                or self._release_operation_in_progress
            ):
                raise BrokerProtocolError(
                    "RELEASE_TERMINAL_STATE_INVALID",
                    "release terminal publication is absent, duplicate, or uncertain",
                )
            self._release_operation_in_progress = True
            parent_fd = self._release_parent_fd
            extents = dict(self._release_extents)
            self._release_parent_fd = None
            self._release_extents.clear()
        selected_extent, selected_fd = extents[purpose]
        unused_purpose = (
            "failure-terminal-release"
            if purpose == "success-dual-lock-release"
            else "success-dual-lock-release"
        )
        unused_extent, unused_fd = extents[unused_purpose]
        terminal: dict[str, object] | None = None
        primary: BaseException | None = None
        try:
            selected_identity = publish_preallocated_extent(
                selected_extent,
                parent_fd=parent_fd,
                staging_fd=selected_fd,
                raw=canonical_json_bytes(record),
            )
            os.fchmod(unused_fd, 0o444)
            os.fsync(unused_fd)
            os.fsync(parent_fd)
            unused_identity = _identity(unused_fd)
            unused_staging_identity = cast(
                Mapping[str, object],
                unused_extent["staging_identity"],
            )
            if (
                unused_identity["device"]
                != unused_staging_identity["device"]
                or unused_identity["inode"]
                != unused_staging_identity["inode"]
                or unused_identity["mode_octal"] != "0444"
            ):
                raise BrokerProtocolError(
                    "UNUSED_RELEASE_SEAL_DRIFT",
                    "unused release staging extent was not sealed in place",
                )
            terminal = {
                "selected_identity": selected_identity,
                "selected_purpose": purpose,
                "state": "RELEASE_TERMINAL_PUBLISHED_UNUSED_SEALED",
                "unused_purpose": unused_purpose,
                "unused_staging_identity": unused_identity,
            }
        except BaseException as exc:
            primary = exc
            raise
        finally:
            close_primary: BaseException | None = None
            for descriptor in (
                selected_fd,
                unused_fd,
                parent_fd,
            ):
                try:
                    os.close(descriptor)
                except BaseException as exc:
                    if close_primary is None:
                        close_primary = exc
                    else:
                        close_primary.add_note(
                            "release terminal close also failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
            with self._lock:
                self._release_operation_in_progress = False
                if (
                    primary is None
                    and close_primary is None
                    and terminal is not None
                ):
                    self._release_terminal = dict(terminal)
            if close_primary is not None:
                if primary is None:
                    raise close_primary
                primary.add_note(
                    "release terminal descriptor cleanup failed: "
                    f"{type(close_primary).__name__}: {close_primary}"
                )
        assert terminal is not None
        return terminal

    def abandon_recovery_handle(self) -> None:
        with self._lock:
            process = self._recovery_process
            self._recovery_process = None
            self._recovery_pid = None
            self._recovery_operation_in_progress = False
        if process is not None:
            process.close()

    def abandon_release_handles(self) -> None:
        with self._lock:
            parent_fd = self._release_parent_fd
            extents = dict(self._release_extents)
            self._release_parent_fd = None
            self._release_extents.clear()
            self._release_operation_in_progress = False
        closed: set[int] = set()
        for _extent, descriptor in extents.values():
            if descriptor in closed:
                continue
            closed.add(descriptor)
            os.close(descriptor)
        if parent_fd is not None and parent_fd not in closed:
            os.close(parent_fd)


class BrokerServer:
    """One request-serialized persistent owner."""

    def __init__(
        self,
        connection: socket.socket,
        *,
        root: Path | None = None,
        category_limits: Mapping[str, object] | None = None,
        nonce: str,
        expected_peer: Mapping[str, int],
        native_helper: NativeHelperProtocol | None = None,
        formal_directories: Sequence[Mapping[str, object]] = (),
        arm_directories: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
        account: budget.FormalBudgetBroker | None = None,
        actor: Mapping[str, object] | None = None,
        runtime: _SharedBrokerRuntime | None = None,
        session_grant: BrokerSessionGrant | None = None,
        fixed_reservations: (
            dict[str, budget.RetainedStagingReservation] | None
        ) = None,
        final_release_parent_capability: (
            FinalReleaseParentCapability | None
        ) = None,
        package_authorization: (
            PackageRoleAuthorizationProtocol | None
        ) = None,
        manager_ready_record: Mapping[str, object] | None = None,
        close_account_on_exit: bool = True,
    ) -> None:
        self.connection = connection
        self.nonce = _nonce(nonce)
        self.expected_peer = dict(expected_peer)
        self.native_helper = native_helper
        if account is None:
            if root is None or category_limits is None:
                raise BrokerProtocolError(
                    "ACCOUNT_CONFIGURATION_INVALID",
                    "new broker account requires root and category limits",
                )
            self.account = budget.FormalBudgetBroker.create(
                root,
                category_limits=category_limits,
            )
            self._account_was_created = True
        else:
            if root is not None or category_limits is not None:
                raise BrokerProtocolError(
                    "ACCOUNT_CONFIGURATION_INVALID",
                    "transferred broker account cannot be mixed with root creation",
                )
            self.account = account
            self._account_was_created = False
        self.close_account_on_exit = close_account_on_exit
        self.runtime = runtime
        self.session_grant = session_grant
        self._formal_supervisor_phase = (
            "PRESELECTION"
            if session_grant is not None
            and session_grant.role == "formal-supervisor"
            else None
        )
        self.fixed_reservations = fixed_reservations
        self.final_release_parent_capability = (
            final_release_parent_capability
        )
        self.package_authorization = package_authorization
        self.manager_ready_record = (
            None
            if manager_ready_record is None
            else dict(manager_ready_record)
        )
        self.formal_directories = _fixed_directories(
            formal_directories,
            label="formal_directories",
        )
        raw_arm_directories = {} if arm_directories is None else dict(arm_directories)
        self.arm_directories: dict[str, tuple[FixedDirectory, ...]] = {}
        for raw_slot, raw_directories in sorted(raw_arm_directories.items()):
            slot = budget._safe_component(raw_slot, label="arm_slot")  # noqa: SLF001
            directories = _fixed_directories(
                raw_directories,
                label=f"arm_directories[{slot}]",
            )
            self.arm_directories[slot] = directories
        try:
            for directory in self.formal_directories:
                parts = budget._relative_parts(  # noqa: SLF001
                    directory.path,
                    allow_dot=False,
                )
                if self._account_was_created:
                    self.account.register_directory(
                        directory.path,
                        mode=directory.mode,
                    )
                elif (
                    parts not in self.account._registered_directories  # noqa: SLF001
                    or self.account._registered_directory_modes[parts]  # noqa: SLF001
                    != directory.mode
                ):
                    raise BrokerProtocolError(
                        "FIXED_LAYOUT_NOT_PREREGISTERED",
                        "transferred account lacks one fixed formal directory",
                    )
        except BaseException:
            if self.close_account_on_exit:
                self.account.close()
            raise
        self.actor = (
            {
                "schema_version": ACTOR_SCHEMA,
                **process_identity(),
            }
            if actor is None
            else dict(actor)
        )
        self.sequence = 0
        self.journal_sequence = 0
        self.exit_requested = False
        self._session_instance_id = secrets.token_hex(32)
        self._active_arm_seal: dict[str, object] | None = None
        self._session_connection_identity = tuple(
            budget._signature(  # noqa: SLF001
                os.fstat(self.connection.fileno())
            )
        )
        self._session_peer_pidfd = -1
        self._session_peer_pidfd_method: str | None = None
        if self.runtime is not None:
            peer_pidfd, peer_pidfd_method = open_pidfd(
                cast(int, self.expected_peer["pid"])
            )
            try:
                if pidfd_reports_exit(peer_pidfd):
                    raise BrokerProtocolError(
                        "PEER_IDENTITY_DRIFT",
                        "broker session peer exited before READY",
                    )
                self._session_peer_pidfd = peer_pidfd
                self._session_peer_pidfd_method = peer_pidfd_method
                peer_pidfd = -1
            finally:
                if peer_pidfd >= 0:
                    os.close(peer_pidfd)

    def _require_peer(self, peer: Mapping[str, int]) -> None:
        expected = {
            "pid": self.expected_peer["pid"],
            "pid_starttime": self.expected_peer["pid_starttime"],
            "uid": self.expected_peer["uid"],
        }
        observed = {key: peer[key] for key in expected}
        if observed != expected:
            raise BrokerProtocolError("PEER_IDENTITY_DRIFT", "broker peer identity drifted")

    def _request(self, frame: ReceivedFrame) -> tuple[str, dict[str, object]]:
        record = frame.record
        required = {"action", "nonce", "payload", "schema_version", "sequence"}
        _exact_keys(record, required, label="broker request")
        if record["schema_version"] != REQUEST_SCHEMA or _nonce(record["nonce"]) != self.nonce:
            raise BrokerProtocolError("REQUEST_IDENTITY_DRIFT", "broker request schema or nonce drifted")
        sequence = _positive_int(record["sequence"], label="sequence")
        if sequence != self.sequence + 1:
            raise BrokerProtocolError("SEQUENCE_DRIFT", "broker request sequence drifted")
        action = record["action"]
        payload = record["payload"]
        if not isinstance(action, str) or type(payload) is not dict:
            raise BrokerProtocolError("FRAME_SHAPE_MISMATCH", "broker action or payload is invalid")
        self.sequence = sequence
        return action, dict(payload)

    def _journal(
        self,
        *,
        action: str,
        request_sha256: str,
        result: Mapping[str, object],
    ) -> dict[str, object]:
        sequence = (
            self.journal_sequence
            if self.runtime is None
            else self.runtime.next_journal_sequence()
        )
        result_raw = canonical_json_bytes(dict(result))
        result_projection: dict[str, object] = {
            "result_sha256": hashlib.sha256(result_raw).hexdigest(),
            "result_size_bytes": len(result_raw),
        }
        for key in ("schema_version", "state", "status"):
            value = result.get(key)
            if type(value) is str:
                result_projection[key] = value
        event = {
            "schema_version": JOURNAL_SCHEMA,
            "action": action,
            "actor": dict(self.actor),
            "event_sequence": sequence,
            "nonce": self.nonce,
            "request_sha256": request_sha256,
            "result": result_projection,
        }
        raw = canonical_json_bytes(event)
        if len(raw) > JOURNAL_MAX_BYTES:
            raise BrokerProtocolError("JOURNAL_EVENT_TOO_LARGE", "broker journal event exceeds its allocation")
        if self.runtime is not None:
            self.runtime.publication_policy.authorize(
                arm_slot=None,
                artifact_class="metadata",
                channel="budget-journal",
                label=FORMAL_BUDGET_JOURNAL_LABEL,
                maximum_bytes=JOURNAL_MAX_BYTES,
                relative_path=(
                    "channels/budget-journal/"
                    f"segment-{sequence:08d}.bin"
                ),
                sequence=sequence,
            )
        identity = self.account.append_segment(
            "budget-journal",
            sequence,
            raw,
            maximum_bytes=JOURNAL_MAX_BYTES,
            artifact_class="metadata",
        )
        if self.runtime is None:
            self.journal_sequence += 1
        return identity

    def _prepare_recovery(self, payload: Mapping[str, object]) -> tuple[dict[str, object], tuple[int, ...]]:
        if self.fixed_reservations is not None:
            _exact_keys(payload, set(), label="prepare recovery")
            detached: list[tuple[dict[str, object], int, int]] = []
            process: Any | None = None
            try:
                for purpose in (
                    "recovery-closeout",
                    "recovery-takeover-consumption",
                ):
                    try:
                        reservation = self.fixed_reservations.pop(purpose)
                    except KeyError as exc:
                        raise BrokerProtocolError(
                            "FIXED_RESERVATION_ALREADY_CONSUMED",
                            f"fixed reservation {purpose!r} is unavailable",
                        ) from exc
                    detached.append(
                        _prepared_fixed_reservation(
                            self.account,
                            purpose,
                            reservation,
                            to_owner_nonce=(
                                f"recovery-{secrets.token_hex(16)}"
                            ),
                        )
                    )
                closeout_record, closeout_parent_fd, closeout_fd = (
                    detached[0]
                )
                recovery_lock_record, lock_parent_fd, lock_fd = (
                    detached[1]
                )
                os.close(lock_parent_fd)
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if (
                    self.package_authorization is None
                    or self.native_helper is None
                    or self.runtime is None
                ):
                    raise BrokerProtocolError(
                        "PACKAGE_RUNTIME_REQUIRED",
                        "formal recovery requires retained package roles and native helper",
                    )
                internal_result = {
                    "schema_version": (
                        "noncert-cuts-ab16-prepared-recovery-v2"
                    ),
                    "closeout": closeout_record,
                    "lock": recovery_lock_record,
                }
                recovery_role = "ab16-recovery-closeout-v1"
                role_identity = _package_role_source_identity(
                    self.package_authorization,
                    recovery_role,
                )
                recovery_module = (
                    self.package_authorization.load_verified_role(
                        recovery_role
                    )
                )
                spawn = getattr(
                    recovery_module,
                    "spawn_persistent_recovery",
                    None,
                )
                if not callable(spawn):
                    raise BrokerProtocolError(
                        "PACKAGE_ROLE_ENTRYPOINT_MISSING",
                        "package recovery role lacks its fixed spawn entrypoint",
                    )
                broker_pidfd, _broker_pidfd_method = open_pidfd(
                    os.getpid()
                )
                try:
                    transfer_descriptors = (
                        closeout_parent_fd,
                        closeout_fd,
                        lock_fd,
                    )
                    detached.clear()
                    process = spawn(
                        broker_process=_BrokerLiveness(
                            actor=dict(self.actor),
                            pidfd=broker_pidfd,
                        ),
                        prepared_result=internal_result,
                        descriptors=transfer_descriptors,
                        package_authorization=self.package_authorization,
                        native_helper=self.native_helper,
                    )
                finally:
                    os.close(broker_pidfd)
                observation = self.runtime.register_recovery_actor(
                    process,
                    handoff={
                        "schema_version": (
                            "noncert-cuts-ab16-recovery-owner-observation-v2"
                        ),
                        "actor": dict(process.actor),
                        "broker_actor": dict(self.actor),
                        "pidfd_method": process.pidfd_method,
                        "prepared_recovery_identity": (
                            _message_identity(internal_result)
                        ),
                        "role": recovery_role,
                        "role_source_identity": role_identity,
                    },
                    lock_extent=cast(
                        Mapping[str, object],
                        recovery_lock_record["extent"],
                    ),
                )
                process = None
                return (observation, ())
            except BaseException:
                if process is not None:
                    try:
                        process.close()
                    except BaseException:
                        pass
                for prepared, parent_fd, staging_fd in detached:
                    try:
                        consume_once_extent(
                            prepared["extent"],
                            descriptor=staging_fd,
                            record={
                                "schema_version": DETACHED_TRANSFER_INCOMPLETE_SCHEMA,
                                "state": "TRANSFER_INCOMPLETE_SEALED",
                            },
                        )
                    except BaseException:
                        try:
                            os.fchmod(staging_fd, 0o444)
                            os.fsync(staging_fd)
                        except BaseException:
                            pass
                    for descriptor in (staging_fd, parent_fd):
                        try:
                            os.close(descriptor)
                        except BaseException:
                            pass
                raise
        _exact_keys(payload, {"closeout_maximum_bytes"}, label="prepare recovery")
        legacy_closeout, legacy_parent_fd, legacy_closeout_fd = (
            _prepare_extent(
            self.account,
            parent_path="closeout",
            target_name="formal-consumed-incomplete.json",
            maximum_bytes=_positive_int(payload["closeout_maximum_bytes"], label="closeout_maximum_bytes"),
            artifact_class="closeout",
            )
        )
        legacy_lock: PreparedExtent | None = None
        legacy_lock_fd: int | None = None
        try:
            legacy_lock, legacy_lock_fd = _prepare_once_lock(
                self.account,
                target_name="recovery-takeover-consumption.json",
            )
            return (
                {
                    "closeout_extent": legacy_closeout.as_record(),
                    "lock_extent": legacy_lock.as_record(),
                },
                (
                    legacy_parent_fd,
                    legacy_closeout_fd,
                    legacy_lock_fd,
                ),
            )
        except BaseException:
            os.close(legacy_parent_fd)
            os.close(legacy_closeout_fd)
            if legacy_lock_fd is not None:
                os.close(legacy_lock_fd)
            raise

    def _prepare_closure(self, payload: Mapping[str, object]) -> tuple[dict[str, object], tuple[int, ...]]:
        if self.fixed_reservations is not None:
            _exact_keys(payload, set(), label="prepare closure")
            order = (
                "recovery-disarm-terminal",
                "formal-budget-terminal",
                "formal-manifest",
                "formal-closure-consumption",
            )
            detached: dict[
                str,
                tuple[dict[str, object], int, int],
            ] = {}
            owned: set[int] | None = None
            transfers: dict[
                str,
                tuple[dict[str, object], int, int],
            ] = {}
            control_fd = -1
            closure_pidfd = -1
            final_release_control_fd = -1
            final_release_pidfd = -1
            release_extents: dict[
                str,
                tuple[dict[str, object], int],
            ] = {}
            release_root: Path | None = None
            try:
                for purpose in order:
                    try:
                        reservation = self.fixed_reservations.pop(purpose)
                    except KeyError as exc:
                        raise BrokerProtocolError(
                            "FIXED_RESERVATION_ALREADY_CONSUMED",
                            f"fixed reservation {purpose!r} is unavailable",
                        ) from exc
                    detached[purpose] = _prepared_fixed_reservation(
                        self.account,
                        purpose,
                        reservation,
                        to_owner_nonce=f"closure-{secrets.token_hex(16)}",
                    )
                closure_parent_fd = detached[
                    "recovery-disarm-terminal"
                ][1]
                duplicate_closure_parents = [
                    detached["formal-budget-terminal"][1],
                    detached["formal-manifest"][1],
                ]
                lock_parent_fd = detached[
                    "formal-closure-consumption"
                ][1]
                lock_fd = detached["formal-closure-consumption"][2]
                if any(
                        budget._signature(  # noqa: SLF001
                            os.fstat(closure_parent_fd)
                        )
                        != budget._signature(  # noqa: SLF001
                            os.fstat(parent_fd)
                        )
                        for parent_fd in duplicate_closure_parents
                ):
                    raise BrokerProtocolError(
                        "FIXED_RESERVATION_PARENT_DRIFT",
                        "formal closure or release reservations have different parents",
                    )
                owned = {
                    descriptor
                    for _prepared, parent_fd, staging_fd in detached.values()
                    for descriptor in (parent_fd, staging_fd)
                }
                transfers = dict(detached)
                reservations = {
                    purpose: transfers[purpose][0]
                    for purpose in order
                }
                detached.clear()
                for descriptor in (
                    *duplicate_closure_parents,
                    lock_parent_fd,
                ):
                    os.close(descriptor)
                    owned.remove(descriptor)
                if self.final_release_parent_capability is None:
                    raise BrokerProtocolError(
                        "FINAL_RELEASE_CAPABILITY_MISSING",
                        "formal closure lacks its outside final-release capability",
                    )
                release_root = self.final_release_parent_capability.path
                release_parent_fd, release_extents = (
                    self.final_release_parent_capability.detach_for_closure()
                )
                owned.add(release_parent_fd)
                owned.update(
                    descriptor
                    for _extent, descriptor in release_extents.values()
                )
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                if (
                    self.package_authorization is None
                    or self.native_helper is None
                    or self.runtime is None
                ):
                    raise BrokerProtocolError(
                        "PACKAGE_RUNTIME_REQUIRED",
                        "formal closure requires retained package roles and native helper",
                    )
                recovery_actor, recovery_pidfd, recovery_lock = (
                    self.runtime.recovery_closure_inputs()
                )
                final_release_role = "ab16-final-release-actor-v1"
                primary_replay_role = "replay-ab16-formal-root-v1"
                alternate_replay_role = (
                    "replay-ab16-formal-root-alt-v1"
                )
                final_release_source_identity = (
                    _package_role_source_identity(
                        self.package_authorization,
                        final_release_role,
                    )
                )
                primary_replay_source_identity = (
                    _package_role_source_identity(
                        self.package_authorization,
                        primary_replay_role,
                    )
                )
                alternate_replay_source_identity = (
                    _package_role_source_identity(
                        self.package_authorization,
                        alternate_replay_role,
                    )
                )
                final_release_module = (
                    self.package_authorization.load_verified_role(
                        final_release_role
                    )
                )
                spawn_final_release = getattr(
                    final_release_module,
                    "spawn_persistent_final_release",
                    None,
                )
                if not callable(spawn_final_release) or release_root is None:
                    raise BrokerProtocolError(
                        "PACKAGE_ROLE_ENTRYPOINT_MISSING",
                        "package final-release role lacks its fixed spawn entrypoint",
                    )
                success_extent, success_fd = release_extents[
                    "success-dual-lock-release"
                ]
                failure_extent, failure_fd = release_extents[
                    "failure-terminal-release"
                ]
                primary_replay_extent, primary_replay_fd = release_extents[
                    "formal-root-replay-primary-receipt"
                ]
                (
                    alternate_replay_extent,
                    alternate_replay_fd,
                ) = release_extents[
                    "formal-root-replay-alternate-receipt"
                ]
                release_owned = {
                    release_parent_fd,
                    success_fd,
                    failure_fd,
                    primary_replay_fd,
                    alternate_replay_fd,
                }
                if not release_owned <= owned:
                    raise BrokerProtocolError(
                        "RELEASE_EXTENT_OWNERSHIP_DRIFT",
                        "release extent ownership changed before actor transfer",
                    )
                # The actor's spawn primitive crosses the irreversible fork
                # handoff and closes every broker-side release copy on every
                # returned path.
                owned.difference_update(release_owned)
                final_release_process = spawn_final_release(
                    formal_root=self.account.root,
                    release_root=release_root,
                    parent_fd=release_parent_fd,
                    success_fd=success_fd,
                    failure_fd=failure_fd,
                    primary_replay_fd=primary_replay_fd,
                    alternate_replay_fd=alternate_replay_fd,
                    success_extent=success_extent,
                    failure_extent=failure_extent,
                    primary_replay_extent=primary_replay_extent,
                    alternate_replay_extent=alternate_replay_extent,
                    primary_replay_source_identity=(
                        primary_replay_source_identity
                    ),
                    alternate_replay_source_identity=(
                        alternate_replay_source_identity
                    ),
                    source_identity=final_release_source_identity,
                    expected_peer=self.expected_peer,
                )
                final_release_control_fd = (
                    final_release_process.connection.detach()
                )
                final_release_pidfd = final_release_process.pidfd
                final_release_process.pidfd = -1
                final_release_handoff = {
                    "schema_version": (
                        "noncert-cuts-ab16-final-release-owner-handoff-v1"
                    ),
                    "actor": dict(final_release_process.actor),
                    "alternate_replay_source_identity": (
                        alternate_replay_source_identity
                    ),
                    "broker_actor": dict(self.actor),
                    "control_descriptor_identity": _identity(
                        final_release_control_fd
                    ),
                    "formal_root_path": str(self.account.root),
                    "nonce": final_release_process.nonce,
                    "pidfd_method": final_release_process.pidfd_method,
                    "prepared_release_identity": _message_identity(
                        {
                            "alternate_replay_extent": (
                                alternate_replay_extent
                            ),
                            "failure_extent": failure_extent,
                            "primary_replay_extent": (
                                primary_replay_extent
                            ),
                            "success_extent": success_extent,
                        }
                    ),
                    "primary_replay_source_identity": (
                        primary_replay_source_identity
                    ),
                    "ready_handshake_identity": (
                        final_release_process.ready_handshake_identity
                    ),
                    "release_root_path": str(release_root),
                    "role": final_release_role,
                    "role_source_identity": (
                        final_release_source_identity
                    ),
                }
                final_release_handoff_identity = _message_identity(
                    final_release_handoff
                )
                closure_role = "ab16-closure-actor-v1"
                role_identity = _package_role_source_identity(
                    self.package_authorization,
                    closure_role,
                )
                closure_module = (
                    self.package_authorization.load_verified_role(
                        closure_role
                    )
                )
                spawn = getattr(
                    closure_module,
                    "spawn_persistent_closure",
                    None,
                )
                if not callable(spawn):
                    raise BrokerProtocolError(
                        "PACKAGE_ROLE_ENTRYPOINT_MISSING",
                        "package closure role lacks its fixed spawn entrypoint",
                    )
                prepared_for_actor = {
                    "extents": [
                        reservations[purpose]["extent"]
                        for purpose in (
                            "recovery-disarm-terminal",
                            "formal-budget-terminal",
                            "formal-manifest",
                        )
                    ],
                    "lock_extent": reservations[
                        "formal-closure-consumption"
                    ]["extent"],
                    "expected_root_path_types": (
                        self.account.expected_root_path_types()
                    ),
                    "control_endpoint_paths": (
                        self.runtime.closure_control_endpoint_paths()
                    ),
                }
                closure_descriptors = (
                    closure_parent_fd,
                    lock_fd,
                    transfers["recovery-disarm-terminal"][2],
                    transfers["formal-budget-terminal"][2],
                    transfers["formal-manifest"][2],
                )
                broker_pidfd, _broker_pidfd_method = open_pidfd(
                    os.getpid()
                )
                process: Any | None = None
                try:
                    process = spawn(
                        root=self.account.root,
                        broker_actor=dict(self.actor),
                        broker_pidfd=broker_pidfd,
                        recovery_actor=recovery_actor,
                        recovery_pidfd=recovery_pidfd,
                        recovery_lock_extent=recovery_lock,
                        final_release_actor=dict(
                            final_release_process.actor
                        ),
                        final_release_pidfd=final_release_pidfd,
                        final_release_pidfd_method=(
                            final_release_process.pidfd_method
                        ),
                        final_release_handoff_identity=(
                            final_release_handoff_identity
                        ),
                        prepared_result=prepared_for_actor,
                        descriptors=closure_descriptors,
                        expected_peer=self.expected_peer,
                        package_authorization=self.package_authorization,
                        native_helper=self.native_helper,
                    )
                    for descriptor in closure_descriptors:
                        owned.remove(descriptor)
                finally:
                    os.close(broker_pidfd)
                control_fd = process.connection.detach()
                closure_pidfd = process.pidfd
                process.pidfd = -1
                handoff = {
                    "schema_version": "noncert-cuts-ab16-closure-owner-handoff-v1",
                    "actor": dict(process.actor),
                    "broker_actor": dict(self.actor),
                    "control_descriptor_identity": _identity(control_fd),
                    "final_release_actor": dict(
                        final_release_process.actor
                    ),
                    "final_release_handoff_identity": (
                        final_release_handoff_identity
                    ),
                    "final_release_pidfd_method": (
                        final_release_process.pidfd_method
                    ),
                    "nonce": process.nonce,
                    "pidfd_method": process.pidfd_method,
                    "prepared_closure_identity": _message_identity(
                        prepared_for_actor
                    ),
                    "recovery_actor": recovery_actor,
                    "role": closure_role,
                    "role_source_identity": role_identity,
                }
                registered = self.runtime.register_closure_transfer(
                    handoff=handoff,
                    final_release_handoff=final_release_handoff,
                )
                return (
                    {
                        "schema_version": CLOSURE_CONTROL_TRANSFER_SCHEMA,
                        "closure_handoff": handoff,
                        "final_release_handoff": final_release_handoff,
                        "registration": registered,
                    },
                    (
                        control_fd,
                        closure_pidfd,
                        final_release_control_fd,
                        final_release_pidfd,
                    ),
                )
            except BaseException:
                for descriptor in (
                    control_fd,
                    closure_pidfd,
                    final_release_control_fd,
                    final_release_pidfd,
                ):
                    if descriptor >= 0:
                        try:
                            os.close(descriptor)
                        except BaseException:
                            pass
                if owned is not None:
                    for _extent, staging_fd in release_extents.values():
                        if staging_fd in owned:
                            try:
                                os.fchmod(staging_fd, 0o444)
                                os.fsync(staging_fd)
                            except BaseException:
                                pass
                    for prepared, parent_fd, staging_fd in (
                        transfers.values()
                    ):
                        if staging_fd in owned:
                            try:
                                consume_once_extent(
                                    prepared["extent"],
                                    descriptor=staging_fd,
                                    record={
                                        "schema_version": DETACHED_TRANSFER_INCOMPLETE_SCHEMA,
                                        "state": (
                                            "TRANSFER_INCOMPLETE_SEALED"
                                        ),
                                    },
                                )
                            except BaseException:
                                try:
                                    os.fchmod(staging_fd, 0o444)
                                    os.fsync(staging_fd)
                                except BaseException:
                                    pass
                    for descriptor in tuple(owned):
                        try:
                            os.close(descriptor)
                        except BaseException:
                            pass
                    owned.clear()
                    raise
                closed: set[int] = set()
                for prepared, parent_fd, staging_fd in detached.values():
                    try:
                        consume_once_extent(
                            prepared["extent"],
                            descriptor=staging_fd,
                            record={
                                "schema_version": (
                                    "noncert-cuts-ab16-detached-transfer-"
                                    "incomplete-v1"
                                ),
                                "state": "TRANSFER_INCOMPLETE_SEALED",
                            },
                        )
                    except BaseException:
                        try:
                            os.fchmod(staging_fd, 0o444)
                            os.fsync(staging_fd)
                        except BaseException:
                            pass
                    for descriptor in (staging_fd, parent_fd):
                        if descriptor in closed:
                            continue
                        closed.add(descriptor)
                        try:
                            os.close(descriptor)
                        except BaseException:
                            pass
                raise
        expected = {
            "budget_terminal_maximum_bytes",
            "formal_manifest_maximum_bytes",
            "recovery_terminal_maximum_bytes",
        }
        _exact_keys(payload, expected, label="prepare closure")
        specifications = (
            (
                "recovery-disarm-terminal.json",
                payload["recovery_terminal_maximum_bytes"],
                "closeout",
            ),
            (
                "budget-terminal.json",
                payload["budget_terminal_maximum_bytes"],
                "closeout",
            ),
            (
                "formal-manifest.json",
                payload["formal_manifest_maximum_bytes"],
                "metadata",
            ),
        )
        legacy_parent_fd: int | None = None
        legacy_extent_fds: list[int] = []
        legacy_extents: list[PreparedExtent] = []
        legacy_lock_fd: int | None = None
        try:
            for target, maximum, artifact_class in specifications:
                extent, observed_parent, descriptor = _prepare_extent(
                    self.account,
                    parent_path="formal-closure",
                    target_name=target,
                    maximum_bytes=_positive_int(maximum, label=f"{target}.maximum_bytes"),
                    artifact_class=artifact_class,
                )
                if legacy_parent_fd is None:
                    legacy_parent_fd = observed_parent
                else:
                    os.close(observed_parent)
                legacy_extents.append(extent)
                legacy_extent_fds.append(descriptor)
            legacy_lock, legacy_lock_fd = _prepare_once_lock(
                self.account,
                target_name="formal-closure-consumption.json",
            )
            assert legacy_parent_fd is not None
            return (
                {
                    "extents": [
                        extent.as_record()
                        for extent in legacy_extents
                    ],
                    "lock_extent": legacy_lock.as_record(),
                },
                (
                    legacy_parent_fd,
                    legacy_lock_fd,
                    *legacy_extent_fds,
                ),
            )
        except BaseException:
            if legacy_parent_fd is not None:
                os.close(legacy_parent_fd)
            if legacy_lock_fd is not None:
                os.close(legacy_lock_fd)
            for descriptor in legacy_extent_fds:
                os.close(descriptor)
            raise

    def _publish_bootstrap_handoff(
        self,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        if self.runtime is None:
            raise BrokerProtocolError(
                "PERSISTENT_RUNTIME_REQUIRED",
                "bootstrap handoff requires the persistent runtime",
            )
        specification = self.runtime.claim_bootstrap_handoff(payload)
        raw = canonical_json_bytes(dict(payload))
        published = self.account.publish_bytes(
            cast(str, specification["relative_path"]),
            raw,
            maximum_bytes=cast(int, specification["maximum_bytes"]),
            artifact_class=cast(str, specification["artifact_class"]),
        )
        identity = {
            "path": str(
                self.account.root / cast(str, published["path"])
            ),
            "sha256": published["sha256"],
            "size_bytes": published["size_bytes"],
        }
        self.runtime.commit_bootstrap_handoff(identity)
        return {
            "handoff_identity": identity,
            "handoff_message_identity": _message_identity(payload),
        }

    def _abort_bootstrap_incomplete(
        self,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        if self.runtime is None or self.fixed_reservations is None:
            raise BrokerProtocolError(
                "PERSISTENT_RUNTIME_REQUIRED",
                "bootstrap abort requires its transferred runtime",
            )
        checked = self.runtime.begin_bootstrap_abort(payload)
        recovery_terminal, lock_extent, recovery_handoff = (
            self.runtime.abort_recovery(
                reason_sha256=cast(str, checked["reason_sha256"]),
            )
        )
        lock_release: dict[str, object] | None = None
        if lock_extent is not None:
            lock_release = _prove_prepared_lock_released(
                self.account,
                lock_extent,
            )
        abandoned: dict[str, dict[str, object]] = {}
        for purpose in sorted(tuple(self.fixed_reservations)):
            reservation = self.fixed_reservations.pop(purpose)
            _seal_abandoned_reservation(
                purpose,
                reservation,
                reason="bootstrap markerless-incomplete",
            )
            abandoned[purpose] = {
                "state": "STAGING_SEALED_WITHOUT_REFUND_OR_REUSE",
            }
        result = {
            "abandoned_fixed_reservations": abandoned,
            "bootstrap_failure_identity": checked[
                "bootstrap_failure_identity"
            ],
            "prior_handoff_state": checked["prior_handoff_state"],
            "recovery_handoff_identity": (
                None
                if recovery_handoff is None
                else _message_identity(recovery_handoff)
            ),
            "recovery_lock_release": lock_release,
            "recovery_terminal": recovery_terminal,
            "state": "MARKERLESS_BOOTSTRAP_ABORTED",
        }
        self.runtime.finish_bootstrap_abort(result)
        self.exit_requested = True
        return result

    def _validate_arm_seal_request(
        self,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        if (
            self.session_grant is None
            or self.session_grant.role
            not in {"arm-authority", "supervisor"}
            or self.runtime is None
            or self.native_helper is None
        ):
            raise BrokerProtocolError(
                "ACTION_NOT_AUTHORIZED",
                "arm sealing requires the package-pinned formal supervisor",
            )
        _exact_keys(
            payload,
            {
                "arm_allocation_identity",
                "arm_attempt_prefix",
                "arm_slot",
                "expected_path_types_before",
                "manifest_expected_sha256",
                "manifest_maximum_bytes",
                "manifest_size_bytes",
                "replay_maximum_bytes",
                "consumption_maximum_bytes",
                "terminal_maximum_bytes",
            },
            label="publish arm manifest and seal",
        )
        slot = budget._safe_component(  # noqa: SLF001
            cast(str, payload["arm_slot"]),
            label="arm_slot",
        )
        prefix_parts = budget._relative_parts(  # noqa: SLF001
            cast(str, payload["arm_attempt_prefix"]),
            allow_dot=False,
        )
        prefix = str(PurePosixPath(*prefix_parts))
        manifest_path = str(
            PurePosixPath(*prefix_parts, ARM_MANIFEST_NAME)
        )
        terminal_path = str(
            PurePosixPath(
                *budget._relative_parts(  # noqa: SLF001
                    ARM_TERMINAL_DIRECTORY,
                    allow_dot=False,
                ),
                f"{slot}.json",
            )
        )
        replay_path = str(
            PurePosixPath(ARM_REPLAY_DIRECTORY, f"{slot}.json")
        )
        consumption_path = str(
            PurePosixPath(ARM_CONSUMPTION_DIRECTORY, f"{slot}.json")
        )
        if (
            prefix_parts not in self.account._registered_directories  # noqa: SLF001
            or budget._relative_parts(  # noqa: SLF001
                ARM_TERMINAL_DIRECTORY,
                allow_dot=False,
            )
            not in self.account._registered_directories  # noqa: SLF001
            or budget._relative_parts(  # noqa: SLF001
                ARM_REPLAY_DIRECTORY,
                allow_dot=False,
            )
            not in self.account._registered_directories  # noqa: SLF001
            or budget._relative_parts(  # noqa: SLF001
                ARM_CONSUMPTION_DIRECTORY,
                allow_dot=False,
            )
            not in self.account._registered_directories  # noqa: SLF001
        ):
            raise BrokerProtocolError(
                "FIXED_LAYOUT_NOT_PREREGISTERED",
                "arm manifest or terminal directory is not package-preregistered",
            )
        expected_before = _canonical_path_types(
            payload["expected_path_types_before"],
            label="expected_path_types_before",
        )
        if expected_before != self.account.expected_root_path_types():
            raise BrokerProtocolError(
                "ROOT_INVENTORY_DRIFT",
                "arm seal input does not equal the live broker inventory",
            )
        allocation_identity = self.runtime.require_allocation(
            slot,
            payload["arm_allocation_identity"],
        )
        if self.session_grant.role == "arm-authority" and (
            self.session_grant.arm_slot != slot
            or self.session_grant.allocation_identity
            != allocation_identity
        ):
            raise BrokerProtocolError(
                "GRANT_SCOPE_DRIFT",
                "arm seal differs from its exact arm-authority grant",
            )
        if self.runtime.pending_arm_response() is not None:
            raise BrokerProtocolError(
                "PRIOR_RESPONSE_UNACKNOWLEDGED",
                "the previous arm seal response is not durably accepted",
            )
        return {
            "allocation_identity": allocation_identity,
            "arm_attempt_prefix": prefix,
            "arm_slot": slot,
            "expected_path_types_before": expected_before,
            "manifest_expected_sha256": _sha256(
                payload["manifest_expected_sha256"],
                label="manifest_expected_sha256",
            ),
            "manifest_maximum_bytes": _positive_int(
                payload["manifest_maximum_bytes"],
                label="manifest_maximum_bytes",
            ),
            "manifest_path": manifest_path,
            "manifest_size_bytes": _positive_int(
                payload["manifest_size_bytes"],
                label="manifest_size_bytes",
            ),
            "replay_maximum_bytes": _positive_int(
                payload["replay_maximum_bytes"],
                label="replay_maximum_bytes",
            ),
            "replay_path": replay_path,
            "consumption_maximum_bytes": _positive_int(
                payload["consumption_maximum_bytes"],
                label="consumption_maximum_bytes",
            ),
            "consumption_path": consumption_path,
            "terminal_maximum_bytes": _positive_int(
                payload["terminal_maximum_bytes"],
                label="terminal_maximum_bytes",
            ),
            "terminal_path": terminal_path,
        }

    def _publish_arm_manifest_and_terminal(
        self,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        context = self._active_arm_seal
        if context is None or self.native_helper is None:
            raise BrokerProtocolError(
                "ARM_SEAL_STATE_DRIFT",
                "arm seal publication lacks its locked intent context",
            )
        if any(
            payload.get(request_key) != context.get(context_key)
            for request_key, context_key in (
                ("arm_slot", "arm_slot"),
                ("arm_attempt_prefix", "arm_attempt_prefix"),
                ("manifest_expected_sha256", "manifest_expected_sha256"),
                ("manifest_maximum_bytes", "manifest_maximum_bytes"),
                ("manifest_size_bytes", "manifest_size_bytes"),
                ("replay_maximum_bytes", "replay_maximum_bytes"),
                (
                    "consumption_maximum_bytes",
                    "consumption_maximum_bytes",
                ),
                ("terminal_maximum_bytes", "terminal_maximum_bytes"),
            )
        ):
            raise BrokerProtocolError(
                "ARM_SEAL_STATE_DRIFT",
                "arm seal payload changed after its durable intent",
            )
        source_fd = self.native_helper.recv_fd(self.connection.fileno())
        try:
            seals = self.native_helper.get_seals(source_fd)
            if (
                seals != self.native_helper.final_seal_mask
                or self.native_helper.has_writable_mapping(source_fd)
            ):
                raise BrokerProtocolError(
                    "SOURCE_MEMFD_NOT_SEALED",
                    "arm manifest source lacks the exact final seal boundary",
                )
            size = cast(int, context["manifest_size_bytes"])
            metadata = os.fstat(source_fd)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 0
                or metadata.st_size != size
            ):
                raise BrokerProtocolError(
                    "SOURCE_MEMFD_IDENTITY_DRIFT",
                    "arm manifest source is not the expected anonymous memfd",
                )
            digest = budget._sha256_descriptor(  # noqa: SLF001
                source_fd,
                size_bytes=size,
            )
            if digest != context["manifest_expected_sha256"]:
                raise BrokerProtocolError(
                    "SOURCE_MEMFD_IDENTITY_DRIFT",
                    "arm manifest source SHA-256 differs",
                )
            raw = b"".join(
                os.pread(
                    source_fd,
                    min(1024 * 1024, size - offset),
                    offset,
                )
                for offset in range(0, size, 1024 * 1024)
            )
            if len(raw) != size:
                raise BrokerProtocolError(
                    "SOURCE_MEMFD_IDENTITY_DRIFT",
                    "arm manifest source short-read",
                )
            manifest = strict_canonical_object(
                raw,
                label="arm attempt manifest",
            )
            expected_manifest_keys = {
                "arm_attempt_prefix",
                "arm_slot",
                "authority_scope",
                "authorizations",
                "bindings",
                "entries",
                "inventory",
                "schema_version",
                "status",
                "terminal_self_exclusion",
            }
            _exact_keys(
                manifest,
                expected_manifest_keys,
                label="arm attempt manifest",
            )
            current_inventory = self.account.expected_root_path_types()
            current_arm_inventory = _path_types_for_prefix(
                current_inventory,
                prefix=cast(str, context["arm_attempt_prefix"]),
            )
            before_arm_inventory = _path_types_for_prefix(
                cast(list[dict[str, str]], context["expected_path_types_before"]),
                prefix=cast(str, context["arm_attempt_prefix"]),
            )
            if current_arm_inventory != before_arm_inventory:
                raise BrokerProtocolError(
                    "ARM_INVENTORY_DRIFT",
                    "arm subtree changed while writing the sealing intent",
                )
            predicted_arm_inventory = sorted(
                (
                    *current_arm_inventory,
                    {
                        "path": cast(str, context["manifest_path"]),
                        "type": "regular",
                    },
                ),
                key=lambda item: (item["path"], item["type"]),
            )
            arm_inventory_digest = hashlib.sha256(
                canonical_json_bytes(predicted_arm_inventory)
            ).hexdigest()
            if (
                manifest["schema_version"]
                != "noncert-cuts-ab16-organic-attempt-artifact-manifest-v1"
                or manifest["status"] != "CLOSED_NO_GLOBAL_AUTHORITY"
                or manifest["authority_scope"] != "AB16_RESEARCH_ONLY"
                or manifest["authorizations"] != ARM_FALSE_AUTHORIZATIONS
                or manifest["arm_slot"] != context["arm_slot"]
                or manifest["arm_attempt_prefix"]
                != context["arm_attempt_prefix"]
                or manifest["inventory"]
                != {
                    "schema_version": ROOT_INVENTORY_SCHEMA,
                    "arm_expected_path_types_sha256": arm_inventory_digest,
                }
            ):
                raise BrokerProtocolError(
                    "ARM_MANIFEST_IDENTITY_DRIFT",
                    "arm manifest does not bind the broker-predicted subtree",
                )
            assert self.runtime is not None
            slot = cast(str, context["arm_slot"])
            self.runtime.publication_policy.authorize_batch(
                tuple(
                    {
                        "arm_slot": slot,
                        "artifact_class": artifact_class,
                        "channel": None,
                        "label": logical_label,
                        "maximum_bytes": cast(int, maximum),
                        "relative_path": cast(str, relative_path),
                        "sequence": None,
                    }
                    for (
                        logical_label,
                        relative_path,
                        artifact_class,
                        maximum,
                    ) in (
                        (
                            ARM_MANIFEST_BUDGET_LABEL,
                            context["manifest_path"],
                            ARM_MANIFEST_ARTIFACT_CLASS,
                            context["manifest_maximum_bytes"],
                        ),
                        (
                            ARM_TERMINAL_BUDGET_LABEL,
                            context["terminal_path"],
                            ARM_TERMINAL_ARTIFACT_CLASS,
                            context["terminal_maximum_bytes"],
                        ),
                        (
                            ARM_REPLAY_BUDGET_LABEL,
                            context["replay_path"],
                            ARM_REPLAY_ARTIFACT_CLASS,
                            context["replay_maximum_bytes"],
                        ),
                        (
                            ARM_CONSUMPTION_BUDGET_LABEL,
                            context["consumption_path"],
                            ARM_CONSUMPTION_ARTIFACT_CLASS,
                            context["consumption_maximum_bytes"],
                        ),
                    )
                )
            )
            published_manifest = (
                self.account.publish_preverified_descriptor(
                    cast(str, context["manifest_path"]),
                    source_fd,
                    size_bytes=size,
                    expected_sha256=digest,
                    maximum_bytes=cast(
                        int,
                        context["manifest_maximum_bytes"],
                    ),
                    artifact_class=ARM_MANIFEST_ARTIFACT_CLASS,
                    arm_slot=cast(str, context["arm_slot"]),
                )
            )
            manifest_identity = {
                "path": str(
                    self.account.root
                    / cast(str, published_manifest["path"])
                ),
                "sha256": published_manifest["sha256"],
                "size_bytes": published_manifest["size_bytes"],
            }
            terminal_parent = str(
                PurePosixPath(
                    cast(str, context["terminal_path"])
                ).parent
            )
            terminal_name = PurePosixPath(
                cast(str, context["terminal_path"])
            ).name
            reservation = self.account.reserve_retained_staging(
                terminal_parent,
                maximum_bytes=cast(
                    int,
                    context["terminal_maximum_bytes"],
                ),
                artifact_class=ARM_TERMINAL_ARTIFACT_CLASS,
                purpose=f"arm-terminal-{context['arm_slot']}",
                arm_slot=cast(str, context["arm_slot"]),
            )
            replay_reservation = self.account.reserve_retained_staging(
                str(PurePosixPath(cast(str, context["replay_path"])).parent),
                maximum_bytes=cast(
                    int,
                    context["replay_maximum_bytes"],
                ),
                artifact_class=ARM_REPLAY_ARTIFACT_CLASS,
                purpose=f"arm-replay-{context['arm_slot']}",
                arm_slot=cast(str, context["arm_slot"]),
            )
            consumption_reservation = (
                self.account.reserve_retained_staging(
                    str(
                        PurePosixPath(
                            cast(str, context["consumption_path"])
                        ).parent
                    ),
                    maximum_bytes=cast(
                        int,
                        context["consumption_maximum_bytes"],
                    ),
                    artifact_class=ARM_CONSUMPTION_ARTIFACT_CLASS,
                    purpose=f"arm-consumption-{context['arm_slot']}",
                    arm_slot=cast(str, context["arm_slot"]),
                )
            )
            terminal_published = False
            post_seal_registered = False
            try:
                reservation_record = reservation.record()
                self.account.bind_retained_staging_target(
                    staging_path=cast(
                        str,
                        reservation_record["staging_path"],
                    ),
                    target_path=cast(str, context["terminal_path"]),
                )
                replay_reservation_record = replay_reservation.record()
                consumption_reservation_record = (
                    consumption_reservation.record()
                )
                self.account.bind_retained_staging_target(
                    staging_path=cast(
                        str,
                        replay_reservation_record["staging_path"],
                    ),
                    target_path=cast(str, context["replay_path"]),
                )
                self.account.bind_retained_staging_target(
                    staging_path=cast(
                        str,
                        consumption_reservation_record["staging_path"],
                    ),
                    target_path=cast(
                        str,
                        context["consumption_path"],
                    ),
                )
                reconcile = self.account.arm_account(
                    cast(str, context["arm_slot"])
                )
                reconcile_record = {
                    "schema_version": ARM_RECONCILE_SCHEMA,
                    **{
                        key: reconcile[key]
                        for key in (
                            "arm_slot",
                            "category_limits",
                            "category_remaining",
                            "reserved_bytes",
                            "spent_or_stranded_bytes",
                            "unspent_reserved_bytes",
                        )
                    },
                }
                terminal = {
                    "allocation_state": "SEALED_PENDING_ACK",
                    "arm_allocation_identity": dict(
                        cast(
                            dict[str, object],
                            context["allocation_identity"],
                        )
                    ),
                    "arm_attempt_prefix": context[
                        "arm_attempt_prefix"
                    ],
                    "arm_budget_reconcile": reconcile_record,
                    "arm_expected_path_types": predicted_arm_inventory,
                    "arm_expected_path_types_sha256": (
                        arm_inventory_digest
                    ),
                    "arm_slot": context["arm_slot"],
                    "authority_scope": "AB16_RESEARCH_ONLY",
                    "authorizations": dict(ARM_FALSE_AUTHORIZATIONS),
                    "global_journal_sequence_snapshot": {
                        "next_event_sequence": context[
                            "next_journal_sequence"
                        ],
                        "sealing_intent_event_sequence": context[
                            "sealing_intent_event_sequence"
                        ],
                    },
                    "manifest_allocation_debit": {
                        "artifact_class": (
                            ARM_MANIFEST_ARTIFACT_CLASS
                        ),
                        "maximum_bytes": context[
                            "manifest_maximum_bytes"
                        ],
                        "path": context["manifest_path"],
                    },
                    "manifest_identity": manifest_identity,
                    "post_seal_reservations": {
                        "consumption": {
                            "artifact_class": (
                                ARM_CONSUMPTION_ARTIFACT_CLASS
                            ),
                            "maximum_bytes": context[
                                "consumption_maximum_bytes"
                            ],
                            "path": context["consumption_path"],
                        },
                        "replay": {
                            "artifact_class": (
                                ARM_REPLAY_ARTIFACT_CLASS
                            ),
                            "maximum_bytes": context[
                                "replay_maximum_bytes"
                            ],
                            "path": context["replay_path"],
                        },
                    },
                    "schema_version": ARM_TERMINAL_SCHEMA,
                    "sealing_intent_identity": dict(
                        cast(
                            dict[str, object],
                            context["sealing_intent_identity"],
                        )
                    ),
                    "status": "SEAL_DURABLE_PENDING_ACK",
                    "terminal_self_exclusion": {
                        "terminal_contains_own_sha256": False,
                        "terminal_contains_own_size": False,
                        "terminal_path": context["terminal_path"],
                        "terminal_path_excluded_from_arm_expected_path_types": True,
                    },
                }
                terminal_raw = canonical_json_bytes(terminal)
                published_terminal = reservation.publish_bytes(
                    terminal_name,
                    terminal_raw,
                )
                terminal_published = True
                self.account.mark_bound_target_published(
                    cast(str, context["terminal_path"])
                )
                assert self.runtime is not None
                self.runtime.register_arm_post_seal_reservations(
                    cast(str, context["arm_slot"]),
                    replay=replay_reservation,
                    replay_target_path=cast(
                        str,
                        context["replay_path"],
                    ),
                    consumption=consumption_reservation,
                    consumption_target_path=cast(
                        str,
                        context["consumption_path"],
                    ),
                )
                post_seal_registered = True
            finally:
                if not terminal_published:
                    try:
                        reservation.close()
                    except BaseException:
                        pass
                if not post_seal_registered:
                    for pending_reservation in (
                        replay_reservation,
                        consumption_reservation,
                    ):
                        try:
                            pending_reservation.close()
                        except BaseException:
                            pass
            terminal_identity = {
                "path": str(
                    self.account.root
                    / cast(str, published_terminal["path"])
                ),
                "sha256": published_terminal["sha256"],
                "size_bytes": published_terminal["size_bytes"],
            }
            if (
                _path_types_for_prefix(
                    self.account.expected_root_path_types(),
                    prefix=cast(str, context["arm_attempt_prefix"]),
                )
                != predicted_arm_inventory
            ):
                raise BrokerProtocolError(
                    "ARM_INVENTORY_DRIFT",
                    "arm subtree differs after terminal publication",
                )
            context["manifest_identity"] = manifest_identity
            context["terminal_identity"] = terminal_identity
            return {
                "terminal": terminal,
                "terminal_identity": terminal_identity,
            }
        finally:
            os.close(source_fd)

    def _dispatch(
        self,
        action: str,
        payload: Mapping[str, object],
    ) -> tuple[dict[str, object], tuple[int, ...]]:
        raw_role = (
            None if self.session_grant is None else self.session_grant.role
        )
        if (
            raw_role == "formal-supervisor"
            and self._formal_supervisor_phase == "PRESELECTION"
            and action
            not in {
                "BIND_SELECTION",
                "CLOSE_SESSION",
                "PUBLISH",
                "PUBLISH_FD",
                "STATUS",
            }
        ):
            raise BrokerProtocolError(
                "FORMAL_SUPERVISOR_PHASE_VIOLATION",
                "preselection formal supervisor requested a selected-phase action",
            )
        role = (
            "supervisor"
            if raw_role == "formal-supervisor"
            and self._formal_supervisor_phase == "SELECTED"
            else raw_role
        )
        if role == "bootstrap-admin" and action not in {
            "ABORT_BOOTSTRAP_INCOMPLETE",
            "BUILD_AND_DELIVER_FORMAL_LAUNCH_CONTEXT",
            "CLOSE_SESSION",
            "CONFIRM_BOUND_NONARM_SESSION",
            "PUBLISH_BOOTSTRAP_HANDOFF",
            "PREPARE_RECOVERY",
            "REGISTER_BOUND_NONARM_GRANT",
            "REGISTER_FORMAL_LAUNCH_CLAIMANT",
            "START_FORMAL_LAUNCH_OWNER",
            "STATUS",
        }:
            raise BrokerProtocolError(
                "ACTION_NOT_AUTHORIZED",
                "bootstrap admin requested an action outside its handoff scope",
            )
        if role == "formal-launch-owner" and action not in {
            "BIND_MANAGER_OPENFILE_GRANT",
            "BIND_MANAGER_OPENFILE_SELECTION",
            "CLOSE_SESSION",
            "GET_FORMAL_LAUNCH_ARTIFACT_SPEC",
            "PUBLISH_FD",
            "PREREGISTER_MANAGER_OPENFILE_GRANT",
            "REGISTER_BOUND_NONARM_GRANT",
            "STATUS",
        }:
            raise BrokerProtocolError(
                "ACTION_NOT_AUTHORIZED",
                "formal-launch owner requested a runtime publication action",
            )
        if role == "formal-launch-claimant" and action not in {
            "ACK_FORMAL_LAUNCH_OWNER_CONTROL",
            "CLAIM_FORMAL_LAUNCH_OWNER_CONTROL",
            "CLOSE_SESSION",
            "STATUS",
        }:
            raise BrokerProtocolError(
                "ACTION_NOT_AUTHORIZED",
                "formal-launch claimant requested an action outside its relay",
            )
        if role == "formal-closeout-owner" and action not in {
            "CLOSE_SESSION",
            "STATUS",
        }:
            raise BrokerProtocolError(
                "ACTION_NOT_AUTHORIZED",
                "formal closeout owner requested an action outside its retained scope",
            )
        if role == "formal-worker" and action not in {
            "CLOSE_SESSION",
            "PUBLISH",
            "PUBLISH_FD",
            "REGISTER_DIRECTORY",
            "STATUS",
        }:
            raise BrokerProtocolError(
                "ACTION_NOT_AUTHORIZED",
                "formal worker requested a supervisor-only broker action",
            )
        if role == "arm" and action not in {
            "CLOSE_SESSION",
            "PUBLISH",
            "PUBLISH_ARM_MANIFEST_AND_SEAL",
            "PUBLISH_FD",
            "STATUS",
        }:
            raise BrokerProtocolError(
                "ACTION_NOT_AUTHORIZED",
                "arm session requested a supervisor-only broker action",
            )
        if role == "arm-authority" and action not in {
            "BIND_MANAGER_OPENFILE_ARM_GRANT",
            "CLOSE_SESSION",
            "PUBLISH",
            "PUBLISH_ARM_MANIFEST_AND_SEAL",
            "PUBLISH_FD",
            "STATUS",
        }:
            raise BrokerProtocolError(
                "ACTION_NOT_AUTHORIZED",
                "arm authority requested an action outside its exact scope",
            )
        if role == "arm-supervisor" and action not in {
            "CLOSE_SESSION",
            "PUBLISH",
            "PUBLISH_FD",
            "REGISTER_BOUND_ARM_GRANT",
            "STATUS",
        }:
            raise BrokerProtocolError(
                "ACTION_NOT_AUTHORIZED",
                "arm supervisor requested an action outside its child-grant scope",
            )
        if action == "REGISTER_BOUND_NONARM_GRANT":
            if (
                role
                not in {
                    "bootstrap-admin",
                    "formal-launch-owner",
                    "supervisor",
                }
                or self.runtime is None
                or self.native_helper is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "bound non-arm registration requires its exact owner and helper",
                )
            pidfd = self.native_helper.recv_fd(
                self.connection.fileno()
            )
            try:
                result = self.runtime.register_bound_nonarm_grant(
                    payload,
                    pidfd=pidfd,
                )
            finally:
                os.close(pidfd)
            return (result, ())
        if action == "GET_FORMAL_LAUNCH_ARTIFACT_SPEC":
            if (
                role != "formal-launch-owner"
                or self.runtime is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "formal-launch artifact lookup requires its retained owner",
                )
            _exact_keys(
                payload,
                {"label"},
                label="formal-launch artifact lookup",
            )
            label = payload["label"]
            if label not in {
                "formal launch admission",
                "formal selection",
            }:
                raise BrokerProtocolError(
                    "PUBLICATION_POLICY_DRIFT",
                    "formal-launch artifact label is not fixed",
                )
            return (
                self.runtime.publication_policy.formal_fixed_spec(
                    cast(str, label)
                ),
                (),
            )
        if action == "REGISTER_FORMAL_LAUNCH_CLAIMANT":
            if (
                role != "bootstrap-admin"
                or self.runtime is None
                or self.native_helper is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "formal-launch claimant registration requires bootstrap admin",
                )
            pidfd = self.native_helper.recv_fd(
                self.connection.fileno()
            )
            try:
                result = self.runtime.register_formal_launch_claimant(
                    payload,
                    pidfd=pidfd,
                )
            finally:
                os.close(pidfd)
            return (result, ())
        if action == "CLAIM_FORMAL_LAUNCH_OWNER_CONTROL":
            if (
                role != "formal-launch-claimant"
                or self.runtime is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "formal-launch control claim requires its exact claimant",
                )
            _exact_keys(
                payload,
                set(),
                label="formal-launch owner control claim",
            )
            result, descriptor = (
                self.runtime.transfer_formal_launch_owner_control(
                    peer=self.expected_peer,
                )
            )
            return (result, (descriptor,))
        if action == "ACK_FORMAL_LAUNCH_OWNER_CONTROL":
            if (
                role != "formal-launch-claimant"
                or self.runtime is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "formal-launch control ACK requires its exact claimant",
                )
            _exact_keys(
                payload,
                set(),
                label="formal-launch owner control ACK",
            )
            return (
                self.runtime.acknowledge_formal_launch_owner_control(
                    peer=self.expected_peer,
                ),
                (),
            )
        if action == "START_FORMAL_LAUNCH_OWNER":
            if (
                role != "bootstrap-admin"
                or self.runtime is None
                or self.package_authorization is None
                or self.native_helper is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "formal-launch owner startup requires bootstrap package authority",
                )
            _exact_keys(
                payload,
                {"session_id"},
                label="start formal-launch owner",
            )
            session_id = payload["session_id"]
            if (
                not isinstance(session_id, str)
                or len(session_id) < 8
                or len(session_id) > 128
                or any(
                    character
                    not in "abcdefghijklmnopqrstuvwxyz0123456789-"
                    for character in session_id
                )
            ):
                raise BrokerProtocolError(
                    "FORMAL_LAUNCH_OWNER_SESSION_INVALID",
                    "formal-launch owner session ID is invalid",
                )
            owner_role = "ab16-formal-orchestrator-v1"
            role_identity = _package_role_source_identity(
                self.package_authorization,
                owner_role,
            )
            owner_module = self.package_authorization.load_verified_role(
                owner_role
            )
            spawn = getattr(
                owner_module,
                "spawn_delayed_formal_launch_owner",
                None,
            )
            if not callable(spawn):
                raise BrokerProtocolError(
                    "PACKAGE_ROLE_ENTRYPOINT_MISSING",
                    "formal-launch owner package role lacks delayed spawn",
                )
            endpoint = self.runtime._control_endpoint_path  # noqa: SLF001
            parent_fd = _open_absolute_directory_no_symlinks(
                endpoint.parent
            )
            process: Any | None = None
            claim_descriptor = -1
            try:
                credential = secrets.token_hex(32)
                process = spawn(
                    broker_module=sys.modules[__name__],
                    broker_parent_descriptor=parent_fd,
                    broker_endpoint_name=endpoint.name,
                    broker_actor=dict(self.actor),
                    broker_nonce=self.nonce,
                    credential=credential,
                    native_helper=self.native_helper,
                    session_id=session_id,
                )
                peer = {
                    "pid": process.pid,
                    "pid_starttime": process.actor["starttime"],
                    "uid": os.getuid(),
                }
                grant = self.runtime.register_bound_nonarm_grant(
                    {
                        "credential": credential,
                        "expected_peer": peer,
                        "role": "formal-launch-owner",
                    },
                    pidfd=process.pidfd,
                )
                ready = process.release_and_wait_ready(
                    expected_grant=grant,
                )
                confirmation = (
                    self.runtime.confirm_bound_nonarm_session(
                        {
                            "credential_sha256": grant[
                                "credential_sha256"
                            ],
                            "expected_peer": peer,
                            "role": "formal-launch-owner",
                        }
                    )
                )
                claim_token = secrets.token_hex(32)
                claim_descriptor, claim_identity = (
                    _sealed_claim_memfd(
                        self.native_helper,
                        claim_token,
                    )
                )
                handoff = {
                    "broker_actor": dict(self.actor),
                    "broker_endpoint_identity": dict(
                        self.runtime._bootstrap_handoff_base[  # noqa: SLF001
                            "broker_endpoint_identity"
                        ]
                    ),
                    "claim_identity": claim_identity,
                    "context_state": "AWAITING_DELAYED_CONTEXT",
                    "grant": grant,
                    "owner_actor": dict(process.actor),
                    "owner_pidfd_method": process.pidfd_method,
                    "owner_role_source_identity": role_identity,
                    "ready": ready,
                    "registration_confirmation": confirmation,
                    "schema_version": (
                        "noncert-cuts-ab16-formal-launch-owner-"
                        "broker-handoff-v1"
                    ),
                    "state": "PREREGISTERED_LIVE_OWNER",
                    "transport_only": True,
                }
                self.runtime.retain_formal_launch_owner(
                    process=process,
                    handoff=handoff,
                    claim_identity=claim_identity,
                )
                process = None
                descriptor = claim_descriptor
                claim_descriptor = -1
                return (handoff, (descriptor,))
            except BaseException:
                if claim_descriptor >= 0:
                    os.close(claim_descriptor)
                if process is not None:
                    try:
                        process.close()
                    except BaseException:
                        pass
                raise
            finally:
                os.close(parent_fd)
        if action == "BUILD_AND_DELIVER_FORMAL_LAUNCH_CONTEXT":
            if (
                role != "bootstrap-admin"
                or self.runtime is None
                or self.package_authorization is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "formal context replay requires bootstrap package authority",
                )
            _exact_keys(
                payload,
                {"campaign_dir"},
                label="build formal-launch owner context",
            )
            campaign_dir = payload["campaign_dir"]
            if (
                not isinstance(campaign_dir, str)
                or not Path(campaign_dir).is_absolute()
            ):
                raise BrokerProtocolError(
                    "FORMAL_CONTEXT_PATH_INVALID",
                    "formal context campaign directory is invalid",
                )
            authority_module = (
                self.package_authorization.load_verified_role(
                    "ab16-authority-v2"
                )
            )
            replay = getattr(
                authority_module,
                "replay_formal_launch_context",
                None,
            )
            if not callable(replay):
                raise BrokerProtocolError(
                    "PACKAGE_ROLE_ENTRYPOINT_MISSING",
                    "package authority lacks formal context replay",
                )
            context = replay(campaign_dir=Path(campaign_dir))
            raw = canonical_json_bytes(context)
            acknowledgement = (
                self.runtime.deliver_formal_launch_owner_context(
                    {"context": context}
                )
            )
            return (
                {
                    "context_identity": {
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "size_bytes": len(raw),
                    },
                    "owner_acknowledgement": acknowledgement,
                    "state": "PACKAGE_CONTEXT_REPLAYED_AND_RETAINED",
                },
                (),
            )
        if action == "CONFIRM_BOUND_NONARM_SESSION":
            if role != "bootstrap-admin" or self.runtime is None:
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "bound owner confirmation requires bootstrap admin",
                )
            return (
                self.runtime.confirm_bound_nonarm_session(payload),
                (),
            )
        if action == "PUBLISH_BOOTSTRAP_HANDOFF":
            if role != "bootstrap-admin":
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "bootstrap handoff requires its one bootstrap admin",
                )
            return (self._publish_bootstrap_handoff(payload), ())
        if action == "ABORT_BOOTSTRAP_INCOMPLETE":
            if role != "bootstrap-admin":
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "bootstrap abort requires its one bootstrap admin",
                )
            return (self._abort_bootstrap_incomplete(payload), ())
        if action == "BIND_SELECTION":
            if (
                role
                not in {
                    "formal-launch-owner",
                    "formal-supervisor",
                    "supervisor",
                }
                or self.runtime is None
                or self.session_grant is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "selection binding requires the persistent supervisor session",
                )
            _exact_keys(
                payload,
                {"selection_identity"},
                label="bind selection",
            )
            selected = self.runtime.bind_selection(
                payload["selection_identity"]
            )
            if raw_role == "formal-supervisor":
                if self._formal_supervisor_phase != "PRESELECTION":
                    raise BrokerProtocolError(
                        "FORMAL_SUPERVISOR_PHASE_VIOLATION",
                        "formal supervisor selection transition is not exact-once",
                    )
                self._formal_supervisor_phase = "SELECTED"
            return ({"selection_identity": selected}, ())
        if action == "REGISTER_BOUND_ARM_GRANT":
            if (
                role not in {"supervisor", "arm-supervisor"}
                or self.runtime is None
                or self.native_helper is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "bound arm registration requires its supervisor and helper",
                )
            pidfd = self.native_helper.recv_fd(
                self.connection.fileno()
            )
            try:
                result = self.runtime.register_bound_arm_grant(
                    payload,
                    pidfd=pidfd,
                )
            finally:
                os.close(pidfd)
            return (result, ())
        if action == "PREREGISTER_MANAGER_OPENFILE_GRANT":
            if (
                role not in {"formal-launch-owner", "supervisor"}
                or self.runtime is None
                or self.session_grant is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "manager OpenFile preregistration requires supervisor",
                )
            return (
                self.runtime.preregister_manager_openfile_grant(
                    payload,
                    owner_grant=self.session_grant,
                ),
                (),
            )
        if action == "BIND_MANAGER_OPENFILE_SELECTION":
            if (
                role not in {"formal-launch-owner", "supervisor"}
                or self.runtime is None
                or self.session_grant is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "prepared selection binding requires its exact owner",
                )
            return (
                self.runtime.bind_manager_openfile_selection(
                    payload,
                    owner_grant=self.session_grant,
                ),
                (),
            )
        if action == "PREREGISTER_MANAGER_OPENFILE_ARM_GRANT":
            if role != "supervisor" or self.runtime is None:
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "manager OpenFile arm preregistration requires supervisor",
                )
            return (
                self.runtime.preregister_manager_openfile_arm_grant(
                    payload
                ),
                (),
            )
        if action == "BIND_MANAGER_OPENFILE_GRANT":
            if (
                role not in {"formal-launch-owner", "supervisor"}
                or self.runtime is None
                or self.native_helper is None
                or self.session_grant is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "manager OpenFile binding requires supervisor and helper",
                )
            pidfd = self.native_helper.recv_fd(
                self.connection.fileno()
            )
            try:
                result = self.runtime.bind_manager_openfile_grant(
                    payload,
                    pidfd=pidfd,
                    owner_grant=self.session_grant,
                )
            except BaseException:
                os.close(pidfd)
                raise
            return (result, ())
        if action == "BIND_MANAGER_OPENFILE_ARM_GRANT":
            if (
                role not in {"arm-authority", "supervisor"}
                or self.runtime is None
                or self.native_helper is None
            ):
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "manager OpenFile arm binding requires supervisor and helper",
                )
            if role == "arm-authority" and (
                self.session_grant is None
                or payload.get("arm_slot")
                != self.session_grant.arm_slot
                or payload.get("allocation_identity")
                != self.session_grant.allocation_identity
                or payload.get("selection_identity")
                != self.session_grant.selection_identity
            ):
                raise BrokerProtocolError(
                    "GRANT_BINDING_DRIFT",
                    "arm-authority manager grant binding differs from its session",
                )
            pidfd = self.native_helper.recv_fd(
                self.connection.fileno()
            )
            try:
                result = self.runtime.bind_manager_openfile_arm_grant(
                    payload,
                    pidfd=pidfd,
                )
            except BaseException:
                os.close(pidfd)
                raise
            return (result, ())
        if action == "REGISTER_DIRECTORY":
            if role != "supervisor":
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "directory registration requires the supervisor session",
                )
            _exact_keys(
                payload,
                {"mode_octal", "relative_path"},
                label="register directory",
            )
            relative_path = payload["relative_path"]
            mode_octal = payload["mode_octal"]
            if (
                not isinstance(relative_path, str)
                or mode_octal not in {"0500", "0700"}
            ):
                raise BrokerProtocolError(
                    "FRAME_SHAPE_MISMATCH",
                    "directory registration path or mode is invalid",
                )
            parts = budget._relative_parts(  # noqa: SLF001
                relative_path,
                allow_dot=False,
            )
            if parts not in self.account._registered_directories:  # noqa: SLF001
                raise BrokerProtocolError(
                    "FIXED_LAYOUT_NOT_PREREGISTERED",
                    "directory was not created by the package-bound bootstrap",
                )
            mode = int(cast(str, mode_octal), 8)
            self.account.register_directory(relative_path, mode=mode)
            descriptor = budget._open_directory_parts(  # noqa: SLF001
                self.account._root_fd,  # noqa: SLF001
                parts,
            )
            try:
                observed = os.fstat(descriptor)
                return (
                    {
                        "device": observed.st_dev,
                        "inode": observed.st_ino,
                        "mode_octal": f"{stat.S_IMODE(observed.st_mode):04o}",
                        "path": str(self.account.root / relative_path),
                        "uid": observed.st_uid,
                    },
                    (),
                )
            finally:
                os.close(descriptor)
        if action == "ALLOCATE_ARM":
            _exact_keys(payload, {"arm_slot", "category_limits"}, label="allocate arm")
            if not isinstance(payload["arm_slot"], str) or type(payload["category_limits"]) is not dict:
                raise BrokerProtocolError("FRAME_SHAPE_MISMATCH", "arm allocation payload is invalid")
            slot = budget._safe_component(  # noqa: SLF001
                payload["arm_slot"],
                label="arm_slot",
            )
            if slot not in self.arm_directories:
                raise BrokerProtocolError(
                    "ARM_LAYOUT_NOT_PREREGISTERED",
                    f"arm slot has no package-bound fixed layout: {slot}",
                )
            account = self.account.allocate_arm(
                slot,
                category_limits=dict(payload["category_limits"]),
            )
            for directory in self.arm_directories[slot]:
                parts = budget._relative_parts(  # noqa: SLF001
                    directory.path,
                    allow_dot=False,
                )
                if parts in self.account._registered_directories:  # noqa: SLF001
                    if (
                        self.account._registered_directory_modes[parts]  # noqa: SLF001
                        != directory.mode
                    ):
                        raise BrokerProtocolError(
                            "FIXED_LAYOUT_NOT_PREREGISTERED",
                            "arm directory mode differs from the transferred layout",
                        )
                elif self._account_was_created:
                    self.account.register_directory(
                        directory.path,
                        mode=directory.mode,
                    )
                else:
                    raise BrokerProtocolError(
                        "FIXED_LAYOUT_NOT_PREREGISTERED",
                        "transferred account lacks one fixed arm directory",
                    )
            result = {
                **account,
                "schema_version": ARM_ALLOCATION_SCHEMA,
                "status": "ALLOCATED",
                "registered_directories": [
                    directory.as_record()
                    for directory in self.arm_directories[slot]
                ],
            }
            if self.runtime is not None:
                result["allocation_identity"] = (
                    self.runtime.remember_allocation(slot, result)
                )
            return (
                result,
                (),
            )
        if action == "PUBLISH_ARM_MANIFEST_AND_SEAL":
            return (
                self._publish_arm_manifest_and_terminal(payload),
                (),
            )
        if action == "PUBLISH":
            expected = {
                "arm_slot",
                "artifact_class",
                "maximum_bytes",
                "payload_hex",
                "relative_path",
            }
            if self.runtime is not None:
                expected |= {"channel", "label", "sequence"}
            _exact_keys(payload, expected, label="publish")
            try:
                raw = bytes.fromhex(str(payload["payload_hex"]))
            except ValueError as exc:
                raise BrokerProtocolError("INVALID_PAYLOAD", "payload_hex is invalid") from exc
            if not isinstance(payload["relative_path"], str) or not isinstance(payload["artifact_class"], str):
                raise BrokerProtocolError("FRAME_SHAPE_MISMATCH", "publish paths or class are invalid")
            arm_slot = payload["arm_slot"]
            if arm_slot is not None and not isinstance(arm_slot, str):
                raise BrokerProtocolError("FRAME_SHAPE_MISMATCH", "publish arm_slot is invalid")
            if (
                self.session_grant is not None
                and arm_slot != self.session_grant.arm_slot
            ):
                raise BrokerProtocolError(
                    "GRANT_SCOPE_DRIFT",
                    "publication arm slot differs from the authenticated grant",
                )
            if self.runtime is not None:
                if not isinstance(payload["label"], str):
                    raise BrokerProtocolError(
                        "FRAME_SHAPE_MISMATCH",
                        "publication label is invalid",
                    )
                self.runtime.publication_policy.authorize(
                    arm_slot=arm_slot,
                    artifact_class=payload["artifact_class"],
                    channel=cast(str | None, payload["channel"]),
                    label=payload["label"],
                    maximum_bytes=_positive_int(
                        payload["maximum_bytes"],
                        label="maximum_bytes",
                    ),
                    relative_path=payload["relative_path"],
                    sequence=cast(int | None, payload["sequence"]),
                )
            return (
                self.account.publish_bytes(
                    payload["relative_path"],
                    raw,
                    maximum_bytes=_positive_int(payload["maximum_bytes"], label="maximum_bytes"),
                    artifact_class=payload["artifact_class"],
                    arm_slot=arm_slot,
                ),
                (),
            )
        if action == "PUBLISH_FD":
            expected = {
                "arm_slot",
                "artifact_class",
                "expected_sha256",
                "maximum_bytes",
                "relative_path",
                "size_bytes",
            }
            if self.runtime is not None:
                expected |= {"channel", "label", "sequence"}
            _exact_keys(payload, expected, label="publish descriptor")
            if self.native_helper is None:
                raise BrokerProtocolError(
                    "NATIVE_HELPER_REQUIRED",
                    "descriptor publication requires the package-pinned native helper",
                )
            if (
                not isinstance(payload["relative_path"], str)
                or not isinstance(payload["artifact_class"], str)
                or not isinstance(payload["expected_sha256"], str)
            ):
                raise BrokerProtocolError(
                    "FRAME_SHAPE_MISMATCH",
                    "descriptor publication identity is invalid",
                )
            arm_slot = payload["arm_slot"]
            if arm_slot is not None and not isinstance(arm_slot, str):
                raise BrokerProtocolError(
                    "FRAME_SHAPE_MISMATCH",
                    "descriptor publication arm_slot is invalid",
                )
            if (
                self.session_grant is not None
                and arm_slot != self.session_grant.arm_slot
            ):
                raise BrokerProtocolError(
                    "GRANT_SCOPE_DRIFT",
                    "descriptor publication arm slot differs from the authenticated grant",
                )
            if self.runtime is not None:
                if not isinstance(payload["label"], str):
                    raise BrokerProtocolError(
                        "FRAME_SHAPE_MISMATCH",
                        "descriptor publication label is invalid",
                    )
                self.runtime.publication_policy.authorize(
                    arm_slot=arm_slot,
                    artifact_class=payload["artifact_class"],
                    channel=cast(str | None, payload["channel"]),
                    label=payload["label"],
                    maximum_bytes=_positive_int(
                        payload["maximum_bytes"],
                        label="maximum_bytes",
                    ),
                    relative_path=payload["relative_path"],
                    sequence=cast(int | None, payload["sequence"]),
                )
            source_fd = self.native_helper.recv_fd(self.connection.fileno())
            try:
                seals = self.native_helper.get_seals(source_fd)
                expected_seals = self.native_helper.final_seal_mask
                if seals != expected_seals:
                    raise BrokerProtocolError(
                        "SOURCE_MEMFD_NOT_SEALED",
                        f"source seal mask={seals}, expected={expected_seals}",
                    )
                if self.native_helper.has_writable_mapping(source_fd):
                    raise BrokerProtocolError(
                        "SOURCE_MEMFD_WRITABLE_MAPPING",
                        "source memfd has a writable mapping",
                    )
                size = _positive_int(payload["size_bytes"], label="size_bytes")
                metadata = os.fstat(source_fd)
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_nlink != 0
                    or metadata.st_size != size
                ):
                    raise BrokerProtocolError(
                        "SOURCE_MEMFD_IDENTITY_DRIFT",
                        "source descriptor is not the expected anonymous regular memfd",
                    )
                digest = budget._sha256_descriptor(  # noqa: SLF001
                    source_fd,
                    size_bytes=size,
                )
                if digest != payload["expected_sha256"]:
                    raise BrokerProtocolError(
                        "SOURCE_MEMFD_IDENTITY_DRIFT",
                        "source memfd SHA-256 differs",
                    )
                result = self.account.publish_preverified_descriptor(
                    payload["relative_path"],
                    source_fd,
                    size_bytes=size,
                    expected_sha256=digest,
                    maximum_bytes=_positive_int(
                        payload["maximum_bytes"],
                        label="maximum_bytes",
                    ),
                    artifact_class=payload["artifact_class"],
                    arm_slot=arm_slot,
                )
                return (
                    {
                        **result,
                        "source_seal_mask": seals,
                    },
                    (),
                )
            finally:
                os.close(source_fd)
        if action == "PREPARE_RECOVERY":
            return self._prepare_recovery(payload)
        if action == "PUBLISH_DISARM_INTENT":
            if role != "supervisor" or self.runtime is None:
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "recovery disarm intent requires the authenticated formal supervisor",
                )
            return (
                self.runtime.register_recovery_disarm_intent(
                    payload
                ),
                (),
            )
        if action == "DISARM_RECOVERY":
            if role != "supervisor" or self.runtime is None:
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "recovery disarm requires the authenticated formal supervisor",
                )
            terminal, lock_extent, handoff = (
                self.runtime.disarm_recovery(payload)
            )
            lock_release = _prove_prepared_lock_released(
                self.account,
                lock_extent,
            )
            return (
                {
                    "handoff_identity": _message_identity(handoff),
                    "lock_release": lock_release,
                    "terminal": terminal,
                },
                (),
            )
        if action == "PREPARE_CLOSURE":
            return self._prepare_closure(payload)
        if action == "PUBLISH_RELEASE_TERMINAL":
            if role != "supervisor" or self.runtime is None:
                raise BrokerProtocolError(
                    "ACTION_NOT_AUTHORIZED",
                    "release terminal publication requires the authenticated formal supervisor",
                )
            result = self.runtime.publish_release_terminal(payload)
            selected_identity = result.get("selected_identity")
            if type(selected_identity) is not dict or not isinstance(
                selected_identity.get("path"),
                str,
            ):
                raise BrokerProtocolError(
                    "RELEASE_TERMINAL_IDENTITY_DRIFT",
                    "release terminal lacks its published target identity",
                )
            self.account.mark_bound_target_published(
                cast(str, selected_identity["path"])
            )
            return (result, ())
        if action == "STATUS":
            _exact_keys(payload, set(), label="status")
            return (
                {
                    "contract": self.account.contract_record(),
                    "root_inventory": {
                        "schema_version": ROOT_INVENTORY_SCHEMA,
                        "expected_path_types": (
                            self.account.expected_root_path_types()
                        ),
                    },
                    "root_closure": self.account.snapshot_root_closure(),
                },
                (),
            )
        if action == "EXIT":
            _exact_keys(payload, set(), label="exit")
            self.exit_requested = True
            if self.runtime is not None:
                self.runtime.request_exit()
            return ({"state": "BROKER_EXIT_ACCEPTED"}, ())
        if action == "CLOSE_SESSION":
            _exact_keys(payload, set(), label="close session")
            self.exit_requested = True
            return ({"state": "BROKER_SESSION_CLOSED"}, ())
        raise BrokerProtocolError("UNKNOWN_ACTION", f"unknown broker action: {action!r}")

    def _run_arm_seal_action(
        self,
        *,
        frame: ReceivedFrame,
        payload: Mapping[str, object],
    ) -> None:
        if self.runtime is None:
            raise BrokerProtocolError(
                "PERSISTENT_RUNTIME_REQUIRED",
                "arm sealing requires the persistent broker runtime",
            )
        runtime_lock = self.runtime._lock  # noqa: SLF001
        account_lock = self.account._lock  # noqa: SLF001
        runtime_lock.acquire()
        account_lock.acquire()
        context: dict[str, object] | None = None
        seal_started = False
        pending_registered = False
        try:
            context = self._validate_arm_seal_request(payload)
            event_sequence = self.runtime._journal_sequence  # noqa: SLF001
            intent_result = {
                "allocation_identity": dict(
                    cast(
                        dict[str, object],
                        context["allocation_identity"],
                    )
                ),
                "arm_attempt_prefix": context["arm_attempt_prefix"],
                "arm_slot": context["arm_slot"],
                "state": "SEALING",
            }
            intent = self._journal(
                action="PUBLISH_ARM_MANIFEST_AND_SEAL",
                request_sha256=frame.sha256,
                result=intent_result,
            )
            next_sequence = self.runtime._journal_sequence  # noqa: SLF001
            if next_sequence != event_sequence + 1:
                raise BrokerProtocolError(
                    "JOURNAL_SEQUENCE_DRIFT",
                    "arm seal intent did not consume exactly one journal sequence",
                )
            context["sealing_intent_event_sequence"] = event_sequence
            context["next_journal_sequence"] = next_sequence
            context["sealing_intent_identity"] = {
                "path": str(
                    self.account.root / cast(str, intent["path"])
                ),
                "sha256": intent["sha256"],
                "size_bytes": intent["size_bytes"],
            }
            self.account.begin_arm_seal(
                cast(str, context["arm_slot"])
            )
            seal_started = True
            self._active_arm_seal = context
            result, descriptors = self._dispatch(
                "PUBLISH_ARM_MANIFEST_AND_SEAL",
                payload,
            )
            if descriptors:
                raise BrokerProtocolError(
                    "FD_COUNT_MISMATCH",
                    "arm seal response cannot transfer a descriptor",
                )
            self.account.mark_arm_seal_durable_pending_ack(
                cast(str, context["arm_slot"])
            )
            response = {
                "schema_version": RESPONSE_SCHEMA,
                "action": "PUBLISH_ARM_MANIFEST_AND_SEAL",
                "actor": dict(self.actor),
                "journal": intent,
                "nonce": self.nonce,
                "result": result,
                "sequence": self.sequence,
                "status": "PASS",
            }
            response_sha256 = hashlib.sha256(
                canonical_json_bytes(response)
            ).hexdigest()
            if (
                self.session_grant is None
                or self._session_peer_pidfd < 0
                or self._session_peer_pidfd_method is None
                or pidfd_reports_exit(self._session_peer_pidfd)
                or tuple(
                    budget._signature(  # noqa: SLF001
                        os.fstat(self.connection.fileno())
                    )
                )
                != self._session_connection_identity
            ):
                raise BrokerProtocolError(
                    "ARM_SEAL_SESSION_DRIFT",
                    "arm seal session/grant/peer identity drifted before response",
                )
            self.runtime.register_pending_arm_response(
                arm_slot=cast(str, context["arm_slot"]),
                arm_attempt_prefix=cast(
                    str,
                    context["arm_attempt_prefix"],
                ),
                manifest_identity=cast(
                    dict[str, object],
                    context["manifest_identity"],
                ),
                terminal_identity=cast(
                    dict[str, object],
                    context["terminal_identity"],
                ),
                response_nonce=self.nonce,
                response_sequence=self.sequence,
                response_sha256=response_sha256,
                session_connection_identity=(
                    self._session_connection_identity
                ),
                session_grant=self.session_grant.as_record(),
                session_instance_id=self._session_instance_id,
                session_peer=self.session_grant.expected_peer,
                session_peer_pidfd_method=(
                    self._session_peer_pidfd_method
                ),
            )
            pending_registered = True
            observed_sha256 = send_frame(self.connection, response)
            if observed_sha256 != response_sha256:
                raise BrokerProtocolError(
                    "RESPONSE_IDENTITY_DRIFT",
                    "arm seal response digest changed during publication",
                )
        except BaseException:
            if context is not None and pending_registered:
                try:
                    self.runtime.fail_pending_arm_response(
                        cast(str, context["arm_slot"])
                    )
                except BaseException:
                    pass
            if context is not None and seal_started:
                try:
                    self.account.fail_arm_seal(
                        cast(str, context["arm_slot"])
                    )
                except BaseException:
                    pass
            raise
        finally:
            self._active_arm_seal = None
            account_lock.release()
            runtime_lock.release()

    def _run_prior_response_acceptance(
        self,
        *,
        frame: ReceivedFrame,
        payload: Mapping[str, object],
    ) -> None:
        if (
            self.runtime is None
            or self.session_grant is None
            or self.session_grant.role
            not in {"arm-authority", "supervisor"}
        ):
            raise BrokerProtocolError(
                "ACTION_NOT_AUTHORIZED",
                "prior arm response acceptance requires the formal supervisor",
            )
        runtime_lock = self.runtime._lock  # noqa: SLF001
        account_lock = self.account._lock  # noqa: SLF001
        runtime_lock.acquire()
        account_lock.acquire()
        try:
            if (
                self._session_peer_pidfd < 0
                or self._session_peer_pidfd_method is None
                or pidfd_reports_exit(self._session_peer_pidfd)
                or tuple(
                    budget._signature(  # noqa: SLF001
                        os.fstat(self.connection.fileno())
                    )
                )
                != self._session_connection_identity
            ):
                raise BrokerProtocolError(
                    "ARM_SEAL_SESSION_DRIFT",
                    "prior response acceptance left its original live connection",
                )
            accepted = self.runtime.claim_pending_arm_response(
                payload,
                session_connection_identity=(
                    self._session_connection_identity
                ),
                session_grant=self.session_grant.as_record(),
                session_instance_id=self._session_instance_id,
                session_peer=self.session_grant.expected_peer,
                session_peer_pidfd_method=(
                    self._session_peer_pidfd_method
                ),
            )
            if (
                accepted["continuation"] == "next-arm"
                and accepted["successor_arm_slot"]
                not in self.arm_directories
            ):
                raise BrokerProtocolError(
                    "PRIOR_RESPONSE_ACCEPTANCE_DRIFT",
                    "successor arm is not in the package-bound layout",
                )
            journal_result = {
                "arm_attempt_prefix": accepted[
                    "arm_attempt_prefix"
                ],
                "arm_slot": accepted["arm_slot"],
                "continuation": accepted["continuation"],
                "manifest_identity": accepted["manifest_identity"],
                "prior_response_authentication": accepted[
                    "response_authentication"
                ],
                "schema_version": PRIOR_SEAL_RESPONSE_ACCEPTED_SCHEMA,
                "state": "PRIOR_RESPONSE_ACCEPTED",
                "successor_arm_slot": accepted[
                    "successor_arm_slot"
                ],
                "terminal_identity": accepted["terminal_identity"],
            }
            journal = self._journal(
                action="PRIOR_RESPONSE_ACCEPTED",
                request_sha256=frame.sha256,
                result=journal_result,
            )
            acceptance_identity = {
                "path": str(
                    self.account.root / cast(str, journal["path"])
                ),
                "sha256": journal["sha256"],
                "size_bytes": journal["size_bytes"],
            }
            self.account.complete_arm_seal(
                cast(str, accepted["arm_slot"])
            )
            self.runtime.commit_pending_arm_response(
                accepted,
                acceptance_identity=acceptance_identity,
            )
            response = {
                "schema_version": RESPONSE_SCHEMA,
                "action": "ACCEPT_PRIOR_ARM_SEAL_RESPONSE",
                "actor": dict(self.actor),
                "journal": journal,
                "nonce": self.nonce,
                "result": journal_result,
                "sequence": self.sequence,
                "status": "PASS",
            }
            send_frame(self.connection, response)
        except BaseException:
            pending = self.runtime.pending_arm_response()
            if pending is not None:
                try:
                    self.account.fail_arm_seal(
                        cast(str, pending["arm_slot"])
                    )
                except BaseException:
                    pass
            raise
        finally:
            account_lock.release()
            runtime_lock.release()

    def _run_arm_post_seal_publication(
        self,
        *,
        frame: ReceivedFrame,
        payload: Mapping[str, object],
        kind: str,
    ) -> None:
        if (
            self.runtime is None
            or self.native_helper is None
            or self.session_grant is None
            or self.session_grant.role
            not in {"arm-authority", "supervisor"}
        ):
            raise BrokerProtocolError(
                "ACTION_NOT_AUTHORIZED",
                "post-seal arm publication requires its authenticated closure session",
            )
        _exact_keys(
            payload,
            {
                "allocation_identity",
                "arm_slot",
                "expected_sha256",
                "maximum_bytes",
                "prerequisite_identity",
                "prior_response_accepted_identity",
                "relative_path",
                "size_bytes",
            },
            label=f"arm post-seal {kind}",
        )
        slot = budget._safe_component(  # noqa: SLF001
            cast(str, payload["arm_slot"]),
            label="arm_slot",
        )
        expected_relative = (
            str(PurePosixPath(ARM_REPLAY_DIRECTORY, f"{slot}.json"))
            if kind == "replay"
            else str(
                PurePosixPath(
                    ARM_CONSUMPTION_DIRECTORY,
                    f"{slot}.json",
                )
            )
        )
        if payload["relative_path"] != expected_relative:
            raise BrokerProtocolError(
                "ARM_POST_SEAL_STATE_DRIFT",
                "post-seal target differs from its fixed path",
            )
        runtime_lock = self.runtime._lock  # noqa: SLF001
        account_lock = self.account._lock  # noqa: SLF001
        runtime_lock.acquire()
        account_lock.acquire()
        reservation: budget.RetainedStagingReservation | None = None
        try:
            reservation, context = (
                self.runtime.claim_arm_post_seal_reservation(
                    slot,
                    kind=kind,
                    allocation_identity=payload[
                        "allocation_identity"
                    ],
                    prior_response_accepted_identity=payload[
                        "prior_response_accepted_identity"
                    ],
                    prerequisite_identity=payload[
                        "prerequisite_identity"
                    ],
                    session_connection_identity=(
                        self._session_connection_identity
                    ),
                    session_grant=self.session_grant.as_record(),
                    session_instance_id=self._session_instance_id,
                )
            )
            reservation_record = cast(
                dict[str, object],
                context["reservation_record"],
            )
            size = _positive_int(
                payload["size_bytes"],
                label="size_bytes",
            )
            maximum = _positive_int(
                payload["maximum_bytes"],
                label="maximum_bytes",
            )
            digest = _sha256(
                payload["expected_sha256"],
                label="expected_sha256",
            )
            if (
                context["target_path"] != expected_relative
                or reservation_record.get("maximum_bytes") != maximum
                or reservation_record.get("arm_slot") != slot
                or reservation_record.get("artifact_class") != "closeout"
                or size > maximum
            ):
                raise BrokerProtocolError(
                    "ARM_POST_SEAL_STATE_DRIFT",
                    "post-seal request differs from its retained extent",
                )
            source_fd = self.native_helper.recv_fd(
                self.connection.fileno()
            )
            try:
                metadata = os.fstat(source_fd)
                if (
                    self.native_helper.get_seals(source_fd)
                    != self.native_helper.final_seal_mask
                    or self.native_helper.has_writable_mapping(source_fd)
                    or not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_nlink != 0
                    or metadata.st_size != size
                    or budget._sha256_descriptor(  # noqa: SLF001
                        source_fd,
                        size_bytes=size,
                    )
                    != digest
                ):
                    raise BrokerProtocolError(
                        "SOURCE_MEMFD_IDENTITY_DRIFT",
                        "post-seal source lacks its exact sealed identity",
                    )
                raw = b"".join(
                    os.pread(
                        source_fd,
                        min(1024 * 1024, size - offset),
                        offset,
                    )
                    for offset in range(0, size, 1024 * 1024)
                )
                if len(raw) != size:
                    raise BrokerProtocolError(
                        "SOURCE_MEMFD_IDENTITY_DRIFT",
                        "post-seal source short-read",
                    )
            finally:
                os.close(source_fd)
            target_name = PurePosixPath(expected_relative).name
            published = reservation.publish_bytes(
                target_name,
                raw,
                acknowledgement=lambda _record: (
                    self.account.mark_bound_target_published(
                        expected_relative
                    )
                ),
            )
            reservation = None
            publication_identity = {
                "path": str(self.account.root / expected_relative),
                "sha256": published["sha256"],
                "size_bytes": published["size_bytes"],
            }
            action = (
                "PUBLISH_ACCEPTED_ARM_REPLAY"
                if kind == "replay"
                else "PUBLISH_ARM_CONSUMPTION"
            )
            journal = self._journal(
                action=action,
                request_sha256=frame.sha256,
                result={
                    "allocation_identity": context[
                        "allocation_identity"
                    ],
                    "arm_slot": slot,
                    "publication_identity": publication_identity,
                    "state": (
                        "REPLAY_PUBLISHED"
                        if kind == "replay"
                        else "ARM_CLOSED"
                    ),
                },
            )
            journal_identity = {
                "path": str(
                    self.account.root / cast(str, journal["path"])
                ),
                "sha256": journal["sha256"],
                "size_bytes": journal["size_bytes"],
            }
            if kind == "replay":
                self.account.mark_arm_replay_published(slot)
            else:
                self.account.complete_arm_closeout(slot)
            self.runtime.commit_arm_post_seal_publication(
                slot,
                kind=kind,
                publication_identity=publication_identity,
                journal_identity=journal_identity,
            )
            send_frame(
                self.connection,
                {
                    "schema_version": RESPONSE_SCHEMA,
                    "action": action,
                    "actor": dict(self.actor),
                    "journal": journal,
                    "nonce": self.nonce,
                    "result": {
                        "publication_identity": publication_identity,
                        "state": (
                            "REPLAY_PUBLISHED"
                            if kind == "replay"
                            else "ARM_CLOSED"
                        ),
                    },
                    "sequence": self.sequence,
                    "status": "PASS",
                },
            )
        except BaseException:
            if reservation is not None:
                try:
                    reservation.close()
                except BaseException:
                    pass
            try:
                self.runtime.fail_arm_post_seal_publication(slot)
            except BaseException:
                pass
            try:
                self.account.fail_arm_post_seal_closeout(slot)
            except BaseException:
                pass
            raise
        finally:
            account_lock.release()
            runtime_lock.release()

    def run(self) -> int:
        _socket_type(self.connection)
        self._require_peer(_peer_identity(self.connection))
        ready = {
            "schema_version": RESPONSE_SCHEMA,
            "action": "READY",
            "actor": dict(self.actor),
            "journal": None,
            "nonce": self.nonce,
            "result": {
                "session_grant": (
                    self.manager_ready_record
                    if self.manager_ready_record is not None
                    else (
                        None
                        if self.session_grant is None
                        else self.session_grant.as_record()
                    )
                ),
                "state": "READY",
            },
            "sequence": 0,
            "status": "PASS",
        }
        send_frame(self.connection, ready)
        try:
            while not self.exit_requested:
                frame = receive_frame(self.connection)
                self._require_peer(frame.peer)
                action, payload = self._request(frame)
                pending = (
                    None
                    if self.runtime is None
                    else self.runtime.pending_arm_response()
                )
                if pending is not None:
                    if action != "ACCEPT_PRIOR_ARM_SEAL_RESPONSE":
                        raise BrokerProtocolError(
                            "PRIOR_RESPONSE_UNACKNOWLEDGED",
                            "the next authenticated request must accept the prior arm seal response",
                        )
                    self._run_prior_response_acceptance(
                        frame=frame,
                        payload=payload,
                    )
                    continue
                if action == "ACCEPT_PRIOR_ARM_SEAL_RESPONSE":
                    raise BrokerProtocolError(
                        "PRIOR_RESPONSE_ACCEPTANCE_DRIFT",
                        "no arm seal response awaits successor acceptance",
                    )
                if action == "PUBLISH_ARM_MANIFEST_AND_SEAL":
                    self._run_arm_seal_action(
                        frame=frame,
                        payload=payload,
                    )
                    continue
                if action == "PUBLISH_ACCEPTED_ARM_REPLAY":
                    self._run_arm_post_seal_publication(
                        frame=frame,
                        payload=payload,
                        kind="replay",
                    )
                    continue
                if action == "PUBLISH_ARM_CONSUMPTION":
                    self._run_arm_post_seal_publication(
                        frame=frame,
                        payload=payload,
                        kind="consumption",
                    )
                    continue
                result, descriptors = self._dispatch(action, payload)
                journal = None
                if action != "STATUS":
                    journal_result = (
                        {
                            "prepared_result_identity": (
                                _message_identity(result)
                            )
                        }
                        if action
                        in {"PREPARE_RECOVERY", "PREPARE_CLOSURE"}
                        else result
                    )
                    journal = self._journal(
                        action=action,
                        request_sha256=frame.sha256,
                        result=journal_result,
                    )
                if action == "EXIT":
                    # EXIT is the final broker-root write: its journal segment
                    # is durable before this exact inventory is captured.
                    # The caller must pass this record unchanged to the
                    # package-pinned closure actor after proving broker exit.
                    path_types = self.account.expected_root_path_types()
                    staging_inventory = self.account.staging_inventory()
                    result = {
                        **result,
                        "root_inventory": {
                            "schema_version": ROOT_INVENTORY_SCHEMA,
                            "expected_path_types": path_types,
                            "staging_inventory_sha256": hashlib.sha256(
                                canonical_json_bytes(staging_inventory)
                            ).hexdigest(),
                        },
                    }
                response = {
                    "schema_version": RESPONSE_SCHEMA,
                    "action": action,
                    "actor": dict(self.actor),
                    "journal": journal,
                    "nonce": self.nonce,
                    "result": result,
                    "sequence": self.sequence,
                    "status": "PASS",
                }
                try:
                    send_frame(self.connection, response, descriptors=descriptors)
                finally:
                    for descriptor in descriptors:
                        os.close(descriptor)
            return 0
        except BaseException as exc:
            try:
                send_frame(
                    self.connection,
                    {
                        "schema_version": RESPONSE_SCHEMA,
                        "action": "FAIL_CLOSED",
                        "actor": dict(self.actor),
                        "code": getattr(exc, "code", type(exc).__name__),
                        "journal": None,
                        "nonce": self.nonce,
                        "result": {"message": str(exc)},
                        "sequence": self.sequence,
                        "status": "FAIL_CLOSED",
                    },
                )
            except BaseException:
                pass
            return 2
        finally:
            cleanup_error: BaseException | None = None
            if self.runtime is not None:
                runtime_lock = self.runtime._lock  # noqa: SLF001
                account_lock = self.account._lock  # noqa: SLF001
                runtime_lock.acquire()
                account_lock.acquire()
                try:
                    abandoned_slot = (
                        self.runtime.fail_pending_arm_response_for_session(
                            self._session_instance_id
                        )
                    )
                    if abandoned_slot is not None:
                        self.account.fail_arm_seal(abandoned_slot)
                except BaseException as exc:
                    cleanup_error = exc
                finally:
                    account_lock.release()
                    runtime_lock.release()
                try:
                    self.runtime.release_session(
                        self.expected_peer["pid"]
                    )
                except BaseException as exc:
                    if cleanup_error is None:
                        cleanup_error = exc
                    else:
                        cleanup_error.add_note(
                            "session release also failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
            if self._session_peer_pidfd >= 0:
                descriptor = self._session_peer_pidfd
                self._session_peer_pidfd = -1
                try:
                    os.close(descriptor)
                except BaseException as exc:
                    if cleanup_error is None:
                        cleanup_error = exc
                    else:
                        cleanup_error.add_note(
                            "session peer pidfd close also failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
            if self.close_account_on_exit:
                try:
                    self.account.close()
                except BaseException as exc:
                    if cleanup_error is None:
                        cleanup_error = exc
                    else:
                        cleanup_error.add_note(
                            "broker account close also failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
            if cleanup_error is not None:
                raise cleanup_error


class BrokerProcess:
    """Zero-authority process harness used by focused tests and calibration."""

    def __init__(
        self,
        *,
        pid: int,
        pidfd: int,
        pidfd_method: str,
        connection: socket.socket,
        nonce: str,
        actor: Mapping[str, object],
        native_helper: NativeHelperProtocol | None = None,
    ) -> None:
        self.pid = pid
        self.pidfd = pidfd
        self.pidfd_method = pidfd_method
        self.connection = connection
        self.nonce = nonce
        self.actor = dict(actor)
        self.native_helper = native_helper
        self.sequence = 0
        self._waited = False

    def _validated_response(
        self,
        action: str,
        response: ReceivedFrame,
    ) -> ReceivedFrame:
        record = response.record
        if (
            record.get("schema_version") == RESPONSE_SCHEMA
            and record.get("status") == "FAIL_CLOSED"
            and record.get("nonce") == self.nonce
            and record.get("sequence") == self.sequence
            and record.get("actor") == self.actor
        ):
            for descriptor in response.descriptors:
                os.close(descriptor)
            code = record.get("code")
            result = record.get("result")
            message = result.get("message") if isinstance(result, dict) else None
            raise BrokerProtocolError(
                str(code) if isinstance(code, str) and code else "BROKER_FAIL_CLOSED",
                str(message) if isinstance(message, str) and message else "broker failed closed",
            )
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("status") != "PASS"
            or record.get("action") != action
            or record.get("nonce") != self.nonce
            or record.get("sequence") != self.sequence
            or record.get("actor") != self.actor
        ):
            for descriptor in response.descriptors:
                os.close(descriptor)
            raise BrokerProtocolError("RESPONSE_IDENTITY_DRIFT", "broker response identity drifted")
        return response

    def request(
        self,
        action: str,
        payload: Mapping[str, object],
        *,
        expected_fd_counts: frozenset[int] = frozenset({0}),
    ) -> ReceivedFrame:
        self.sequence += 1
        send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": action,
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": self.sequence,
            },
        )
        response = receive_frame(self.connection, expected_fd_counts=expected_fd_counts)
        return self._validated_response(action, response)

    def publish_descriptor(
        self,
        payload: Mapping[str, object],
        *,
        descriptor: int,
    ) -> ReceivedFrame:
        """Send one fully sealed memfd in the request's second packet."""

        if self.native_helper is None:
            raise BrokerProtocolError(
                "NATIVE_HELPER_REQUIRED",
                "descriptor publication requires the package-pinned native helper",
            )
        self.sequence += 1
        send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "PUBLISH_FD",
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": self.sequence,
            },
        )
        self.native_helper.send_fd(self.connection.fileno(), descriptor)
        response = receive_frame(self.connection)
        return self._validated_response("PUBLISH_FD", response)

    def wait(self) -> int:
        if self._waited:
            raise BrokerProtocolError("PROCESS_ALREADY_WAITED", "broker process cannot be waited twice")
        _pid, status = os.waitpid(self.pid, 0)
        self._waited = True
        if os.WIFEXITED(status):
            return os.WEXITSTATUS(status)
        return 128 + os.WTERMSIG(status)

    def close(self) -> None:
        self.connection.close()
        os.close(self.pidfd)


class BrokerSessionClient:
    """One authenticated supervisor or arm connection to a persistent owner."""

    def __init__(
        self,
        *,
        connection: socket.socket,
        nonce: str,
        actor: Mapping[str, object],
        grant: BrokerSessionGrant,
        native_helper: NativeHelperProtocol | None,
    ) -> None:
        self.connection = connection
        self.nonce = nonce
        self.actor = dict(actor)
        self.grant = grant
        self.native_helper = native_helper
        self.sequence = 0
        self.closed = False
        self._pending_arm_response_authentication: (
            dict[str, object] | None
        ) = None

    def request(
        self,
        action: str,
        payload: Mapping[str, object],
        *,
        expected_fd_counts: frozenset[int] = frozenset({0}),
    ) -> ReceivedFrame:
        if self.closed:
            raise BrokerProtocolError(
                "SESSION_CLOSED",
                "persistent broker session is already closed",
            )
        if (
            self._pending_arm_response_authentication is not None
            and action != "ACCEPT_PRIOR_ARM_SEAL_RESPONSE"
        ):
            raise BrokerProtocolError(
                "PRIOR_RESPONSE_UNACKNOWLEDGED",
                "the next request must accept the prior arm seal response",
            )
        self.sequence += 1
        send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": action,
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": self.sequence,
            },
        )
        response = receive_frame(
            self.connection,
            expected_fd_counts=expected_fd_counts | frozenset({0}),
        )
        record = response.record
        if (
            record.get("schema_version") == RESPONSE_SCHEMA
            and record.get("status") == "FAIL_CLOSED"
            and record.get("nonce") == self.nonce
            and record.get("sequence") == self.sequence
            and record.get("actor") == self.actor
        ):
            for descriptor in response.descriptors:
                os.close(descriptor)
            code = record.get("code")
            result = record.get("result")
            message = result.get("message") if isinstance(result, dict) else None
            raise BrokerProtocolError(
                str(code) if isinstance(code, str) and code else "BROKER_FAIL_CLOSED",
                str(message) if isinstance(message, str) and message else "broker failed closed",
            )
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("status") != "PASS"
            or record.get("action") != action
            or record.get("nonce") != self.nonce
            or record.get("sequence") != self.sequence
            or record.get("actor") != self.actor
        ):
            for descriptor in response.descriptors:
                os.close(descriptor)
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "persistent broker response identity drifted",
            )
        if len(response.descriptors) not in expected_fd_counts:
            for descriptor in response.descriptors:
                os.close(descriptor)
            raise BrokerProtocolError(
                "FD_COUNT_MISMATCH",
                "persistent broker PASS descriptor count differs",
            )
        return response

    def publish_arm_manifest_and_seal(
        self,
        payload: Mapping[str, object],
        *,
        descriptor: int,
    ) -> ReceivedFrame:
        if self.native_helper is None:
            raise BrokerProtocolError(
                "NATIVE_HELPER_REQUIRED",
                "arm manifest sealing requires the package-pinned native helper",
            )
        if self.closed:
            raise BrokerProtocolError(
                "SESSION_CLOSED",
                "persistent broker session is already closed",
            )
        if self._pending_arm_response_authentication is not None:
            raise BrokerProtocolError(
                "PRIOR_RESPONSE_UNACKNOWLEDGED",
                "another arm seal response still awaits acceptance",
            )
        self.sequence += 1
        send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "PUBLISH_ARM_MANIFEST_AND_SEAL",
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": self.sequence,
            },
        )
        self.native_helper.send_fd(
            self.connection.fileno(),
            descriptor,
        )
        response = receive_frame(self.connection)
        record = response.record
        if (
            record.get("schema_version") == RESPONSE_SCHEMA
            and record.get("status") == "FAIL_CLOSED"
            and record.get("nonce") == self.nonce
            and record.get("actor") == self.actor
        ):
            failure = record.get("result")
            raise BrokerProtocolError(
                (
                    cast(str, record["code"])
                    if isinstance(record.get("code"), str)
                    else "BROKER_FAIL_CLOSED"
                ),
                (
                    cast(str, failure["message"])
                    if type(failure) is dict
                    and isinstance(failure.get("message"), str)
                    else "broker failed closed"
                ),
            )
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("status") != "PASS"
            or record.get("action")
            != "PUBLISH_ARM_MANIFEST_AND_SEAL"
            or record.get("nonce") != self.nonce
            or record.get("sequence") != self.sequence
            or record.get("actor") != self.actor
            or type(record.get("result")) is not dict
        ):
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "persistent broker arm-seal response drifted",
            )
        self._pending_arm_response_authentication = {
            "nonce": self.nonce,
            "response_sequence": self.sequence,
            "response_sha256": response.sha256,
        }
        return response

    def accept_prior_arm_seal_response(
        self,
        *,
        continuation: str,
        successor_arm_slot: str | None,
    ) -> ReceivedFrame:
        authentication = self._pending_arm_response_authentication
        if authentication is None:
            raise BrokerProtocolError(
                "PRIOR_RESPONSE_ACCEPTANCE_DRIFT",
                "no arm seal response awaits acceptance",
            )
        response = self.request(
            "ACCEPT_PRIOR_ARM_SEAL_RESPONSE",
            {
                "continuation": continuation,
                "prior_response_authentication": dict(authentication),
                "successor_arm_slot": successor_arm_slot,
            },
        )
        result = response.record.get("result")
        if (
            type(result) is not dict
            or result.get("state") != "PRIOR_RESPONSE_ACCEPTED"
            or result.get("prior_response_authentication")
            != authentication
        ):
            raise BrokerProtocolError(
                "PRIOR_RESPONSE_ACCEPTANCE_DRIFT",
                "durable prior-response acceptance differs",
            )
        self._pending_arm_response_authentication = None
        return response

    def _publish_arm_post_seal_descriptor(
        self,
        action: str,
        payload: Mapping[str, object],
        *,
        descriptor: int,
    ) -> ReceivedFrame:
        if (
            action
            not in {
                "PUBLISH_ACCEPTED_ARM_REPLAY",
                "PUBLISH_ARM_CONSUMPTION",
            }
            or self.native_helper is None
            or self.closed
            or self._pending_arm_response_authentication is not None
        ):
            raise BrokerProtocolError(
                "ARM_POST_SEAL_STATE_DRIFT",
                "post-seal publication client state differs",
            )
        self.sequence += 1
        send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": action,
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": self.sequence,
            },
        )
        self.native_helper.send_fd(
            self.connection.fileno(),
            descriptor,
        )
        response = receive_frame(self.connection)
        record = response.record
        if (
            record.get("schema_version") == RESPONSE_SCHEMA
            and record.get("status") == "FAIL_CLOSED"
            and record.get("nonce") == self.nonce
            and record.get("sequence") == self.sequence
            and record.get("actor") == self.actor
        ):
            result = record.get("result")
            raise BrokerProtocolError(
                (
                    cast(str, record["code"])
                    if isinstance(record.get("code"), str)
                    else "BROKER_FAIL_CLOSED"
                ),
                (
                    cast(str, result["message"])
                    if type(result) is dict
                    and isinstance(result.get("message"), str)
                    else "broker failed closed"
                ),
            )
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("status") != "PASS"
            or record.get("action") != action
            or record.get("nonce") != self.nonce
            or record.get("sequence") != self.sequence
            or record.get("actor") != self.actor
            or response.descriptors
        ):
            for received in response.descriptors:
                os.close(received)
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "post-seal publication response differs",
            )
        return response

    def publish_accepted_arm_replay(
        self,
        payload: Mapping[str, object],
        *,
        descriptor: int,
    ) -> ReceivedFrame:
        return self._publish_arm_post_seal_descriptor(
            "PUBLISH_ACCEPTED_ARM_REPLAY",
            payload,
            descriptor=descriptor,
        )

    def publish_arm_consumption(
        self,
        payload: Mapping[str, object],
        *,
        descriptor: int,
    ) -> ReceivedFrame:
        return self._publish_arm_post_seal_descriptor(
            "PUBLISH_ARM_CONSUMPTION",
            payload,
            descriptor=descriptor,
        )

    def register_bound_nonarm_grant(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
    ) -> ReceivedFrame:
        if self.native_helper is None:
            raise BrokerProtocolError(
                "NATIVE_HELPER_REQUIRED",
                "bound non-arm registration requires the package-pinned helper",
            )
        if self.closed:
            raise BrokerProtocolError(
                "SESSION_CLOSED",
                "persistent broker session is already closed",
            )
        self.sequence += 1
        send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "REGISTER_BOUND_NONARM_GRANT",
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": self.sequence,
            },
        )
        self.native_helper.send_fd(self.connection.fileno(), pidfd)
        response = receive_frame(self.connection)
        record = response.record
        if (
            record.get("schema_version") == RESPONSE_SCHEMA
            and record.get("status") == "FAIL_CLOSED"
            and record.get("nonce") == self.nonce
            and record.get("sequence") == self.sequence
            and record.get("actor") == self.actor
        ):
            code = record.get("code")
            result = record.get("result")
            message = result.get("message") if isinstance(result, dict) else None
            raise BrokerProtocolError(
                str(code) if isinstance(code, str) and code else "BROKER_FAIL_CLOSED",
                str(message) if isinstance(message, str) and message else "broker failed closed",
            )
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("status") != "PASS"
            or record.get("action")
            != "REGISTER_BOUND_NONARM_GRANT"
            or record.get("nonce") != self.nonce
            or record.get("sequence") != self.sequence
            or record.get("actor") != self.actor
        ):
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "bound non-arm registration response drifted",
            )
        return response

    def register_formal_launch_claimant(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
    ) -> ReceivedFrame:
        if self.native_helper is None:
            raise BrokerProtocolError(
                "NATIVE_HELPER_REQUIRED",
                "formal-launch claimant registration requires the package helper",
            )
        if self.closed:
            raise BrokerProtocolError(
                "SESSION_CLOSED",
                "persistent broker session is already closed",
            )
        self.sequence += 1
        send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "REGISTER_FORMAL_LAUNCH_CLAIMANT",
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": self.sequence,
            },
        )
        self.native_helper.send_fd(self.connection.fileno(), pidfd)
        response = receive_frame(self.connection)
        record = response.record
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("status") != "PASS"
            or record.get("action")
            != "REGISTER_FORMAL_LAUNCH_CLAIMANT"
            or record.get("nonce") != self.nonce
            or record.get("sequence") != self.sequence
            or record.get("actor") != self.actor
            or response.descriptors
        ):
            for descriptor in response.descriptors:
                os.close(descriptor)
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "formal-launch claimant registration response drifted",
            )
        return response

    def claim_formal_launch_owner_control(
        self,
    ) -> tuple[ReceivedFrame, ReceivedFrame]:
        claimed = self.request(
            "CLAIM_FORMAL_LAUNCH_OWNER_CONTROL",
            {},
            expected_fd_counts=frozenset({1}),
        )
        try:
            acknowledged = self.request(
                "ACK_FORMAL_LAUNCH_OWNER_CONTROL",
                {},
            )
        except BaseException:
            for descriptor in claimed.descriptors:
                os.close(descriptor)
            raise
        return claimed, acknowledged

    def register_bound_arm_grant(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
    ) -> ReceivedFrame:
        if self.native_helper is None:
            raise BrokerProtocolError(
                "NATIVE_HELPER_REQUIRED",
                "bound arm registration requires the package-pinned helper",
            )
        if self.closed:
            raise BrokerProtocolError(
                "SESSION_CLOSED",
                "persistent broker session is already closed",
            )
        self.sequence += 1
        send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "REGISTER_BOUND_ARM_GRANT",
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": self.sequence,
            },
        )
        self.native_helper.send_fd(self.connection.fileno(), pidfd)
        response = receive_frame(self.connection)
        record = response.record
        if (
            record.get("schema_version") == RESPONSE_SCHEMA
            and record.get("status") == "FAIL_CLOSED"
            and record.get("nonce") == self.nonce
            and record.get("sequence") == self.sequence
            and record.get("actor") == self.actor
        ):
            code = record.get("code")
            result = record.get("result")
            message = result.get("message") if isinstance(result, dict) else None
            raise BrokerProtocolError(
                str(code) if isinstance(code, str) and code else "BROKER_FAIL_CLOSED",
                str(message) if isinstance(message, str) and message else "broker failed closed",
            )
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("status") != "PASS"
            or record.get("action") != "REGISTER_BOUND_ARM_GRANT"
            or record.get("nonce") != self.nonce
            or record.get("sequence") != self.sequence
            or record.get("actor") != self.actor
        ):
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "bound arm registration response drifted",
            )
        return response

    def bind_manager_openfile_grant(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
    ) -> ReceivedFrame:
        if self.native_helper is None:
            raise BrokerProtocolError(
                "NATIVE_HELPER_REQUIRED",
                "manager OpenFile pidfd transfer requires native helper",
            )
        if self.closed:
            raise BrokerProtocolError(
                "SESSION_CLOSED",
                "persistent broker session is already closed",
            )
        self.sequence += 1
        send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "BIND_MANAGER_OPENFILE_GRANT",
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": self.sequence,
            },
        )
        self.native_helper.send_fd(
            self.connection.fileno(),
            pidfd,
        )
        response = receive_frame(self.connection)
        record = response.record
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("status") != "PASS"
            or record.get("action")
            != "BIND_MANAGER_OPENFILE_GRANT"
            or record.get("nonce") != self.nonce
            or record.get("sequence") != self.sequence
            or record.get("actor") != self.actor
        ):
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "manager OpenFile bind response drifted",
            )
        return response

    def bind_manager_openfile_selection(
        self,
        payload: Mapping[str, object],
    ) -> ReceivedFrame:
        """Bind exact PREPARE bytes before their no-replace COMMIT."""

        return self.request(
            "BIND_MANAGER_OPENFILE_SELECTION",
            payload,
        )

    def preregister_manager_openfile_arm_grant(
        self,
        payload: Mapping[str, object],
    ) -> ReceivedFrame:
        return self.request(
            "PREREGISTER_MANAGER_OPENFILE_ARM_GRANT",
            payload,
        )

    def bind_manager_openfile_arm_grant(
        self,
        payload: Mapping[str, object],
        *,
        pidfd: int,
    ) -> ReceivedFrame:
        if self.native_helper is None:
            raise BrokerProtocolError(
                "NATIVE_HELPER_REQUIRED",
                "manager OpenFile arm pidfd transfer requires native helper",
            )
        if self.closed:
            raise BrokerProtocolError(
                "SESSION_CLOSED",
                "persistent broker session is already closed",
            )
        self.sequence += 1
        send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "BIND_MANAGER_OPENFILE_ARM_GRANT",
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": self.sequence,
            },
        )
        self.native_helper.send_fd(
            self.connection.fileno(),
            pidfd,
        )
        response = receive_frame(self.connection)
        record = response.record
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("status") != "PASS"
            or record.get("action")
            != "BIND_MANAGER_OPENFILE_ARM_GRANT"
            or record.get("nonce") != self.nonce
            or record.get("sequence") != self.sequence
            or record.get("actor") != self.actor
        ):
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "manager OpenFile arm bind response drifted",
            )
        return response

    def publish_descriptor(
        self,
        payload: Mapping[str, object],
        *,
        descriptor: int,
        publication_boundary: Callable[[], None] | None = None,
    ) -> ReceivedFrame:
        if self.native_helper is None:
            raise BrokerProtocolError(
                "NATIVE_HELPER_REQUIRED",
                "descriptor publication requires the package-pinned native helper",
            )
        if self.closed:
            raise BrokerProtocolError(
                "SESSION_CLOSED",
                "persistent broker session is already closed",
            )
        self.sequence += 1
        if publication_boundary is not None:
            publication_boundary()
        send_frame(
            self.connection,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "PUBLISH_FD",
                "nonce": self.nonce,
                "payload": dict(payload),
                "sequence": self.sequence,
            },
        )
        self.native_helper.send_fd(self.connection.fileno(), descriptor)
        response = receive_frame(self.connection)
        record = response.record
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("status") != "PASS"
            or record.get("action") != "PUBLISH_FD"
            or record.get("nonce") != self.nonce
            or record.get("sequence") != self.sequence
            or record.get("actor") != self.actor
        ):
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "persistent broker descriptor response drifted",
            )
        return response

    def close_session(self) -> None:
        if self.closed:
            raise BrokerProtocolError(
                "SESSION_CLOSED",
                "persistent broker session cannot close twice",
            )
        self.request("CLOSE_SESSION", {})
        try:
            self.connection.close()
        finally:
            self.closed = True

    def close(self) -> None:
        if not self.closed:
            try:
                self.connection.close()
            finally:
                self.closed = True


def validate_worker_stdio_contract() -> list[dict[str, object]]:
    """Close stdio as an explicit non-filesystem diagnostic capability.

    Landlock does not revoke an already-open writable descriptor.  Workers
    therefore accept only a read-only pipe/socket/null input and writable
    pipe/socket/null diagnostic outputs before the descriptor allowlist is
    installed.  In particular, regular files, directories, block devices,
    and arbitrary character devices fail closed.
    """

    try:
        null_metadata = os.stat("/dev/null", follow_symlinks=False)
    except OSError as exc:
        raise BrokerProtocolError(
            "WORKER_STDIO_CONTRACT_INVALID",
            "trusted null-device identity cannot be observed",
        ) from exc
    if not stat.S_ISCHR(null_metadata.st_mode):
        raise BrokerProtocolError(
            "WORKER_STDIO_CONTRACT_INVALID",
            "trusted null-device path is not a character device",
        )
    records: list[dict[str, object]] = []
    for descriptor in (0, 1, 2):
        try:
            metadata = os.fstat(descriptor)
            flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
        except OSError as exc:
            raise BrokerProtocolError(
                "WORKER_STDIO_CONTRACT_INVALID",
                f"worker stdio FD{descriptor} cannot be verified",
            ) from exc
        access = flags & os.O_ACCMODE
        if descriptor == 0:
            if access != os.O_RDONLY:
                raise BrokerProtocolError(
                    "WORKER_STDIO_CONTRACT_INVALID",
                    "worker stdin is not read-only",
                )
            access_name = "read-only"
        else:
            if access not in {os.O_WRONLY, os.O_RDWR}:
                raise BrokerProtocolError(
                    "WORKER_STDIO_CONTRACT_INVALID",
                    f"worker FD{descriptor} is not a diagnostic output",
                )
            access_name = (
                "write-only" if access == os.O_WRONLY else "read-write"
            )
        if stat.S_ISFIFO(metadata.st_mode):
            kind = "pipe"
        elif stat.S_ISSOCK(metadata.st_mode):
            kind = "socket"
        elif (
            stat.S_ISCHR(metadata.st_mode)
            and metadata.st_rdev == null_metadata.st_rdev
        ):
            kind = "null-character-device"
        else:
            raise BrokerProtocolError(
                "WORKER_STDIO_WRITABLE_PATH_FORBIDDEN",
                f"worker FD{descriptor} is not a safe diagnostic transport",
            )
        records.append(
            {
                "access": access_name,
                "descriptor": descriptor,
                "device": metadata.st_dev,
                "inode": metadata.st_ino,
                "kind": kind,
                "mode": stat.S_IMODE(metadata.st_mode),
                "rdev": metadata.st_rdev,
            }
        )
    return records


class BrokerProcessFormalBudgetBackend:
    """Fixed-label formal-root adapter over one authenticated broker session.

    The adapter never owns a root, directory, or staging descriptor.  Once
    worker confinement is installed, its only writable capability is the
    already-connected broker socket.
    """

    def __init__(
        self,
        *,
        broker_client: BrokerSessionClient,
        native_helper: NativeHelperProtocol,
        formal_root: Path,
        enforced_budget_profile: Mapping[str, object],
        resource_calibration_authorization_bundle: Mapping[str, object],
        resource_calibration_authorization_bundle_identity: Mapping[
            str,
            object,
        ],
        expected_calibration_tool_identities: Mapping[
            str, Mapping[str, object]
        ],
        authority_binding: Mapping[str, object],
        fixed_artifacts: Mapping[str, Mapping[str, object]],
        fixed_channels: Mapping[str, Mapping[str, object]] | None = None,
        fixed_directories: Mapping[str, Mapping[str, object]] | None = None,
        require_worker_confinement: bool = True,
    ) -> None:
        self._broker = broker_client
        self._helper = native_helper
        self._formal_root = Path(os.path.abspath(formal_root))
        self._enforced_budget_profile = dict(
            enforced_budget_profile
        )
        self._resource_calibration_authorization_bundle = dict(
            resource_calibration_authorization_bundle
        )
        self._resource_calibration_authorization_bundle_identity = dict(
            resource_calibration_authorization_bundle_identity
        )
        self._expected_calibration_tool_identities = (
            _calibration_tool_content_identities(
                expected_calibration_tool_identities
            )
        )
        self._authority_binding = dict(authority_binding)
        profile_identity = self._authority_binding.get(
            "budget_profile_identity"
        )
        if type(profile_identity) is not dict:
            raise BrokerProtocolError(
                "BUDGET_PROFILE_IDENTITY_MISSING",
                "formal backend lacks its package-pinned budget profile identity",
            )
        self._enforced_budget_profile_identity = dict(
            profile_identity
        )
        if (
            self._authority_binding.get(
                "formal_resource_calibration_bundle_identity"
            )
            != self._resource_calibration_authorization_bundle_identity
        ):
            raise BrokerProtocolError(
                "RESOURCE_CALIBRATION_BINDING_DRIFT",
                "formal backend calibration bundle differs from its selection binding",
            )
        expected_confinement = (
            "landlock-read-only-worker-v1"
            if require_worker_confinement
            else "not-applicable-persistent-supervisor-v1"
        )
        if (
            self._authority_binding.get("filesystem_write_confinement")
            != expected_confinement
            or any(
                token in key
                for key in self._authority_binding
                for token in ("root_fd", "staging_fd", "directory_fd")
            )
        ):
            raise BrokerProtocolError(
                "WORKER_AUTHORITY_BINDING_INVALID",
                "formal backend binding exposes writable authority or lacks Landlock",
            )
        self._fixed_artifacts = self._validate_fixed_targets(
            fixed_artifacts,
            label="fixed_artifacts",
        )
        (
            self._fixed_channels,
            self._fixed_channel_labels,
            self._fixed_channel_maximum_segments,
        ) = self._validate_fixed_channels(
            {} if fixed_channels is None else fixed_channels,
        )
        checked_directories: dict[str, tuple[str, frozenset[str]]] = {}
        for label, raw in (
            {} if fixed_directories is None else fixed_directories
        ).items():
            if (
                not isinstance(label, str)
                or not label
                or type(raw) is not dict
                or set(raw) != {"allowed_modes", "relative_path"}
                or type(raw["allowed_modes"]) is not list
            ):
                raise BrokerProtocolError(
                    "FIXED_DIRECTORY_TABLE_INVALID",
                    "fixed directory table shape differs",
                )
            relative = self._relative(cast(str, raw["relative_path"]))
            modes = frozenset(cast(list[str], raw["allowed_modes"]))
            if not modes or not modes <= {"0500", "0700"}:
                raise BrokerProtocolError(
                    "FIXED_DIRECTORY_TABLE_INVALID",
                    "fixed directory mode set differs",
                )
            checked_directories[label] = (relative, modes)
        self._fixed_directories = checked_directories
        self._channel_next = {
            channel: 0 for channel in self._fixed_channels
        }
        self._require_worker_confinement = require_worker_confinement
        self._confinement_installed = False

    @property
    def enforced_budget_profile(self) -> Mapping[str, object]:
        return dict(self._enforced_budget_profile)

    @property
    def native_helper(self) -> NativeHelperProtocol:
        return self._helper

    @property
    def enforced_budget_profile_identity(
        self,
    ) -> Mapping[str, object]:
        return dict(self._enforced_budget_profile_identity)

    @property
    def resource_calibration_authorization_bundle(
        self,
    ) -> Mapping[str, object]:
        return dict(
            self._resource_calibration_authorization_bundle
        )

    @property
    def resource_calibration_authorization_bundle_identity(
        self,
    ) -> Mapping[str, object]:
        return dict(
            self._resource_calibration_authorization_bundle_identity
        )

    @property
    def expected_calibration_tool_identities(
        self,
    ) -> Mapping[str, Mapping[str, object]]:
        return {
            role: dict(identity)
            for role, identity in sorted(
                self._expected_calibration_tool_identities.items()
            )
        }

    def _relative(self, value: str) -> str:
        if not isinstance(value, str):
            raise BrokerProtocolError(
                "FIXED_TARGET_TABLE_INVALID",
                "fixed relative path is not text",
            )
        parts = budget._relative_parts(value, allow_dot=False)  # noqa: SLF001
        return str(PurePosixPath(*parts))

    def _validate_fixed_targets(
        self,
        value: Mapping[str, Mapping[str, object]],
        *,
        label: str,
    ) -> dict[str, tuple[str, str, int]]:
        checked: dict[str, tuple[str, str, int]] = {}
        for logical_label, raw in value.items():
            if (
                not isinstance(logical_label, str)
                or not logical_label
                or type(raw) is not dict
                or set(raw)
                != {"artifact_class", "maximum_bytes", "relative_path"}
                or not isinstance(raw["artifact_class"], str)
            ):
                raise BrokerProtocolError(
                    "FIXED_TARGET_TABLE_INVALID",
                    f"{label} shape differs",
                )
            checked[logical_label] = (
                self._relative(cast(str, raw["relative_path"])),
                cast(str, raw["artifact_class"]),
                _positive_int(
                    raw["maximum_bytes"],
                    label=f"{logical_label}.maximum_bytes",
                ),
            )
        return checked

    def _validate_fixed_channels(
        self,
        value: Mapping[str, Mapping[str, object]],
    ) -> tuple[
        dict[str, tuple[str, str, int]],
        dict[str, str],
        dict[str, int],
    ]:
        checked: dict[str, tuple[str, str, int]] = {}
        labels: dict[str, str] = {}
        maxima: dict[str, int] = {}
        for channel, raw in value.items():
            if (
                not isinstance(channel, str)
                or not channel
                or type(raw) is not dict
                or set(raw)
                != {
                    "artifact_class",
                    "label",
                    "maximum_bytes",
                    "maximum_segments",
                    "relative_path",
                }
                or type(raw["artifact_class"]) is not str
                or type(raw["label"]) is not str
                or not raw["label"]
            ):
                raise BrokerProtocolError(
                    "FIXED_CHANNEL_TABLE_INVALID",
                    "fixed append-channel table shape differs",
                )
            checked[channel] = (
                self._relative(cast(str, raw["relative_path"])),
                cast(str, raw["artifact_class"]),
                _positive_int(
                    raw["maximum_bytes"],
                    label=f"{channel}.maximum_bytes",
                ),
            )
            labels[channel] = cast(str, raw["label"])
            maxima[channel] = _nonnegative_int(
                raw["maximum_segments"],
                label=f"{channel}.maximum_segments",
            )
        return checked, labels, maxima

    @property
    def authority_binding(self) -> Mapping[str, object]:
        return dict(self._authority_binding)

    @property
    def formal_budget_runtime(self) -> Mapping[str, object]:
        value = self._authority_binding.get("formal_budget_runtime")
        if type(value) is not dict:
            raise BrokerProtocolError(
                "WORKER_AUTHORITY_BINDING_INVALID",
                "formal backend binding lacks the validated budget runtime",
            )
        return dict(value)

    @property
    def selected_fd_transport(self) -> Mapping[str, object]:
        value = self._authority_binding.get("selected_fd_transport")
        if type(value) is not dict:
            raise BrokerProtocolError(
                "WORKER_AUTHORITY_BINDING_INVALID",
                "formal backend lacks the verified selected-FD transport",
            )
        return dict(value)

    def register_formal_worker_grant(
        self,
        *,
        credential: str,
        expected_peer: Mapping[str, object],
        pidfd: int,
    ) -> Mapping[str, object]:
        response = self._broker.register_bound_nonarm_grant(
            {
                "credential": credential,
                "expected_peer": dict(expected_peer),
                "role": "formal-worker",
            },
            pidfd=pidfd,
        )
        result = response.record.get("result")
        if type(result) is not dict:
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "formal worker grant receipt is absent",
            )
        return dict(result)

    def bind_formal_selection(
        self,
        selection_identity: Mapping[str, object],
    ) -> Mapping[str, object]:
        response = self._broker.request(
            "BIND_SELECTION",
            {"selection_identity": dict(selection_identity)},
        )
        result = response.record.get("result")
        if type(result) is not dict:
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "formal selection binding receipt is absent",
            )
        return dict(result)

    def allocate_arm(
        self,
        *,
        arm_slot: str,
        category_limits: Mapping[str, object],
    ) -> Mapping[str, object]:
        response = self._broker.request(
            "ALLOCATE_ARM",
            {
                "arm_slot": arm_slot,
                "category_limits": dict(category_limits),
            },
        )
        result = response.record.get("result")
        if type(result) is not dict:
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "arm allocation receipt is absent",
            )
        return dict(result)

    def preregister_manager_openfile_arm_grant(
        self,
        *,
        allocation_identity: Mapping[str, object],
        arm_slot: str,
        attempt_consumption_identity: Mapping[str, object],
        credential: str,
        manager_epoch_identity: Mapping[str, object],
        selection_identity: Mapping[str, object],
        unit_name: str,
    ) -> Mapping[str, object]:
        response = self._broker.preregister_manager_openfile_arm_grant(
            {
                "allocation_identity": dict(allocation_identity),
                "arm_slot": arm_slot,
                "attempt_consumption_identity": dict(
                    attempt_consumption_identity
                ),
                "credential": credential,
                "manager_epoch_identity": dict(
                    manager_epoch_identity
                ),
                "selection_identity": dict(selection_identity),
                "unit_name": unit_name,
            }
        )
        result = response.record.get("result")
        if type(result) is not dict:
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "manager OpenFile arm preregistration receipt is absent",
            )
        return dict(result)

    def register_bound_arm_grant(
        self,
        *,
        credential: str,
        expected_peer: Mapping[str, object],
        pidfd: int,
        role: str,
        arm_slot: str,
        selection_identity: Mapping[str, object],
        allocation_identity: Mapping[str, object],
    ) -> Mapping[str, object]:
        response = self._broker.register_bound_arm_grant(
            {
                "allocation_identity": dict(allocation_identity),
                "arm_slot": arm_slot,
                "credential": credential,
                "expected_peer": dict(expected_peer),
                "role": role,
                "selection_identity": dict(selection_identity),
            },
            pidfd=pidfd,
        )
        result = response.record.get("result")
        if type(result) is not dict:
            raise BrokerProtocolError(
                "RESPONSE_IDENTITY_DRIFT",
                "bound arm grant receipt is absent",
            )
        return dict(result)

    def connect_registered_arm(
        self,
        *,
        credential: str,
        role: str,
        arm_slot: str,
        selection_identity: Mapping[str, object],
        allocation_identity: Mapping[str, object],
    ) -> BrokerSessionClient:
        runtime = self.formal_budget_runtime
        endpoint = runtime.get("broker_endpoint_identity")
        actor_identity = runtime.get("broker_actor_identity")
        if (
            type(endpoint) is not dict
            or type(endpoint.get("path")) is not str
            or type(actor_identity) is not dict
        ):
            raise BrokerProtocolError(
                "BROKER_ENDPOINT_IDENTITY_DRIFT",
                "formal runtime lacks its broker endpoint",
            )
        endpoint_path = Path(cast(str, endpoint["path"]))
        parent_fd = _open_absolute_directory_no_symlinks(
            endpoint_path.parent
        )
        connection = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
        )
        try:
            connection.connect(
                f"/proc/self/fd/{parent_fd}/{endpoint_path.name}"
            )
        except BaseException:
            connection.close()
            raise
        finally:
            os.close(parent_fd)
        return attach_registered_arm_session(
            connection.detach(),
            broker_actor={
                "schema_version": ACTOR_SCHEMA,
                **actor_identity,
            },
            broker_nonce=cast(str, runtime["broker_nonce"]),
            credential=credential,
            role=role,
            arm_slot=arm_slot,
            selection_identity=selection_identity,
            allocation_identity=allocation_identity,
            native_helper=self._helper,
        )

    def maximum_bytes(
        self,
        label: str,
        *,
        artifact_class: str,
    ) -> int:
        try:
            _relative, expected_class, maximum = self._fixed_artifacts[label]
        except KeyError as exc:
            raise BrokerProtocolError(
                "FIXED_ARTIFACT_UNKNOWN",
                f"artifact label is not package-bound: {label!r}",
            ) from exc
        if artifact_class != expected_class:
            raise BrokerProtocolError(
                "FIXED_ARTIFACT_CLASS_DRIFT",
                f"artifact class differs for {label!r}",
            )
        return maximum

    def install_worker_confinement(
        self,
        retained_read_only_fds: Sequence[int],
    ) -> Mapping[str, object]:
        if not self._require_worker_confinement:
            raise BrokerProtocolError(
                "WORKER_CONFINEMENT_NOT_APPLICABLE",
                "persistent supervisor cannot install worker confinement",
            )
        if self._confinement_installed:
            raise BrokerProtocolError(
                "WORKER_CONFINEMENT_ALREADY_INSTALLED",
                "formal worker confinement cannot be installed twice",
            )
        stdio_contract = validate_worker_stdio_contract()
        connection_fd = self._broker.connection.fileno()
        keep = {0, 1, 2, connection_fd}
        for descriptor in retained_read_only_fds:
            if (
                isinstance(descriptor, bool)
                or not isinstance(descriptor, int)
                or descriptor < 0
            ):
                raise BrokerProtocolError(
                    "WORKER_FD_ALLOWLIST_INVALID",
                    "worker retained FD list is invalid",
                )
            flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
            if flags & os.O_ACCMODE != os.O_RDONLY:
                raise BrokerProtocolError(
                    "WORKER_WRITABLE_FD_FORBIDDEN",
                    "worker retained input FD is writable",
                )
            keep.add(descriptor)
        if self._helper.landlock_abi() < 1:
            raise BrokerProtocolError(
                "LANDLOCK_UNAVAILABLE",
                "formal worker requires a positive Landlock ABI",
            )
        self._helper.close_range_allowlist(sorted(keep))
        self._helper.install_no_filesystem_writes_landlock()
        self._confinement_installed = True
        return {
            "filesystem_write_confinement": (
                "landlock-read-only-worker-v1"
            ),
            "retained_read_only_fds": sorted(
                descriptor
                for descriptor in keep
                if descriptor not in {0, 1, 2, connection_fd}
            ),
            "root_or_staging_writable_fd_count": 0,
            "stdio_contract": stdio_contract,
        }

    def register_directory(
        self,
        path: Path,
        label: str,
        *,
        mode_octal: str = "0500",
    ) -> Mapping[str, object]:
        try:
            relative, allowed_modes = self._fixed_directories[label]
        except KeyError as exc:
            raise BrokerProtocolError(
                "FIXED_DIRECTORY_UNKNOWN",
                f"directory label is not package-bound: {label!r}",
            ) from exc
        absolute = Path(os.path.abspath(path))
        if (
            absolute != self._formal_root / relative
            or mode_octal not in allowed_modes
        ):
            raise BrokerProtocolError(
                "FIXED_DIRECTORY_IDENTITY_DRIFT",
                "directory path or mode differs from its package contract",
            )
        result = self._broker.request(
            "REGISTER_DIRECTORY",
            {
                "mode_octal": mode_octal,
                "relative_path": relative,
            },
        ).record["result"]
        if type(result) is not dict or result.get("path") != str(absolute):
            raise BrokerProtocolError(
                "FIXED_DIRECTORY_IDENTITY_DRIFT",
                "broker directory receipt differs",
            )
        return dict(result)

    @staticmethod
    def _sha256_descriptor(
        descriptor: int,
        size_bytes: int,
    ) -> str:
        digest = hashlib.sha256()
        offset = 0
        while offset < size_bytes:
            block = os.pread(
                descriptor,
                min(1024 * 1024, size_bytes - offset),
                offset,
            )
            if not block:
                raise BrokerProtocolError(
                    "MEMFD_IDENTITY_DRIFT",
                    "sealed memfd ended early",
                )
            digest.update(block)
            offset += len(block)
        if os.pread(descriptor, 1, size_bytes):
            raise BrokerProtocolError(
                "MEMFD_IDENTITY_DRIFT",
                "sealed memfd exceeds its stated size",
            )
        return digest.hexdigest()

    def _sealed_bytes_memfd(self, raw: bytes, *, label: str) -> int:
        descriptor = self._helper.create_memfd(
            f"ab16-{hashlib.sha256(label.encode()).hexdigest()[:16]}"
        )
        try:
            offset = 0
            while offset < len(raw):
                written = os.pwrite(descriptor, raw[offset:], offset)
                if written <= 0:
                    raise BrokerProtocolError(
                        "MEMFD_WRITE_FAILED",
                        "memfd write made no progress",
                    )
                offset += written
            os.fsync(descriptor)
            if (
                os.fstat(descriptor).st_size != len(raw)
                or self._sha256_descriptor(descriptor, len(raw))
                != hashlib.sha256(raw).hexdigest()
                or self._helper.has_writable_mapping(descriptor)
            ):
                raise BrokerProtocolError(
                    "MEMFD_IDENTITY_DRIFT",
                    "memfd identity differs before sealing",
                )
            if (
                self._helper.install_final_seals(descriptor)
                != self._helper.final_seal_mask
                or self._helper.get_seals(descriptor)
                != self._helper.final_seal_mask
            ):
                raise BrokerProtocolError(
                    "MEMFD_SEAL_FAILED",
                    "memfd final seal mask differs",
                )
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def _publish_descriptor(
        self,
        descriptor: int,
        *,
        relative: str,
        artifact_class: str,
        channel: str | None,
        label: str,
        maximum_bytes: int,
        sequence: int | None,
        size_bytes: int,
        digest: str,
        publication_boundary: Callable[[], None] | None = None,
    ) -> Mapping[str, object]:
        response = self._broker.publish_descriptor(
            {
                "arm_slot": None,
                "artifact_class": artifact_class,
                "channel": channel,
                "expected_sha256": digest,
                "label": label,
                "maximum_bytes": maximum_bytes,
                "relative_path": relative,
                "sequence": sequence,
                "size_bytes": size_bytes,
            },
            descriptor=descriptor,
            publication_boundary=publication_boundary,
        )
        result = response.record["result"]
        if (
            type(result) is not dict
            or result.get("path") != relative
            or result.get("sha256") != digest
            or result.get("size_bytes") != size_bytes
            or result.get("maximum_bytes") != maximum_bytes
            or result.get("source_seal_mask")
            != self._helper.final_seal_mask
        ):
            raise BrokerProtocolError(
                "PUBLICATION_RECEIPT_DRIFT",
                "formal broker publication receipt differs",
            )
        return {
            "path": str(self._formal_root / relative),
            "sha256": digest,
            "size_bytes": size_bytes,
        }

    def publish_bytes(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
    ) -> Mapping[str, object]:
        return self._publish_fixed_bytes(
            path,
            raw,
            maximum_bytes=maximum_bytes,
            artifact_class=artifact_class,
            label=label,
            publication_boundary=None,
        )

    def publish_bytes_with_publication_boundary(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
        publication_boundary: Callable[[], None],
    ) -> Mapping[str, object]:
        """Publish while exposing the exact pre-send no-retry boundary."""

        if not callable(publication_boundary):
            raise BrokerProtocolError(
                "PUBLICATION_BOUNDARY_INVALID",
                "formal publication boundary callback is not callable",
            )
        return self._publish_fixed_bytes(
            path,
            raw,
            maximum_bytes=maximum_bytes,
            artifact_class=artifact_class,
            label=label,
            publication_boundary=publication_boundary,
        )

    def _publish_fixed_bytes(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
        publication_boundary: Callable[[], None] | None,
    ) -> Mapping[str, object]:
        if (
            self._require_worker_confinement
            and not self._confinement_installed
        ):
            raise BrokerProtocolError(
                "WORKER_CONFINEMENT_MISSING",
                "publication precedes worker Landlock confinement",
            )
        expected_maximum = self.maximum_bytes(
            label,
            artifact_class=artifact_class,
        )
        relative = self._fixed_artifacts[label][0]
        if (
            Path(os.path.abspath(path)) != self._formal_root / relative
            or maximum_bytes != expected_maximum
            or type(raw) is not bytes
            or not 0 < len(raw) <= maximum_bytes
        ):
            raise BrokerProtocolError(
                "FIXED_ARTIFACT_IDENTITY_DRIFT",
                "publication differs from its package-bound target",
            )
        descriptor = self._sealed_bytes_memfd(raw, label=label)
        try:
            return self._publish_descriptor(
                descriptor,
                relative=relative,
                artifact_class=artifact_class,
                channel=None,
                label=label,
                maximum_bytes=maximum_bytes,
                sequence=None,
                size_bytes=len(raw),
                digest=hashlib.sha256(raw).hexdigest(),
                publication_boundary=publication_boundary,
            )
        finally:
            os.close(descriptor)

    def publish_arm_manifest_and_seal(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
        arm_slot: str,
        arm_attempt_prefix: str,
        arm_allocation_identity: Mapping[str, object],
        expected_path_types_before: Sequence[Mapping[str, object]],
    ) -> Mapping[str, object]:
        if (
            self._require_worker_confinement
            and not self._confinement_installed
        ):
            raise BrokerProtocolError(
                "WORKER_CONFINEMENT_MISSING",
                "arm sealing precedes worker Landlock confinement",
            )
        if (
            label != ARM_MANIFEST_BUDGET_LABEL
            or artifact_class != ARM_MANIFEST_ARTIFACT_CLASS
        ):
            raise BrokerProtocolError(
                "FIXED_ARTIFACT_IDENTITY_DRIFT",
                "arm manifest label or class differs",
            )
        expected_manifest_maximum = self.maximum_bytes(
            ARM_MANIFEST_BUDGET_LABEL,
            artifact_class=ARM_MANIFEST_ARTIFACT_CLASS,
        )
        expected_terminal_maximum = self.maximum_bytes(
            ARM_TERMINAL_BUDGET_LABEL,
            artifact_class=ARM_TERMINAL_ARTIFACT_CLASS,
        )
        expected_replay_maximum = self.maximum_bytes(
            ARM_REPLAY_BUDGET_LABEL,
            artifact_class=ARM_REPLAY_ARTIFACT_CLASS,
        )
        expected_consumption_maximum = self.maximum_bytes(
            ARM_CONSUMPTION_BUDGET_LABEL,
            artifact_class=ARM_CONSUMPTION_ARTIFACT_CLASS,
        )
        manifest_relative = self._fixed_artifacts[
            ARM_MANIFEST_BUDGET_LABEL
        ][0]
        terminal_relative = self._fixed_artifacts[
            ARM_TERMINAL_BUDGET_LABEL
        ][0]
        slot = budget._safe_component(arm_slot, label="arm_slot")  # noqa: SLF001
        prefix = self._relative(arm_attempt_prefix)
        if (
            manifest_relative
            != str(PurePosixPath(prefix, ARM_MANIFEST_NAME))
            or terminal_relative
            != str(PurePosixPath(ARM_TERMINAL_DIRECTORY, f"{slot}.json"))
            or Path(os.path.abspath(path))
            != self._formal_root / manifest_relative
            or maximum_bytes != expected_manifest_maximum
            or type(raw) is not bytes
            or not 0 < len(raw) <= maximum_bytes
        ):
            raise BrokerProtocolError(
                "FIXED_ARTIFACT_IDENTITY_DRIFT",
                "arm seal targets differ from the package-bound table",
            )
        canonical_before = _canonical_path_types(
            list(expected_path_types_before),
            label="expected_path_types_before",
        )
        descriptor = self._sealed_bytes_memfd(
            raw,
            label=ARM_MANIFEST_BUDGET_LABEL,
        )
        try:
            response = self._broker.publish_arm_manifest_and_seal(
                {
                    "arm_allocation_identity": dict(
                        arm_allocation_identity
                    ),
                    "arm_attempt_prefix": prefix,
                    "arm_slot": slot,
                    "expected_path_types_before": canonical_before,
                    "manifest_expected_sha256": hashlib.sha256(
                        raw
                    ).hexdigest(),
                    "manifest_maximum_bytes": maximum_bytes,
                    "manifest_size_bytes": len(raw),
                    "replay_maximum_bytes": (
                        expected_replay_maximum
                    ),
                    "consumption_maximum_bytes": (
                        expected_consumption_maximum
                    ),
                    "terminal_maximum_bytes": (
                        expected_terminal_maximum
                    ),
                },
                descriptor=descriptor,
            )
        finally:
            os.close(descriptor)
        result = response.record.get("result")
        journal = response.record.get("journal")
        if (
            type(result) is not dict
            or set(result) != {"terminal", "terminal_identity"}
            or type(result["terminal"]) is not dict
            or type(result["terminal_identity"]) is not dict
            or type(journal) is not dict
        ):
            raise BrokerProtocolError(
                "ARM_SEAL_RECEIPT_DRIFT",
                "arm seal response wrapper differs",
            )
        terminal = cast(dict[str, object], result["terminal"])
        terminal_identity = _detached_identity(
            result["terminal_identity"],
            label="arm budget terminal",
        )
        if (
            terminal.get("status") != "SEAL_DURABLE_PENDING_ACK"
            or terminal.get("allocation_state")
            != "SEALED_PENDING_ACK"
            or terminal.get("arm_slot") != slot
            or terminal.get("arm_attempt_prefix") != prefix
            or terminal.get("arm_allocation_identity")
            != dict(arm_allocation_identity)
            or terminal_identity["path"]
            != str(self._formal_root / terminal_relative)
        ):
            raise BrokerProtocolError(
                "ARM_SEAL_RECEIPT_DRIFT",
                "arm seal terminal join differs",
            )
        return {
            "response_authentication": {
                "nonce": self._broker.nonce,
                "response_sequence": self._broker.sequence,
                "response_sha256": response.sha256,
            },
            "terminal": dict(terminal),
            "terminal_identity": terminal_identity,
        }

    def accept_prior_arm_seal_response(
        self,
        *,
        continuation: str,
        successor_arm_slot: str | None,
    ) -> Mapping[str, object]:
        response = self._broker.accept_prior_arm_seal_response(
            continuation=continuation,
            successor_arm_slot=successor_arm_slot,
        )
        result = response.record.get("result")
        journal = response.record.get("journal")
        if type(result) is not dict or type(journal) is not dict:
            raise BrokerProtocolError(
                "PRIOR_RESPONSE_ACCEPTANCE_DRIFT",
                "prior arm response acceptance receipt is absent",
            )
        return {
            "accepted": dict(result),
            "journal": {
                "path": str(
                    self._formal_root / cast(str, journal["path"])
                ),
                "sha256": journal["sha256"],
                "size_bytes": journal["size_bytes"],
            },
        }

    def append_segment(
        self,
        channel: str,
        sequence: int,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
    ) -> Mapping[str, object]:
        if (
            self._require_worker_confinement
            and not self._confinement_installed
        ):
            raise BrokerProtocolError(
                "WORKER_CONFINEMENT_MISSING",
                "append publication precedes worker Landlock confinement",
            )
        if arm_slot is not None or channel not in self._fixed_channels:
            raise BrokerProtocolError(
                "FIXED_CHANNEL_UNKNOWN",
                "formal-root append channel is not package-bound",
            )
        directory, expected_class, expected_maximum = (
            self._fixed_channels[channel]
        )
        if (
            sequence != self._channel_next[channel]
            or sequence >= self._fixed_channel_maximum_segments[channel]
            or artifact_class != expected_class
            or maximum_bytes != expected_maximum
        ):
            raise BrokerProtocolError(
                "FIXED_CHANNEL_IDENTITY_DRIFT",
                "formal-root append channel sequence or maximum differs",
            )
        relative = f"{directory}/segment-{sequence:08d}.bin"
        descriptor = self._sealed_bytes_memfd(
            raw,
            label=f"{channel}:{sequence}",
        )
        try:
            result = self._publish_descriptor(
                descriptor,
                relative=relative,
                artifact_class=artifact_class,
                channel=channel,
                label=self._fixed_channel_labels[channel],
                maximum_bytes=maximum_bytes,
                sequence=sequence,
                size_bytes=len(raw),
                digest=hashlib.sha256(raw).hexdigest(),
            )
        finally:
            os.close(descriptor)
        self._channel_next[channel] = sequence + 1
        return result

    def export_model_to_sealed_memfd(
        self,
        model: object,
        path: Path,
        *,
        maximum_bytes: int,
        label: str,
    ) -> Mapping[str, object]:
        if (
            self._require_worker_confinement
            and not self._confinement_installed
        ):
            raise BrokerProtocolError(
                "WORKER_CONFINEMENT_MISSING",
                "model export precedes worker Landlock confinement",
            )
        expected_maximum = self.maximum_bytes(label, artifact_class="model")
        relative = self._fixed_artifacts[label][0]
        if (
            maximum_bytes != expected_maximum
            or Path(os.path.abspath(path)) != self._formal_root / relative
        ):
            raise BrokerProtocolError(
                "FIXED_ARTIFACT_IDENTITY_DRIFT",
                "model export differs from its package-bound target",
            )
        descriptor = self._helper.create_memfd(
            f"ab16-model-{hashlib.sha256(label.encode()).hexdigest()[:16]}"
        )
        try:
            sentinel = b"AB16_O_TRUNC_SENTINEL"
            if os.pwrite(descriptor, sentinel, 0) != len(sentinel):
                raise BrokerProtocolError(
                    "MODEL_EXPORT_FAILED",
                    "model sentinel write failed",
                )
            original_limits = resource.getrlimit(resource.RLIMIT_FSIZE)
            _soft, hard = original_limits
            if hard != resource.RLIM_INFINITY and maximum_bytes > hard:
                raise BrokerProtocolError(
                    "MODEL_EXPORT_LIMIT_INVALID",
                    "model maximum exceeds RLIMIT_FSIZE hard limit",
                )
            resource.setrlimit(
                resource.RLIMIT_FSIZE,
                (maximum_bytes, hard),
            )
            exporter = getattr(model, "export_to_file", None)
            try:
                if (
                    not callable(exporter)
                    or exporter(f"/proc/self/fd/{descriptor}") is not True
                ):
                    raise BrokerProtocolError(
                        "MODEL_EXPORT_FAILED",
                        "official O_TRUNC model export failed",
                    )
            except BaseException as primary:
                try:
                    resource.setrlimit(
                        resource.RLIMIT_FSIZE,
                        original_limits,
                    )
                except BaseException as restore_error:
                    primary.add_note(
                        "RLIMIT_FSIZE restore also failed: "
                        f"{restore_error!r}"
                    )
                raise
            try:
                resource.setrlimit(
                    resource.RLIMIT_FSIZE,
                    original_limits,
                )
            except BaseException as exc:
                raise BrokerProtocolError(
                    "MODEL_EXPORT_LIMIT_RESTORE_FAILED",
                    "RLIMIT_FSIZE could not be restored before publication",
                ) from exc
            metadata = os.fstat(descriptor)
            if (
                not 0 < metadata.st_size <= maximum_bytes
                or os.pread(descriptor, len(sentinel), 0).startswith(
                    sentinel
                )
            ):
                raise BrokerProtocolError(
                    "MODEL_EXPORT_FAILED",
                    "model export size or O_TRUNC proof differs",
                )
            digest = self._sha256_descriptor(
                descriptor,
                metadata.st_size,
            )
            if (
                self._helper.has_writable_mapping(descriptor)
                or self._helper.install_final_seals(descriptor)
                != self._helper.final_seal_mask
                or self._helper.get_seals(descriptor)
                != self._helper.final_seal_mask
            ):
                raise BrokerProtocolError(
                    "MEMFD_SEAL_FAILED",
                    "model memfd could not be closed against writes",
                )
            return self._publish_descriptor(
                descriptor,
                relative=relative,
                artifact_class="model",
                channel=None,
                label=label,
                maximum_bytes=maximum_bytes,
                sequence=None,
                size_bytes=metadata.st_size,
                digest=digest,
            )
        finally:
            os.close(descriptor)

    def close(self) -> None:
        if not self._broker.closed:
            self._broker.close_session()


def attach_manager_openfile_supervisor(
    descriptor: int,
    *,
    broker_actor: Mapping[str, object],
    broker_nonce: str,
    credential: str,
    manager_epoch_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    attempt_consumption_identity: Mapping[str, object],
    unit_name: str,
    native_helper: NativeHelperProtocol,
) -> BrokerSessionClient:
    """Authenticate systemd's manager-mediated FD as the selected supervisor.

    ``SO_PEERCRED`` on the client proves the persistent broker.  The broker's
    peer is systemd's connector, so unit authority instead comes from the
    preregistered token and the later supervisor-bound MainPID pidfd.
    """

    actor = dict(broker_actor)
    if (
        set(actor) != {"schema_version", "pid", "pid_starttime", "uid"}
        or actor["schema_version"] != ACTOR_SCHEMA
    ):
        raise BrokerProtocolError(
            "BROKER_ACTOR_IDENTITY_DRIFT",
            "manager OpenFile broker actor shape differs",
        )
    application_peer = process_identity()
    connection = _consume_socket_descriptor(
        descriptor,
        label="manager OpenFile supervisor socket",
    )
    try:
        _socket_type(connection)
        peer = _peer_identity(connection)
        if (
            {
                key: peer[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            != {
                key: actor[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            or peer["gid"] != os.getgid()
        ):
            raise BrokerProtocolError(
                "BROKER_ACTOR_IDENTITY_DRIFT",
                "manager OpenFile socket peer is not the selected broker",
            )
        nonce = _nonce(broker_nonce)
        token = _nonce(credential)
        manager_epoch = _content_identity(
            dict(manager_epoch_identity),
            label="manager OpenFile epoch",
        )
        selection = _detached_identity(
            dict(selection_identity),
            label="manager OpenFile selection",
        )
        attempt = _detached_identity(
            dict(attempt_consumption_identity),
            label="manager OpenFile attempt consumption",
        )
        send_frame(
            connection,
            {
                "schema_version": (
                    MANAGER_OPENFILE_AUTHENTICATION_SCHEMA
                ),
                "application_peer": application_peer,
                "attempt_consumption_identity": attempt,
                "credential": token,
                "manager_epoch_identity": manager_epoch,
                "nonce": nonce,
                "selection_identity": selection,
                "unit_name": unit_name,
            },
        )
        ready = receive_frame(connection)
        result = ready.record.get("result")
        grant_record = (
            result.get("session_grant")
            if type(result) is dict
            else None
        )
        if (
            ready.record.get("schema_version") != RESPONSE_SCHEMA
            or ready.record.get("action") != "READY"
            or ready.record.get("status") != "PASS"
            or ready.record.get("actor") != actor
            or ready.record.get("nonce") != nonce
            or ready.record.get("sequence") != 0
            or type(grant_record) is not dict
            or set(grant_record)
            != {
                "application_peer",
                "attempt_consumption_identity",
                "connector_peer",
                "credential_sha256",
                "guardian_ready_identity",
                "manager_epoch_identity",
                "pidfd_method",
                "schema_version",
                "selection_identity",
                "state",
                "unit_name",
            }
            or grant_record["schema_version"]
            != MANAGER_OPENFILE_GRANT_SCHEMA
            or grant_record["application_peer"] != application_peer
            or grant_record["attempt_consumption_identity"] != attempt
            or grant_record["credential_sha256"]
            != hashlib.sha256(token.encode("ascii")).hexdigest()
            or grant_record["manager_epoch_identity"] != manager_epoch
            or grant_record["selection_identity"] != selection
            or grant_record["state"] != "AUTHENTICATED"
            or grant_record["unit_name"] != unit_name
            or type(grant_record["guardian_ready_identity"]) is not dict
            or type(grant_record["pidfd_method"]) is not str
        ):
            raise BrokerProtocolError(
                "READY_IDENTITY_DRIFT",
                "manager OpenFile broker READY differs",
            )
        _peer_grant_identity(
            grant_record["connector_peer"],
            label="manager OpenFile connector",
        )
        grant = BrokerSessionGrant(
            role="supervisor",
            credential_sha256=hashlib.sha256(
                token.encode("ascii")
            ).hexdigest(),
            expected_peer=application_peer,
            arm_slot=None,
            selection_identity=None,
            allocation_identity=None,
        )
        return BrokerSessionClient(
            connection=connection,
            nonce=nonce,
            actor=actor,
            grant=grant,
            native_helper=native_helper,
        )
    except BaseException:
        connection.close()
        raise


def attach_manager_openfile_arm_supervisor(
    descriptor: int,
    *,
    broker_actor: Mapping[str, object],
    broker_nonce: str,
    credential: str,
    manager_epoch_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    allocation_identity: Mapping[str, object],
    arm_slot: str,
    attempt_consumption_identity: Mapping[str, object],
    unit_name: str,
    native_helper: NativeHelperProtocol,
) -> BrokerSessionClient:
    """Authenticate one manager-mediated FD8 as an exact arm supervisor."""

    actor = dict(broker_actor)
    if (
        set(actor) != {"schema_version", "pid", "pid_starttime", "uid"}
        or actor["schema_version"] != ACTOR_SCHEMA
    ):
        raise BrokerProtocolError(
            "BROKER_ACTOR_IDENTITY_DRIFT",
            "manager OpenFile arm broker actor shape differs",
        )
    application_peer = process_identity()
    connection = _consume_socket_descriptor(
        descriptor,
        label="manager OpenFile arm socket",
    )
    try:
        _socket_type(connection)
        peer = _peer_identity(connection)
        if (
            {
                key: peer[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            != {
                key: actor[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            or peer["gid"] != os.getgid()
        ):
            raise BrokerProtocolError(
                "BROKER_ACTOR_IDENTITY_DRIFT",
                "manager OpenFile arm socket peer is not the selected broker",
            )
        nonce = _nonce(broker_nonce)
        token = _nonce(credential)
        manager_epoch = _content_identity(
            dict(manager_epoch_identity),
            label="manager OpenFile arm epoch",
        )
        selection = _detached_identity(
            dict(selection_identity),
            label="manager OpenFile arm selection",
        )
        allocation = _content_identity(
            dict(allocation_identity),
            label="manager OpenFile arm allocation",
        )
        slot = budget._safe_component(  # noqa: SLF001
            arm_slot,
            label="arm_slot",
        )
        attempt = _detached_identity(
            dict(attempt_consumption_identity),
            label="manager OpenFile arm attempt consumption",
        )
        send_frame(
            connection,
            {
                "schema_version": (
                    MANAGER_OPENFILE_ARM_AUTHENTICATION_SCHEMA
                ),
                "allocation_identity": allocation,
                "application_peer": application_peer,
                "arm_slot": slot,
                "attempt_consumption_identity": attempt,
                "credential": token,
                "manager_epoch_identity": manager_epoch,
                "nonce": nonce,
                "selection_identity": selection,
                "unit_name": unit_name,
            },
        )
        ready = receive_frame(connection)
        result = ready.record.get("result")
        grant_record = (
            result.get("session_grant")
            if type(result) is dict
            else None
        )
        if (
            ready.record.get("schema_version") != RESPONSE_SCHEMA
            or ready.record.get("action") != "READY"
            or ready.record.get("status") != "PASS"
            or ready.record.get("actor") != actor
            or ready.record.get("nonce") != nonce
            or ready.record.get("sequence") != 0
            or type(grant_record) is not dict
            or set(grant_record)
            != {
                "allocation_identity",
                "application_peer",
                "arm_slot",
                "attempt_consumption_identity",
                "connector_peer",
                "credential_sha256",
                "guardian_ready_identity",
                "manager_epoch_identity",
                "pidfd_method",
                "schema_version",
                "selection_identity",
                "state",
                "unit_name",
            }
            or grant_record["schema_version"]
            != MANAGER_OPENFILE_ARM_GRANT_SCHEMA
            or grant_record["allocation_identity"] != allocation
            or grant_record["application_peer"] != application_peer
            or grant_record["arm_slot"] != slot
            or grant_record["attempt_consumption_identity"] != attempt
            or grant_record["credential_sha256"]
            != hashlib.sha256(token.encode("ascii")).hexdigest()
            or grant_record["manager_epoch_identity"] != manager_epoch
            or grant_record["selection_identity"] != selection
            or grant_record["state"] != "AUTHENTICATED"
            or grant_record["unit_name"] != unit_name
            or type(grant_record["guardian_ready_identity"]) is not dict
            or type(grant_record["pidfd_method"]) is not str
        ):
            raise BrokerProtocolError(
                "READY_IDENTITY_DRIFT",
                "manager OpenFile arm broker READY differs",
            )
        _peer_grant_identity(
            grant_record["connector_peer"],
            label="manager OpenFile arm connector",
        )
        grant = BrokerSessionGrant(
            role="arm-supervisor",
            credential_sha256=hashlib.sha256(
                token.encode("ascii")
            ).hexdigest(),
            expected_peer=application_peer,
            arm_slot=slot,
            selection_identity=selection,
            allocation_identity=allocation,
        )
        return BrokerSessionClient(
            connection=connection,
            nonce=nonce,
            actor=actor,
            grant=grant,
            native_helper=native_helper,
        )
    except BaseException:
        connection.close()
        raise


def attach_formal_launch_claim_session(
    descriptor: int,
    *,
    broker_actor: Mapping[str, object],
    broker_nonce: str,
    claim_descriptor: int,
    claim_identity: Mapping[str, object],
    native_helper: NativeHelperProtocol,
) -> BrokerSessionClient:
    """Authenticate one pidfd-preregistered claimant using only a sealed FD."""

    actor = dict(broker_actor)
    if (
        set(actor)
        != {"schema_version", "pid", "pid_starttime", "uid"}
        or actor["schema_version"] != ACTOR_SCHEMA
    ):
        raise BrokerProtocolError(
            "BROKER_ACTOR_IDENTITY_DRIFT",
            "formal-launch claimant broker actor shape differs",
        )
    nonce = _nonce(broker_nonce)
    claim = _claim_identity(
        claim_identity,
        label="formal-launch claimant identity",
    )
    expected_peer = process_identity()
    grant = BrokerSessionGrant(
        role="formal-launch-claimant",
        credential_sha256=cast(str, claim["sha256"]),
        expected_peer=expected_peer,
        arm_slot=None,
        selection_identity=None,
        allocation_identity=None,
    )
    connection = _consume_socket_descriptor(
        descriptor,
        label="formal-launch claimant socket",
    )
    try:
        _socket_type(connection)
        peer = _peer_identity(connection)
        if (
            {
                key: peer[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            != {
                key: actor[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            or peer["gid"] != os.getgid()
        ):
            raise BrokerProtocolError(
                "BROKER_ACTOR_IDENTITY_DRIFT",
                "formal-launch claimant socket peer is not the broker",
            )
        send_frame(
            connection,
            {
                "claim_identity": claim,
                "nonce": nonce,
                "role": "formal-launch-claimant",
                "schema_version": (
                    FORMAL_LAUNCH_OWNER_CLAIM_AUTHENTICATION_SCHEMA
                ),
            },
            descriptors=(claim_descriptor,),
        )
        ready = receive_frame(connection)
        result = ready.record.get("result")
        if (
            ready.record.get("schema_version") != RESPONSE_SCHEMA
            or ready.record.get("action") != "READY"
            or ready.record.get("status") != "PASS"
            or ready.record.get("actor") != actor
            or ready.record.get("nonce") != nonce
            or ready.record.get("sequence") != 0
            or type(result) is not dict
            or result.get("session_grant") != grant.as_record()
        ):
            raise BrokerProtocolError(
                "READY_IDENTITY_DRIFT",
                "formal-launch claimant broker READY differs",
            )
        return BrokerSessionClient(
            connection=connection,
            nonce=nonce,
            actor=actor,
            grant=grant,
            native_helper=native_helper,
        )
    except BaseException:
        connection.close()
        raise


def attach_registered_nonarm_session(
    descriptor: int,
    *,
    broker_actor: Mapping[str, object],
    broker_nonce: str,
    credential: str,
    role: str,
    native_helper: NativeHelperProtocol,
) -> BrokerSessionClient:
    """Authenticate one direct child connection after a pidfd-bound grant."""

    if role not in {
        "formal-closeout-owner",
        "formal-launch-owner",
        "formal-supervisor",
        "formal-worker",
    }:
        raise BrokerProtocolError(
            "GRANT_SCOPE_DRIFT",
            "direct non-arm session role is invalid",
        )
    actor = dict(broker_actor)
    if (
        set(actor)
        != {"schema_version", "pid", "pid_starttime", "uid"}
        or actor["schema_version"] != ACTOR_SCHEMA
    ):
        raise BrokerProtocolError(
            "BROKER_ACTOR_IDENTITY_DRIFT",
            "direct non-arm broker actor shape differs",
        )
    expected_peer = process_identity()
    grant = build_session_grant(
        credential=credential,
        expected_peer=expected_peer,
        role=role,
    )
    connection = _consume_socket_descriptor(
        descriptor,
        label="direct non-arm socket",
    )
    try:
        _socket_type(connection)
        peer = _peer_identity(connection)
        if (
            {
                key: peer[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            != {
                key: actor[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            or peer["gid"] != os.getgid()
        ):
            raise BrokerProtocolError(
                "BROKER_ACTOR_IDENTITY_DRIFT",
                "direct non-arm socket peer is not the selected broker",
            )
        nonce = _nonce(broker_nonce)
        send_frame(
            connection,
            {
                "schema_version": AUTHENTICATION_SCHEMA,
                "allocation_identity": None,
                "arm_slot": None,
                "credential": _nonce(credential),
                "nonce": nonce,
                "role": role,
                "selection_identity": None,
            },
        )
        ready = receive_frame(connection)
        result = ready.record.get("result")
        grant_record = (
            result.get("session_grant")
            if type(result) is dict
            else None
        )
        if (
            ready.record.get("schema_version") != RESPONSE_SCHEMA
            or ready.record.get("action") != "READY"
            or ready.record.get("status") != "PASS"
            or ready.record.get("actor") != actor
            or ready.record.get("nonce") != nonce
            or ready.record.get("sequence") != 0
            or grant_record != grant.as_record()
        ):
            raise BrokerProtocolError(
                "READY_IDENTITY_DRIFT",
                "direct non-arm broker READY differs: "
                f"record={ready.record!r}; expected_grant={grant.as_record()!r}",
            )
        return BrokerSessionClient(
            connection=connection,
            nonce=nonce,
            actor=actor,
            grant=grant,
            native_helper=native_helper,
        )
    except BaseException:
        connection.close()
        raise


def attach_formal_owner_session(
    descriptor: int,
    *,
    handoff: Mapping[str, object],
    native_helper: NativeHelperProtocol,
    role: str,
) -> BrokerSessionClient:
    """Consume one package-mediated owner handoff from an already-open socket.

    The plaintext credential is intentionally a transport capability.  It is
    not a root artifact and the handoff validator requires the broker-issued
    grant hash and exact live peer binding before authentication.
    """

    expected_schema = {
        "formal-launch-owner": FORMAL_LAUNCH_OWNER_HANDOFF_SCHEMA,
        "formal-closeout-owner": FORMAL_CLOSEOUT_OWNER_HANDOFF_SCHEMA,
    }.get(role)
    if expected_schema is None:
        raise BrokerProtocolError(
            "GRANT_SCOPE_DRIFT",
            "formal owner handoff role is invalid",
        )
    _exact_keys(
        handoff,
        {
            "broker_actor",
            "broker_endpoint_identity",
            "broker_nonce",
            "credential",
            "formal_budget_runtime",
            "grant",
            "schema_version",
            "state",
            "transport_only",
        },
        label=f"{role} handoff",
    )
    grant = handoff["grant"]
    runtime = handoff["formal_budget_runtime"]
    endpoint = handoff["broker_endpoint_identity"]
    if (
        handoff["schema_version"] != expected_schema
        or handoff["state"] != "PREREGISTERED_LIVE_OWNER"
        or handoff["transport_only"] is not True
        or type(grant) is not dict
        or type(runtime) is not dict
        or type(endpoint) is not dict
        or grant.get("schema_version") != SESSION_GRANT_SCHEMA
        or grant.get("role") != role
        or grant.get("expected_peer") != process_identity()
        or grant.get("credential_sha256")
        != hashlib.sha256(
            _nonce(handoff["credential"]).encode("ascii")
        ).hexdigest()
        or runtime.get("broker_actor_identity")
        != {
            key: handoff["broker_actor"][key]
            for key in ("pid", "pid_starttime", "uid")
        }
        or runtime.get("broker_endpoint_identity") != endpoint
    ):
        raise BrokerProtocolError(
            "FORMAL_OWNER_HANDOFF_DRIFT",
            "formal owner handoff differs from its live broker grant",
        )
    return attach_registered_nonarm_session(
        descriptor,
        broker_actor=cast(Mapping[str, object], handoff["broker_actor"]),
        broker_nonce=cast(str, handoff["broker_nonce"]),
        credential=cast(str, handoff["credential"]),
        role=role,
        native_helper=native_helper,
    )


def attach_formal_closeout_owner_session(
    descriptor: int,
    *,
    handoff: Mapping[str, object],
    native_helper: NativeHelperProtocol,
) -> BrokerSessionClient:
    """Attach the supervisor-bound closeout owner on its distinct grant."""

    return attach_formal_owner_session(
        descriptor,
        handoff=handoff,
        native_helper=native_helper,
        role="formal-closeout-owner",
    )


def attach_registered_arm_session(
    descriptor: int,
    *,
    broker_actor: Mapping[str, object],
    broker_nonce: str,
    credential: str,
    role: str,
    arm_slot: str,
    selection_identity: Mapping[str, object],
    allocation_identity: Mapping[str, object],
    native_helper: NativeHelperProtocol,
) -> BrokerSessionClient:
    """Authenticate one direct arm connection after its pidfd-bound grant."""

    if role not in {"arm", "arm-authority", "arm-supervisor"}:
        raise BrokerProtocolError(
            "GRANT_SCOPE_DRIFT",
            "direct arm session role is invalid",
        )
    actor = dict(broker_actor)
    if (
        set(actor)
        != {"schema_version", "pid", "pid_starttime", "uid"}
        or actor["schema_version"] != ACTOR_SCHEMA
    ):
        raise BrokerProtocolError(
            "BROKER_ACTOR_IDENTITY_DRIFT",
            "direct arm broker actor shape differs",
        )
    expected_peer = process_identity()
    grant = build_session_grant(
        credential=credential,
        expected_peer=expected_peer,
        role=role,
        arm_slot=arm_slot,
        selection_identity=selection_identity,
        allocation_identity=allocation_identity,
    )
    connection = _consume_socket_descriptor(
        descriptor,
        label="direct arm socket",
    )
    try:
        _socket_type(connection)
        peer = _peer_identity(connection)
        if (
            {
                key: peer[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            != {
                key: actor[key]
                for key in ("pid", "pid_starttime", "uid")
            }
            or peer["gid"] != os.getgid()
        ):
            raise BrokerProtocolError(
                "BROKER_ACTOR_IDENTITY_DRIFT",
                "direct arm socket peer is not the selected broker",
            )
        nonce = _nonce(broker_nonce)
        send_frame(
            connection,
            {
                "schema_version": AUTHENTICATION_SCHEMA,
                "allocation_identity": grant.allocation_identity,
                "arm_slot": grant.arm_slot,
                "credential": _nonce(credential),
                "nonce": nonce,
                "role": role,
                "selection_identity": grant.selection_identity,
            },
        )
        ready = receive_frame(connection)
        result = ready.record.get("result")
        grant_record = (
            result.get("session_grant")
            if type(result) is dict
            else None
        )
        if (
            ready.record.get("schema_version") != RESPONSE_SCHEMA
            or ready.record.get("action") != "READY"
            or ready.record.get("status") != "PASS"
            or ready.record.get("actor") != actor
            or ready.record.get("nonce") != nonce
            or ready.record.get("sequence") != 0
            or grant_record != grant.as_record()
        ):
            raise BrokerProtocolError(
                "READY_IDENTITY_DRIFT",
                "direct arm broker READY differs",
            )
        return BrokerSessionClient(
            connection=connection,
            nonce=nonce,
            actor=actor,
            grant=grant,
            native_helper=native_helper,
        )
    except BaseException:
        connection.close()
        raise


def _open_absolute_directory_no_symlinks(path: Path) -> int:
    absolute = Path(os.path.abspath(path))
    if not absolute.is_absolute():
        raise BrokerProtocolError(
            "ENDPOINT_PATH_INVALID",
            "broker endpoint parent is not absolute",
        )
    descriptor = os.open(
        "/",
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        for component in absolute.parts[1:]:
            successor = os.open(
                component,
                os.O_RDONLY
                | os.O_CLOEXEC
                | os.O_DIRECTORY
                | os.O_NOFOLLOW,
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = successor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class PersistentBrokerProcess:
    """Handle for the package-authorized persistent broker owner."""

    def __init__(
        self,
        *,
        pid: int,
        pidfd: int,
        pidfd_method: str,
        actor: Mapping[str, object],
        endpoint_identity: Mapping[str, object],
        retired_endpoint_path: str,
        selected_fd_transport: Mapping[str, object],
        nonce: str,
        native_helper: NativeHelperProtocol | None,
        bootstrap_admin_credential: str | None = None,
    ) -> None:
        checked_actor = dict(actor)
        checked_endpoint_identity = dict(endpoint_identity)
        checked_selected_fd_transport = dict(selected_fd_transport)
        retired_parent = Path(retired_endpoint_path).parent
        retired_parent_fd = -1
        try:
            retired_parent_fd = _open_absolute_directory_no_symlinks(
                retired_parent
            )
            retired_parent_identity = _parent_identity(retired_parent_fd)
        except BaseException as exc:
            if retired_parent_fd >= 0:
                owned_retired_parent_fd = retired_parent_fd
                retired_parent_fd = -1
                preserve_spawn_cleanup_failure(
                    exc,
                    label="persistent broker retired-parent descriptor",
                    cleanup=lambda: os.close(owned_retired_parent_fd),
                )
            raise
        self.pid = pid
        self.pidfd = pidfd
        self.pidfd_method = pidfd_method
        self.actor = checked_actor
        self.endpoint_identity = checked_endpoint_identity
        self.retired_endpoint_path = retired_endpoint_path
        self._retired_parent_fd = retired_parent_fd
        self._retired_parent_identity = retired_parent_identity
        self.selected_fd_transport = checked_selected_fd_transport
        self.nonce = nonce
        self.native_helper = native_helper
        self._bootstrap_admin_credential = bootstrap_admin_credential
        self._waited = False
        self._unattached_termination_attempted = False

    def connect_bootstrap_admin(self) -> BrokerSessionClient:
        """Consume the bootstrap-only credential exactly once."""

        credential = self._bootstrap_admin_credential
        if credential is None:
            raise BrokerProtocolError(
                "CREDENTIAL_ALREADY_CONSUMED_OR_UNKNOWN",
                "bootstrap admin credential is absent or already consumed",
            )
        self._bootstrap_admin_credential = None
        return self.connect(
            credential=credential,
            role="bootstrap-admin",
        )

    def connect(
        self,
        *,
        credential: str,
        role: str,
        arm_slot: str | None = None,
        selection_identity: Mapping[str, object] | None = None,
        allocation_identity: Mapping[str, object] | None = None,
    ) -> BrokerSessionClient:
        expected_peer = process_identity()
        grant = build_session_grant(
            credential=credential,
            expected_peer=expected_peer,
            role=role,
            arm_slot=arm_slot,
            selection_identity=selection_identity,
            allocation_identity=allocation_identity,
        )
        endpoint = Path(cast(str, self.endpoint_identity["path"]))
        parent_fd = _open_absolute_directory_no_symlinks(endpoint.parent)
        connection = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
        )
        try:
            connection.connect(f"/proc/self/fd/{parent_fd}/{endpoint.name}")
            send_frame(
                connection,
                {
                    "schema_version": AUTHENTICATION_SCHEMA,
                    "allocation_identity": grant.allocation_identity,
                    "arm_slot": grant.arm_slot,
                    "credential": _nonce(credential),
                    "nonce": self.nonce,
                    "role": grant.role,
                    "selection_identity": grant.selection_identity,
                },
            )
            ready = receive_frame(connection)
            record = ready.record
            failure_result = record.get("result")
            failure_message = (
                cast(dict[str, object], failure_result).get("message")
                if type(failure_result) is dict
                else None
            )
            if (
                record.get("schema_version") == RESPONSE_SCHEMA
                and record.get("action") == "FAIL_CLOSED"
                and record.get("status") == "FAIL_CLOSED"
                and record.get("actor") == self.actor
                and record.get("nonce") == self.nonce
                and record.get("sequence") == 0
                and isinstance(record.get("code"), str)
                and isinstance(failure_message, str)
            ):
                raise BrokerProtocolError(
                    cast(str, record["code"]),
                    failure_message,
                )
            if (
                record.get("schema_version") != RESPONSE_SCHEMA
                or record.get("action") != "READY"
                or record.get("status") != "PASS"
                or record.get("actor") != self.actor
                or record.get("nonce") != self.nonce
                or record.get("sequence") != 0
                or record.get("result")
                != {
                    "session_grant": grant.as_record(),
                    "state": "READY",
                }
            ):
                raise BrokerProtocolError(
                    "READY_IDENTITY_DRIFT",
                    "persistent broker session READY differs",
                )
            return BrokerSessionClient(
                connection=connection,
                nonce=self.nonce,
                actor=self.actor,
                grant=grant,
                native_helper=self.native_helper,
            )
        except BaseException:
            connection.close()
            raise
        finally:
            os.close(parent_fd)

    def wait(self) -> int:
        if self._waited:
            raise BrokerProtocolError(
                "PROCESS_ALREADY_WAITED",
                "persistent broker cannot be waited twice",
            )
        _pid, status = os.waitpid(self.pid, 0)
        self._waited = True
        if os.WIFEXITED(status):
            result = os.WEXITSTATUS(status)
        else:
            result = 128 + os.WTERMSIG(status)
        if result == 0:
            current_parent_fd = -1
            try:
                if (
                    _parent_identity(self._retired_parent_fd)
                    != self._retired_parent_identity
                ):
                    raise BrokerProtocolError(
                        "ENDPOINT_RETIREMENT_FAILED",
                        "persistent broker retained endpoint parent drifted",
                    )
                retired_path = Path(self.retired_endpoint_path)
                current_parent_fd = (
                    _open_absolute_directory_no_symlinks(
                        retired_path.parent
                    )
                )
                if (
                    _parent_identity(current_parent_fd)
                    != self._retired_parent_identity
                ):
                    raise BrokerProtocolError(
                        "ENDPOINT_RETIREMENT_FAILED",
                        "persistent broker endpoint parent path drifted",
                    )
                retired = os.stat(
                    retired_path.name,
                    dir_fd=self._retired_parent_fd,
                    follow_symlinks=False,
                )
                if (
                    not stat.S_ISSOCK(retired.st_mode)
                    or retired.st_dev != self.endpoint_identity["device"]
                    or retired.st_ino != self.endpoint_identity["inode"]
                    or stat.S_IMODE(retired.st_mode) != 0o600
                ):
                    raise BrokerProtocolError(
                        "ENDPOINT_RETIREMENT_FAILED",
                        "persistent broker retired endpoint differs",
                    )
            except OSError as exc:
                raise BrokerProtocolError(
                    "ENDPOINT_RETIREMENT_FAILED",
                    "persistent broker endpoint retirement cannot be verified",
                ) from exc
            finally:
                if current_parent_fd >= 0:
                    os.close(current_parent_fd)
        return result

    def terminate_unattached(
        self,
        *,
        timeout_milliseconds: int = 5000,
    ) -> dict[str, object]:
        """Terminate and reap a spawned broker before any owner attached.

        The pidfd is the signaling authority.  This exact-once path is only
        for bootstrap failure between successful spawn and owner-session
        attachment; it never scans or signals unrelated processes.
        """

        if (
            self._unattached_termination_attempted
            or self._waited
            or isinstance(timeout_milliseconds, bool)
            or not isinstance(timeout_milliseconds, int)
            or timeout_milliseconds <= 0
        ):
            raise BrokerProtocolError(
                "UNATTACHED_TERMINATION_STATE_INVALID",
                "unattached broker termination is duplicate or malformed",
            )
        self._unattached_termination_attempted = True
        self._bootstrap_admin_credential = None
        primary: BaseException | None = None
        signal_method: str | None = None
        escalated = False
        status: int | None = None
        try:
            signal_method = pidfd_send_signal(self.pidfd, signal.SIGTERM)
            poller = __import__("select").poll()
            poller.register(
                self.pidfd,
                __import__("select").POLLIN
                | __import__("select").POLLHUP,
            )
            if not poller.poll(timeout_milliseconds):
                escalated = True
                pidfd_send_signal(self.pidfd, signal.SIGKILL)
                if not poller.poll(timeout_milliseconds):
                    raise BrokerProtocolError(
                        "UNATTACHED_BROKER_EXIT_TIMEOUT",
                        "unattached broker pidfd did not report terminal exit",
                    )
            reaped_pid, status = os.waitpid(self.pid, 0)
            self._waited = True
            if (
                reaped_pid != self.pid
                or status is None
                or not (
                    os.WIFEXITED(status)
                    or os.WIFSIGNALED(status)
                )
                or not pidfd_reports_exit(self.pidfd)
            ):
                raise BrokerProtocolError(
                    "UNATTACHED_BROKER_REAP_DRIFT",
                    "unattached broker did not reach one exact terminal state",
                )
        except BaseException as exc:
            primary = exc
            # This PID is still our unreaped child, so it cannot be reused.
            # Force one terminal state and perform a blocking exact reap even
            # when the preferred pidfd signal or poll path failed.  Never
            # hide the original exception.
            if not self._waited:
                try:
                    try:
                        pidfd_send_signal(
                            self.pidfd,
                            signal.SIGKILL,
                        )
                    except BaseException as pidfd_cleanup_error:
                        try:
                            os.kill(self.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        except BaseException as kill_error:
                            pidfd_cleanup_error.add_note(
                                "exact-child SIGKILL fallback also failed: "
                                f"{type(kill_error).__name__}: {kill_error}"
                            )
                        primary.add_note(
                            "pidfd SIGKILL cleanup also failed: "
                            f"{type(pidfd_cleanup_error).__name__}: "
                            f"{pidfd_cleanup_error}"
                        )
                    reaped_pid, observed_status = os.waitpid(self.pid, 0)
                    if reaped_pid != self.pid:
                        raise BrokerProtocolError(
                            "UNATTACHED_BROKER_REAP_DRIFT",
                            "cleanup reaped a different child",
                        )
                    self._waited = True
                    status = observed_status
                except BaseException as cleanup_error:
                    primary.add_note(
                        "unattached broker reap also failed: "
                        f"{type(cleanup_error).__name__}: {cleanup_error}"
                    )
        try:
            self.close()
        except BaseException as cleanup_error:
            if primary is None:
                primary = cleanup_error
            else:
                primary.add_note(
                    "unattached broker descriptor cleanup also failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        if primary is not None:
            raise primary
        assert status is not None and signal_method is not None
        return {
            "escalated_to_sigkill": escalated,
            "pid": self.pid,
            "pidfd_exit_proved": True,
            "signal_method": signal_method,
            "state": "UNATTACHED_BROKER_TERMINATED_AND_REAPED",
            "terminal_status": (
                {
                    "kind": "exit",
                    "value": os.WEXITSTATUS(status),
                }
                if os.WIFEXITED(status)
                else {
                    "kind": "signal",
                    "value": os.WTERMSIG(status),
                }
            ),
        }

    def close(self) -> None:
        primary: BaseException | None = None
        for attribute in ("pidfd", "_retired_parent_fd"):
            descriptor = cast(int, getattr(self, attribute))
            if descriptor < 0:
                continue
            setattr(self, attribute, -1)
            try:
                os.close(descriptor)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        f"{attribute} close also failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
        if primary is not None:
            raise primary


def _persistent_session(
    connection: socket.socket,
    *,
    account: budget.FormalBudgetBroker,
    runtime: _SharedBrokerRuntime,
    native_helper: NativeHelperProtocol | None,
    formal_directories: Sequence[Mapping[str, object]],
    arm_directories: Mapping[str, Sequence[Mapping[str, object]]],
    fixed_reservations: dict[str, budget.RetainedStagingReservation],
    final_release_parent_capability: FinalReleaseParentCapability,
    package_authorization: PackageRoleAuthorizationProtocol,
) -> None:
    frame: ReceivedFrame | None = None
    try:
        frame = receive_frame(
            connection,
            expected_fd_counts=frozenset({0, 1}),
        )
        manager_ready_record: dict[str, object] | None = None
        if (
            frame.record.get("schema_version")
            == MANAGER_OPENFILE_AUTHENTICATION_SCHEMA
        ):
            if frame.descriptors:
                raise BrokerProtocolError(
                    "FD_COUNT_MISMATCH",
                    "manager OpenFile authentication carried a descriptor",
                )
            grant, manager_ready_record = (
                runtime.authenticate_manager_openfile(frame)
            )
        elif (
            frame.record.get("schema_version")
            == MANAGER_OPENFILE_ARM_AUTHENTICATION_SCHEMA
        ):
            if frame.descriptors:
                raise BrokerProtocolError(
                    "FD_COUNT_MISMATCH",
                    "manager arm authentication carried a descriptor",
                )
            grant, manager_ready_record = (
                runtime.authenticate_manager_openfile_arm(frame)
            )
        elif (
            frame.record.get("schema_version")
            == FORMAL_LAUNCH_OWNER_CLAIM_AUTHENTICATION_SCHEMA
        ):
            if native_helper is None:
                raise BrokerProtocolError(
                    "NATIVE_HELPER_REQUIRED",
                    "formal-launch owner claim requires the package helper",
                )
            grant = runtime.authenticate_formal_launch_claim(
                frame,
                native_helper=native_helper,
            )
        else:
            if frame.descriptors:
                raise BrokerProtocolError(
                    "FD_COUNT_MISMATCH",
                    "ordinary broker authentication carried a descriptor",
                )
            grant = runtime.authenticate(frame)
        server = BrokerServer(
            connection,
            nonce=runtime.nonce,
            expected_peer=frame.peer,
            native_helper=native_helper,
            formal_directories=formal_directories,
            arm_directories=arm_directories,
            account=account,
            actor=runtime.actor,
            runtime=runtime,
            session_grant=grant,
            fixed_reservations=fixed_reservations,
            final_release_parent_capability=(
                final_release_parent_capability
            ),
            package_authorization=package_authorization,
            manager_ready_record=manager_ready_record,
            close_account_on_exit=False,
        )
        if server.run() != 0:
            raise BrokerProtocolError(
                "SESSION_FAILED_CLOSED",
                "persistent broker session failed closed",
            )
    except BaseException as exc:
        runtime.fatal_error = exc
        runtime.exit_requested.set()
        if frame is not None:
            try:
                send_frame(
                    connection,
                    {
                        "schema_version": RESPONSE_SCHEMA,
                        "action": "FAIL_CLOSED",
                        "actor": dict(runtime.actor),
                        "code": getattr(exc, "code", type(exc).__name__),
                        "journal": None,
                        "nonce": runtime.nonce,
                        "result": {"message": str(exc)},
                        "sequence": 0,
                        "status": "FAIL_CLOSED",
                    },
                )
            except BaseException:
                pass
    finally:
        connection.close()


def _run_persistent_owner(
    *,
    account: budget.FormalBudgetBroker,
    nonce: str,
    supervisor_grant: BrokerSessionGrant,
    native_helper_authorization: NativeHelperAuthorizationProtocol,
    formal_directories: Sequence[Mapping[str, object]],
    arm_directories: Mapping[str, Sequence[Mapping[str, object]]],
    fixed_reservations: dict[str, budget.RetainedStagingReservation],
    final_release_parent_capability: FinalReleaseParentCapability,
    control_parent: budget.RetainedDirectoryCapability,
    endpoint_path: Path,
    retired_endpoint_path: Path,
    bootstrap_handoff_spec: Mapping[str, object],
    bootstrap_handoff_base: Mapping[str, object],
    bootstrap_failure_closeout_path: Path,
    ready_control: socket.socket,
    package_authorization: PackageRoleAuthorizationProtocol,
    formal_artifact_contracts: Sequence[Mapping[str, object]],
    formal_append_contracts: Sequence[Mapping[str, object]],
    arm_artifact_contracts: Mapping[
        str, Mapping[str, Mapping[str, object]]
    ],
    arm_append_contracts: Mapping[
        str, Sequence[Mapping[str, object]]
    ],
) -> int:
    endpoint: _BoundBrokerEndpoint | None = None
    runtime: _SharedBrokerRuntime | None = None
    account_closed = False
    package_authorization_close_attempted = False
    native_helper_authorization_close_attempted = False
    actor = {
        "schema_version": ACTOR_SCHEMA,
        **process_identity(),
    }
    try:
        native_helper = native_helper_authorization.helper
        retained_native_helper_descriptors = (
            native_helper_authorization.retained_descriptors()
        )
        retained_package_descriptors = (
            package_authorization.retained_descriptors()
        )
        all_authorization_descriptors = (
            *retained_package_descriptors,
            *retained_native_helper_descriptors,
        )
        if (
            any(
                isinstance(descriptor, bool)
                or not isinstance(descriptor, int)
                or descriptor < 3
                for descriptor in all_authorization_descriptors
            )
            or len(set(all_authorization_descriptors))
            != len(all_authorization_descriptors)
        ):
            raise BrokerProtocolError(
                "PACKAGE_AUTHORIZATION_FD_SET_INVALID",
                "package and native-helper authorization FDs are not one disjoint fixed set",
            )
        for descriptor in all_authorization_descriptors:
            os.fstat(descriptor)
        selected_fd_transport = (
            package_authorization.selected_fd_transport()
        )
        endpoint = _BoundBrokerEndpoint(
            control_parent=control_parent,
            absolute_path=endpoint_path,
            retired_absolute_path=retired_endpoint_path,
        )
        runtime = _SharedBrokerRuntime(
            actor=actor,
            nonce=nonce,
            supervisor_grant=supervisor_grant,
            bootstrap_handoff_spec=bootstrap_handoff_spec,
            bootstrap_handoff_base={
                **dict(bootstrap_handoff_base),
                "broker_actor": actor,
                "broker_endpoint_identity": endpoint.endpoint_identity,
                "selected_fd_transport": selected_fd_transport,
            },
            bootstrap_failure_closeout_path=(
                bootstrap_failure_closeout_path
            ),
            control_endpoint_path=endpoint_path,
            retired_endpoint_path=retired_endpoint_path,
            formal_artifact_contracts=formal_artifact_contracts,
            formal_append_contracts=formal_append_contracts,
            arm_artifact_contracts=arm_artifact_contracts,
            arm_append_contracts=arm_append_contracts,
        )
        close_unlisted_descriptors(
            {
                ready_control.fileno(),
                account._root_fd,  # noqa: SLF001
                *endpoint.retained_descriptors(),
                *(
                    descriptor
                    for reservation in fixed_reservations.values()
                    for descriptor in (
                        reservation._parent_fd,  # noqa: SLF001
                        reservation.fileno(),
                    )
                ),
                *final_release_parent_capability.retained_descriptors(),
                *retained_package_descriptors,
                *retained_native_helper_descriptors,
            }
        )
        send_frame(
            ready_control,
            {
                "schema_version": RESPONSE_SCHEMA,
                "action": "OWNER_READY",
                "actor": actor,
                "journal": None,
                "nonce": nonce,
                "result": {
                    "endpoint_identity": endpoint.endpoint_identity,
                    "retired_endpoint_path": str(
                        endpoint.retired_absolute_path
                    ),
                    "selected_fd_transport": selected_fd_transport,
                },
                "sequence": 0,
                "status": "PASS",
            },
        )
        commit = receive_frame(ready_control)
        if commit.record != {
            "schema_version": REQUEST_SCHEMA,
            "action": "TRANSFER_COMMIT",
            "nonce": nonce,
            "payload": {},
            "sequence": 1,
        }:
            raise BrokerProtocolError(
                "TRANSFER_COMMIT_DRIFT",
                "persistent broker ownership transfer commit differs",
            )
        send_frame(
            ready_control,
            {
                "schema_version": RESPONSE_SCHEMA,
                "action": "TRANSFER_COMMIT",
                "actor": actor,
                "journal": None,
                "nonce": nonce,
                "result": {"state": "OWNERSHIP_ACCEPTED"},
                "sequence": 1,
                "status": "PASS",
            },
        )
        parent_released = receive_frame(ready_control)
        if parent_released.record != {
            "schema_version": REQUEST_SCHEMA,
            "action": "PARENT_RELEASED",
            "nonce": nonce,
            "payload": {},
            "sequence": 2,
        }:
            raise BrokerProtocolError(
                "PARENT_RELEASE_DRIFT",
                "persistent broker parent-release proof differs",
            )
        send_frame(
            ready_control,
            {
                "schema_version": RESPONSE_SCHEMA,
                "action": "PARENT_RELEASED",
                "actor": actor,
                "journal": None,
                "nonce": nonce,
                "result": {"state": "READY_FOR_SESSIONS"},
                "sequence": 2,
                "status": "PASS",
            },
        )
        ready_control.close()

        endpoint.settimeout(0.10)
        sessions: list[threading.Thread] = []
        while not runtime.exit_requested.is_set():
            try:
                connection = endpoint.accept()
            except TimeoutError:
                continue
            thread = threading.Thread(
                target=_persistent_session,
                kwargs={
                    "connection": connection,
                    "account": account,
                    "runtime": runtime,
                    "native_helper": native_helper,
                    "formal_directories": formal_directories,
                    "arm_directories": arm_directories,
                    "fixed_reservations": fixed_reservations,
                    "final_release_parent_capability": (
                        final_release_parent_capability
                    ),
                    "package_authorization": package_authorization,
                },
                daemon=False,
            )
            sessions.append(thread)
            thread.start()
        for thread in sessions:
            thread.join()
        if runtime.fatal_error is not None:
            raise runtime.fatal_error
        if fixed_reservations:
            raise BrokerProtocolError(
                "FIXED_RESERVATIONS_UNCONSUMED",
                "persistent broker cannot close with untransferred fixed reservations",
            )
        if not final_release_parent_capability._detached:  # noqa: SLF001
            raise BrokerProtocolError(
                "FINAL_RELEASE_CAPABILITY_UNCONSUMED",
                "persistent broker cannot close before final-release authority transfer",
            )
        endpoint.retire()
        endpoint = None
        account.close()
        account_closed = True
        package_authorization_close_attempted = True
        package_authorization.close()
        native_helper_authorization_close_attempted = True
        native_helper_authorization.close()
        return 0
    except BaseException:
        return 2
    finally:
        try:
            ready_control.close()
        except BaseException:
            pass
        if endpoint is not None:
            failure = BrokerProtocolError(
                "PERSISTENT_OWNER_INCOMPLETE",
                "persistent broker owner exited before endpoint retirement",
            )
            endpoint._close_descriptors_preserving(failure)  # noqa: SLF001
        if not account_closed:
            for purpose, reservation in tuple(
                fixed_reservations.items()
            ):
                try:
                    _seal_abandoned_reservation(
                        purpose,
                        reservation,
                        reason="persistent broker exited before transfer",
                    )
                except BaseException:
                    pass
                fixed_reservations.pop(purpose, None)
            if not final_release_parent_capability._detached:  # noqa: SLF001
                try:
                    final_release_parent_capability.close()
                except BaseException:
                    pass
            try:
                account.close()
            except BaseException:
                pass
        if runtime is not None:
            try:
                runtime.abandon_formal_launch_owner()
            except BaseException:
                pass
            try:
                runtime.abandon_recovery_handle()
            except BaseException:
                pass
            try:
                runtime.abandon_release_handles()
            except BaseException:
                pass
        if not package_authorization_close_attempted:
            package_authorization_close_attempted = True
            try:
                package_authorization.close()
            except BaseException:
                pass
        if not native_helper_authorization_close_attempted:
            native_helper_authorization_close_attempted = True
            try:
                native_helper_authorization.close()
            except BaseException:
                pass


def spawn_persistent_broker_from_transfer(
    *,
    account: budget.FormalBudgetBroker,
    ownership_handoff: Mapping[str, object],
    fixed_purpose_reservations: Mapping[
        str,
        budget.RetainedStagingReservation,
    ],
    fixed_purpose_handoffs: Mapping[str, Mapping[str, object]],
    control_parent_capability: budget.RetainedDirectoryCapability,
    control_parent_handoff: Mapping[str, object],
    final_release_parent_capability: FinalReleaseParentCapability,
    final_release_parent_handoff: Mapping[str, object],
    endpoint_path: Path,
    owner_nonce: str,
    package_authorization: PackageRoleAuthorizationProtocol,
    native_helper_authorization: NativeHelperAuthorizationProtocol,
    bootstrap_handoff_spec: Mapping[str, object],
    formal_root_budget_contract_identity: Mapping[str, object],
    formal_resource_calibration_bundle_identity: Mapping[str, object],
    resource_budget_profile_identity: Mapping[str, object],
    resource_calibration_authorization_bundles: Mapping[str, object],
    calibration_tool_content_identities: Mapping[
        str, Mapping[str, object]
    ],
    package_id: str,
    campaign_run_nonce: str,
    bootstrap_failure_closeout_path: Path,
    supervisor_credential: str | None = None,
    expected_supervisor_peer: Mapping[str, object] | None = None,
    formal_directories: Sequence[Mapping[str, object]] = (),
    arm_directories: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
    formal_artifact_contracts: Sequence[Mapping[str, object]] = (),
    formal_append_contracts: Sequence[Mapping[str, object]] = (),
    arm_artifact_contracts: Mapping[
        str, Mapping[str, Mapping[str, object]]
    ] | None = None,
    arm_append_contracts: Mapping[
        str, Sequence[Mapping[str, object]]
    ] | None = None,
) -> PersistentBrokerProcess:
    """Start a package-authorized owner without creating or copying a root.

    The bootstrap-provided authorization is consulted before any process or
    endpoint exists.  The parent closes its transferred account copy before
    the child acknowledges ownership; an uncertain acknowledgement is never
    retryable in the same root.
    """

    package_authorization.require_verified_role(PACKAGE_ROLE)
    native_helper = native_helper_authorization.helper
    session_nonce = _nonce(owner_nonce)
    checked_campaign_run_nonce = _campaign_run_nonce(
        campaign_run_nonce
    )
    checked_handoff_spec = _bootstrap_handoff_spec(
        bootstrap_handoff_spec
    )
    if (
        not isinstance(package_id, str)
        or len(package_id) != 64
        or any(character not in "0123456789abcdef" for character in package_id)
    ):
        raise BrokerProtocolError(
            "PACKAGE_IDENTITY_DRIFT",
            "persistent broker package ID is not one SHA-256",
        )
    checked_contract_identity = _require_detached_bytes(
        formal_root_budget_contract_identity,
        expected_path=(
            account.root / "formal-root-budget-contract.json"
        ),
        label="formal-root budget contract",
    )
    checked_calibration_identity = _detached_identity(
        formal_resource_calibration_bundle_identity,
        label="formal resource calibration authorization bundle",
    )
    if (
        type(resource_budget_profile_identity) is not dict
        or set(resource_budget_profile_identity)
        != {"mode", "path", "sha256", "size_bytes"}
    ):
        raise BrokerProtocolError(
            "RESOURCE_BUDGET_PROFILE_DRIFT",
            "resource budget profile identity shape differs",
        )
    checked_profile_identity = {
        "mode": resource_budget_profile_identity["mode"],
        **_detached_identity(
            {
                key: resource_budget_profile_identity[key]
                for key in ("path", "sha256", "size_bytes")
            },
            label="resource budget profile",
        ),
    }
    if checked_profile_identity["mode"] != 0o444:
        raise BrokerProtocolError(
            "RESOURCE_BUDGET_PROFILE_DRIFT",
            "resource budget profile mode differs",
        )
    checked_calibration_bundles = (
        _resource_calibration_authorization_bundles(
            resource_calibration_authorization_bundles
        )
    )
    if (
        checked_calibration_bundles["FORMAL_ORGANIC_ARM"]["identity"]
        != checked_calibration_identity
    ):
        raise BrokerProtocolError(
            "RESOURCE_CALIBRATION_BINDING_DRIFT",
            "formal calibration bundle differs from the complete stage cohort",
        )
    checked_calibration_tools = _calibration_tool_content_identities(
        calibration_tool_content_identities
    )
    raw_arm_artifact_contracts = (
        {} if arm_artifact_contracts is None else arm_artifact_contracts
    )
    raw_arm_append_contracts = (
        {} if arm_append_contracts is None else arm_append_contracts
    )
    _PublicationPolicyState(
        formal_artifacts=formal_artifact_contracts,
        formal_channels=formal_append_contracts,
        arm_artifacts=raw_arm_artifact_contracts,
        arm_channels=raw_arm_append_contracts,
    )
    validate_transferred_account(
        account,
        ownership_handoff,
        expected_owner_nonce=session_nonce,
    )
    transferred_reservations = dict(fixed_purpose_reservations)
    validate_transferred_reservations(
        account,
        transferred_reservations,
        fixed_purpose_handoffs,
        expected_owner_nonce=session_nonce,
    )
    absolute_endpoint = Path(os.path.abspath(endpoint_path))
    validate_transferred_control_parent(
        account,
        control_parent_capability,
        control_parent_handoff,
        expected_owner_nonce=session_nonce,
        endpoint_path=absolute_endpoint,
    )
    validate_transferred_final_release_parent(
        account,
        final_release_parent_capability,
        final_release_parent_handoff,
        expected_owner_nonce=session_nonce,
        expected_parent_path=final_release_parent_capability.path,
    )
    bootstrap_handoff_base = {
        "authority": dict(FALSE_AUTHORITY_BOUNDARY),
        "formal_account_handoff": dict(ownership_handoff),
        "formal_control_parent_handoff": dict(control_parent_handoff),
        "formal_final_release_parent_handoff": dict(
            final_release_parent_handoff
        ),
        "formal_reservation_handoffs": {
            purpose: dict(fixed_purpose_handoffs[purpose])
            for purpose in sorted(FIXED_PURPOSE_SPECS)
        },
        "formal_root_budget_contract_identity": (
            checked_contract_identity
        ),
        "formal_resource_calibration_bundle_identity": (
            checked_calibration_identity
        ),
        "resource_budget_profile_identity": checked_profile_identity,
        "resource_calibration_authorization_bundles": (
            checked_calibration_bundles
        ),
        "calibration_tool_content_identities": (
            checked_calibration_tools
        ),
        "package_id": package_id,
        "run_nonce": checked_campaign_run_nonce,
        "schema_version": BOOTSTRAP_HANDOFF_SCHEMA,
        "state": "PERSISTENT_BROKER_AND_RECOVERY_READY",
        "status": "PASS",
    }
    retired_endpoint = absolute_endpoint.with_name(
        f"{absolute_endpoint.name}.retired"
    )
    if (supervisor_credential is None) != (
        expected_supervisor_peer is None
    ):
        raise BrokerProtocolError(
            "GRANT_SCOPE_DRIFT",
            "legacy supervisor credential and peer must be supplied together",
        )
    bootstrap_admin_credential: str | None
    if supervisor_credential is None:
        bootstrap_admin_credential = secrets.token_hex(32)
        supervisor_grant = build_session_grant(
            credential=bootstrap_admin_credential,
            expected_peer=process_identity(),
            role="bootstrap-admin",
        )
    else:
        bootstrap_admin_credential = None
        supervisor_grant = build_session_grant(
            credential=supervisor_credential,
            expected_peer=cast(
                Mapping[str, object],
                expected_supervisor_peer,
            ),
            role="supervisor",
        )
    raw_arm_directories = (
        {}
        if arm_directories is None
        else {
            str(slot): tuple(directories)
            for slot, directories in arm_directories.items()
        }
    )
    parent, child = socket.socketpair(
        socket.AF_UNIX,
        socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
    )
    parent_release_attempted = False

    def release_parent_copies() -> None:
        nonlocal parent_release_attempted
        if parent_release_attempted:
            raise BrokerProtocolError(
                "PARENT_RELEASE_ALREADY_ATTEMPTED",
                "persistent broker parent copies cannot be released twice",
            )
        parent_release_attempted = True
        primary: BaseException | None = None
        closers: list[tuple[str, object]] = [
            ("formal account", account.close),
            *[
                (
                    f"{purpose} reservation",
                    reservation.close,
                )
                for purpose, reservation in sorted(
                    transferred_reservations.items()
                )
            ],
            ("control parent", control_parent_capability.close),
            (
                "outside final-release parent",
                final_release_parent_capability.release_parent_copy,
            ),
            ("package authorization", package_authorization.close),
            (
                "native-helper authorization",
                native_helper_authorization.close,
            ),
        ]
        for label, raw_closer in closers:
            closer = cast(Any, raw_closer)
            try:
                closer()
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

    pid = os.fork()
    if pid == 0:
        parent.close()
        code = _run_persistent_owner(
            account=account,
            nonce=session_nonce,
            supervisor_grant=supervisor_grant,
            native_helper_authorization=native_helper_authorization,
            formal_directories=tuple(formal_directories),
            arm_directories=raw_arm_directories,
            fixed_reservations=transferred_reservations,
            final_release_parent_capability=(
                final_release_parent_capability
            ),
            control_parent=control_parent_capability,
            endpoint_path=absolute_endpoint,
            retired_endpoint_path=retired_endpoint,
            bootstrap_handoff_spec=checked_handoff_spec,
            bootstrap_handoff_base=bootstrap_handoff_base,
            bootstrap_failure_closeout_path=Path(
                os.path.abspath(bootstrap_failure_closeout_path)
            ),
            ready_control=child,
            package_authorization=package_authorization,
            formal_artifact_contracts=tuple(
                dict(item) for item in formal_artifact_contracts
            ),
            formal_append_contracts=tuple(
                dict(item) for item in formal_append_contracts
            ),
            arm_artifact_contracts={
                slot: {
                    label: dict(record)
                    for label, record in contracts.items()
                }
                for slot, contracts in raw_arm_artifact_contracts.items()
            },
            arm_append_contracts={
                slot: tuple(dict(record) for record in contracts)
                for slot, contracts in raw_arm_append_contracts.items()
            },
        )
        os._exit(code)
    child_close_attempted = False
    parent_close_attempted = False
    pidfd = -1
    pidfd_method = ""
    try:
        child_close_attempted = True
        child.close()
        pidfd, pidfd_method = open_pidfd(pid)
        ready = receive_frame(parent)
        actor = ready.record.get("actor")
        result = ready.record.get("result")
        if (
            ready.record.get("schema_version") != RESPONSE_SCHEMA
            or ready.record.get("action") != "OWNER_READY"
            or ready.record.get("status") != "PASS"
            or ready.record.get("nonce") != session_nonce
            or ready.record.get("sequence") != 0
            or type(actor) is not dict
            or actor.get("pid") != pid
            or actor.get("pid_starttime") != process_starttime(pid)
            or actor.get("uid") != os.getuid()
            or type(result) is not dict
            or set(result)
            != {
                "endpoint_identity",
                "retired_endpoint_path",
                "selected_fd_transport",
            }
        ):
            raise BrokerProtocolError(
                "READY_IDENTITY_DRIFT",
                "persistent broker owner READY differs",
            )
        endpoint_identity = result["endpoint_identity"]
        if (
            type(endpoint_identity) is not dict
            or set(endpoint_identity)
            != {"device", "inode", "mode", "path", "uid"}
            or endpoint_identity["mode"] != 0o600
            or endpoint_identity["uid"] != os.getuid()
        ):
            raise BrokerProtocolError(
                "ENDPOINT_IDENTITY_DRIFT",
                "persistent broker endpoint identity differs",
            )
        send_frame(
            parent,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "TRANSFER_COMMIT",
                "nonce": session_nonce,
                "payload": {},
                "sequence": 1,
            },
        )
        committed = receive_frame(parent)
        if committed.record != {
            "schema_version": RESPONSE_SCHEMA,
            "action": "TRANSFER_COMMIT",
            "actor": actor,
            "journal": None,
            "nonce": session_nonce,
            "result": {"state": "OWNERSHIP_ACCEPTED"},
            "sequence": 1,
            "status": "PASS",
        }:
            raise BrokerProtocolError(
                "TRANSFER_COMMIT_DRIFT",
                "persistent broker ownership acknowledgement differs",
            )
        release_parent_copies()
        send_frame(
            parent,
            {
                "schema_version": REQUEST_SCHEMA,
                "action": "PARENT_RELEASED",
                "nonce": session_nonce,
                "payload": {},
                "sequence": 2,
            },
        )
        released = receive_frame(parent)
        if released.record != {
            "schema_version": RESPONSE_SCHEMA,
            "action": "PARENT_RELEASED",
            "actor": actor,
            "journal": None,
            "nonce": session_nonce,
            "result": {"state": "READY_FOR_SESSIONS"},
            "sequence": 2,
            "status": "PASS",
        }:
            raise BrokerProtocolError(
                "PARENT_RELEASE_DRIFT",
                "persistent broker parent-release acknowledgement differs",
            )
        parent_close_attempted = True
        parent.close()
        process = PersistentBrokerProcess(
            pid=pid,
            pidfd=pidfd,
            pidfd_method=pidfd_method,
            actor=cast(Mapping[str, object], actor),
            endpoint_identity=cast(Mapping[str, object], endpoint_identity),
            retired_endpoint_path=cast(str, result["retired_endpoint_path"]),
            selected_fd_transport=cast(
                Mapping[str, object],
                result["selected_fd_transport"],
            ),
            nonce=session_nonce,
            native_helper=native_helper,
            bootstrap_admin_credential=bootstrap_admin_credential,
        )
        pidfd = -1
        return process
    except BaseException as exc:
        if not child_close_attempted:
            child_close_attempted = True
            preserve_spawn_cleanup_failure(
                exc,
                label="persistent broker child socket",
                cleanup=child.close,
            )
        if not parent_close_attempted:
            parent_close_attempted = True
            preserve_spawn_cleanup_failure(
                exc,
                label="persistent broker parent control",
                cleanup=parent.close,
            )
        if not parent_release_attempted:
            preserve_spawn_cleanup_failure(
                exc,
                label="persistent broker parent capabilities",
                cleanup=release_parent_copies,
            )
        terminate_and_reap_spawned_child(pid, primary=exc)
        if pidfd >= 0:
            owned_pidfd = pidfd
            pidfd = -1
            preserve_spawn_cleanup_failure(
                exc,
                label="persistent broker pidfd",
                cleanup=lambda: os.close(owned_pidfd),
            )
        raise


def spawn_broker_for_test(
    root: Path | str,
    *,
    category_limits: Mapping[str, object],
    nonce: str | None = None,
    native_helper: NativeHelperProtocol | None = None,
    formal_directories: Sequence[Mapping[str, object]] = (),
    arm_directories: Mapping[str, Sequence[Mapping[str, object]]] | None = None,
) -> BrokerProcess:
    """Fork the role for zero-authority focused tests; not a formal launcher."""

    session_nonce = secrets.token_hex(32) if nonce is None else _nonce(nonce)
    parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
    expected_peer = process_identity()
    pid = os.fork()
    if pid == 0:
        parent.close()
        code = 2
        try:
            server = BrokerServer(
                child,
                root=Path(root),
                category_limits=category_limits,
                nonce=session_nonce,
                expected_peer=expected_peer,
                native_helper=native_helper,
                formal_directories=formal_directories,
                arm_directories=arm_directories,
            )
            close_unlisted_descriptors({child.fileno(), server.account._root_fd})  # noqa: SLF001
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
    pidfd = -1
    pidfd_method = ""
    try:
        child_close_attempted = True
        child.close()
        pidfd, pidfd_method = open_pidfd(pid)
        ready = receive_frame(parent)
        record = ready.record
        if (
            record.get("schema_version") != RESPONSE_SCHEMA
            or record.get("action") != "READY"
            or record.get("status") != "PASS"
            or record.get("nonce") != session_nonce
            or record.get("sequence") != 0
        ):
            raise BrokerProtocolError("READY_IDENTITY_DRIFT", "broker READY response drifted")
        actor = record.get("actor")
        if type(actor) is not dict or actor.get("pid") != pid or actor.get("pid_starttime") != process_starttime(pid):
            raise BrokerProtocolError("READY_IDENTITY_DRIFT", "broker actor identity drifted")
        process = BrokerProcess(
            pid=pid,
            pidfd=pidfd,
            pidfd_method=pidfd_method,
            connection=parent,
            nonce=session_nonce,
            actor=dict(actor),
            native_helper=native_helper,
        )
        pidfd = -1
        return process
    except BaseException as exc:
        if not child_close_attempted:
            child_close_attempted = True
            preserve_spawn_cleanup_failure(
                exc,
                label="test broker child socket",
                cleanup=child.close,
            )
        if not parent_close_attempted:
            parent_close_attempted = True
            preserve_spawn_cleanup_failure(
                exc,
                label="test broker parent control",
                cleanup=parent.close,
            )
        terminate_and_reap_spawned_child(pid, primary=exc)
        if pidfd >= 0:
            owned_pidfd = pidfd
            pidfd = -1
            preserve_spawn_cleanup_failure(
                exc,
                label="test broker pidfd",
                cleanup=lambda: os.close(owned_pidfd),
            )
        raise


__all__ = [
    "ACTOR_SCHEMA",
    "AUTHENTICATION_SCHEMA",
    "BrokerProcess",
    "BrokerProtocolError",
    "BrokerServer",
    "BrokerSessionClient",
    "BrokerSessionGrant",
    "DEFAULT_RETIRED_SOCKET_RELATIVE_PATH",
    "DEFAULT_SOCKET_RELATIVE_PATH",
    "ENDPOINT_SCHEMA",
    "FORMAL_CLOSEOUT_OWNER_HANDOFF_SCHEMA",
    "FORMAL_LAUNCH_OWNER_HANDOFF_SCHEMA",
    "JOURNAL_SCHEMA",
    "MANAGER_OPENFILE_ARM_AUTHENTICATION_SCHEMA",
    "MANAGER_OPENFILE_ARM_GRANT_SCHEMA",
    "MANAGER_OPENFILE_AUTHENTICATION_SCHEMA",
    "MANAGER_OPENFILE_GRANT_SCHEMA",
    "MANAGER_OPENFILE_SELECTION_BINDING_SCHEMA",
    "NativeHelperAuthorizationProtocol",
    "NativeHelperProtocol",
    "PACKAGE_ROLE",
    "PackageRoleAuthorizationProtocol",
    "PREPARED_EXTENT_SCHEMA",
    "PreparedExtent",
    "PersistentBrokerProcess",
    "ReceivedFrame",
    "REQUEST_SCHEMA",
    "RESPONSE_SCHEMA",
    "SESSION_GRANT_SCHEMA",
    "build_session_grant",
    "attach_manager_openfile_arm_supervisor",
    "attach_manager_openfile_supervisor",
    "attach_formal_closeout_owner_session",
    "attach_formal_owner_session",
    "attach_registered_arm_session",
    "attach_registered_nonarm_session",
    "canonical_json_bytes",
    "close_unlisted_descriptors",
    "consume_once_extent",
    "pidfd_reports_exit",
    "open_pidfd",
    "preserve_spawn_cleanup_failure",
    "process_identity",
    "process_starttime",
    "receive_frame",
    "send_frame",
    "spawn_broker_for_test",
    "spawn_persistent_broker_from_transfer",
    "strict_canonical_object",
    "terminate_and_reap_spawned_child",
    "publish_preallocated_extent",
    "validate_prepared_extent",
]
