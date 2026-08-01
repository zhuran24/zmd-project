#!/usr/bin/env python3
"""Fail-closed hierarchical byte-budget primitives for a future AB16 cohort.

This module is deliberately not connected to the AB16 campaign launch path.  It
provides an unprivileged, no-overwrite substrate that a later package-pinned
broker can adopt.  A single formal-root account owns every byte.  Arm accounts
are non-refundable reservations from that root account, never independent
authorities.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import ctypes
from dataclasses import dataclass
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
import threading
from typing import Final, cast


BUDGET_CONTRACT_SCHEMA: Final = "noncert-cuts-ab16-budget-contract-v1"
BUDGET_CLOSURE_SCHEMA: Final = "noncert-cuts-ab16-budget-root-closure-v1"
PUBLISHED_ARTIFACT_SCHEMA: Final = "noncert-cuts-ab16-budget-published-artifact-v1"
BUDGET_RETAINED_STAGING_SCHEMA: Final = (
    "noncert-cuts-ab16-budget-retained-staging-v1"
)
BUDGET_RETAINED_DIRECTORY_SCHEMA: Final = (
    "noncert-cuts-ab16-budget-retained-directory-v1"
)
BUDGET_OWNERSHIP_HANDOFF_SCHEMA: Final = (
    "noncert-cuts-ab16-budget-ownership-handoff-v1"
)
EXPERIMENT_CONTRACT_SCHEMA: Final = "noncert-cuts-ab16-experiment-contract-v1"

ARTIFACT_CLASSES: Final = frozenset(
    {
        "closeout",
        "ledger",
        "metadata",
        "model",
        "normal",
        "publication",
        "scratch",
    }
)

FORMAL_MARKERLESS_INCOMPLETE: Final = "markerless-incomplete"
FORMAL_CONSUMED_INCOMPLETE: Final = "formal-consumed-incomplete"
ARM_UNSELECTED_TERMINAL: Final = "arm-allocation-unselected-terminal"
ARM_CONSUMED_INCOMPLETE: Final = "arm-consumed-incomplete"
CONSUMPTION_STATES: Final = frozenset(
    {
        FORMAL_MARKERLESS_INCOMPLETE,
        FORMAL_CONSUMED_INCOMPLETE,
        ARM_UNSELECTED_TERMINAL,
        ARM_CONSUMED_INCOMPLETE,
    }
)

_STAGING_PREFIX: Final = ".ab16-budget-stage-"
_RENAME_NOREPLACE: Final = 1
_READ_CHUNK_BYTES: Final = 1024 * 1024
_DIRECTORY_FLAGS: Final = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
_READ_FLAGS: Final = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
_WRITE_FLAGS: Final = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW


class BudgetContractError(RuntimeError):
    """A budget, topology, publication, or closure invariant failed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class PublishedArtifact:
    """The immutable result of one no-replace publication."""

    arm_slot: str | None
    artifact_class: str
    maximum_bytes: int
    path: str
    sha256: str
    size_bytes: int
    staging_name: str

    def as_record(self) -> dict[str, object]:
        return {
            "schema_version": PUBLISHED_ARTIFACT_SCHEMA,
            "arm_slot": self.arm_slot,
            "artifact_class": self.artifact_class,
            "maximum_bytes": self.maximum_bytes,
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "staging_name": self.staging_name,
        }


class RetainedStagingReservation:
    """One physically allocated hidden extent with a single live owner."""

    def __init__(
        self,
        *,
        root: Path,
        parent_fd: int,
        descriptor: int,
        staging_path: str,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None,
        purpose: str,
        owner_nonce: str,
    ) -> None:
        self.root = root
        self._parent_fd = parent_fd
        self._descriptor = descriptor
        self._staging_path = staging_path
        self._maximum_bytes = maximum_bytes
        self._artifact_class = artifact_class
        self._arm_slot = arm_slot
        self._purpose = purpose
        self._owner_nonce = owner_nonce
        self._closed = False
        self._lock = threading.RLock()

    def _require_open(self) -> None:
        if self._closed:
            raise BudgetContractError(
                "RESERVATION_CLOSED",
                "retained staging reservation no longer has an owner",
            )

    def fileno(self) -> int:
        with self._lock:
            self._require_open()
            return self._descriptor

    def record(self) -> dict[str, object]:
        with self._lock:
            self._require_open()
            metadata = os.fstat(self._descriptor)
            _verify_retained_staging(self._descriptor)
            if metadata.st_size != self._maximum_bytes:
                raise BudgetContractError(
                    "STAGING_IDENTITY_INVALID",
                    "retained staging extent size drifted",
                )
            return {
                "schema_version": BUDGET_RETAINED_STAGING_SCHEMA,
                "arm_slot": self._arm_slot,
                "artifact_class": self._artifact_class,
                "maximum_bytes": self._maximum_bytes,
                "owner_nonce": self._owner_nonce,
                "purpose": self._purpose,
                "root_path": str(self.root),
                "staging_path": self._staging_path,
                "staging_signature": list(_signature(metadata)),
            }

    @staticmethod
    def _close_pair(
        descriptor: int,
        parent_fd: int,
    ) -> BaseException | None:
        first_error: BaseException | None = None
        for owned in (descriptor, parent_fd):
            try:
                os.close(owned)
            except BaseException as exc:  # ownership cleanup must include non-OSError injection
                if first_error is None:
                    first_error = exc
        return first_error

    def transfer_ownership(
        self,
        *,
        to_owner_nonce: str,
    ) -> tuple[RetainedStagingReservation, dict[str, object]]:
        """Transfer both retained FDs; the old object can never write again."""

        target_owner = _safe_component(
            to_owner_nonce,
            label="to_owner_nonce",
        )
        with self._lock:
            self._require_open()
            before_record = self.record()
            parent_before = os.fstat(self._parent_fd)
            staging_before = os.fstat(self._descriptor)
            duplicated_parent: int | None = None
            duplicated_staging: int | None = None
            try:
                duplicated_parent = os.dup(self._parent_fd)
                duplicated_staging = os.dup(self._descriptor)
                if (
                    _signature(os.fstat(duplicated_parent))
                    != _signature(parent_before)
                    or _signature(os.fstat(duplicated_staging))
                    != _signature(staging_before)
                ):
                    raise BudgetContractError(
                        "HANDOFF_IDENTITY_DRIFT",
                        "duplicated retained staging descriptors differ",
                    )
                successor = RetainedStagingReservation(
                    root=self.root,
                    parent_fd=duplicated_parent,
                    descriptor=duplicated_staging,
                    staging_path=self._staging_path,
                    maximum_bytes=self._maximum_bytes,
                    artifact_class=self._artifact_class,
                    arm_slot=self._arm_slot,
                    purpose=self._purpose,
                    owner_nonce=target_owner,
                )
                duplicated_parent = None
                duplicated_staging = None
                handoff = {
                    "schema_version": BUDGET_OWNERSHIP_HANDOFF_SCHEMA,
                    "account_kind": "retained-staging",
                    "from_owner_nonce": self._owner_nonce,
                    "root_path": str(self.root),
                    "source_record_sha256": hashlib.sha256(
                        canonical_json_bytes(before_record)
                    ).hexdigest(),
                    "staging_path": self._staging_path,
                    "to_owner_nonce": target_owner,
                    "transfer_nonce": secrets.token_hex(16),
                }
                old_descriptor = self._descriptor
                old_parent_fd = self._parent_fd
                self._descriptor = -1
                self._parent_fd = -1
                self._closed = True
                close_error = self._close_pair(old_descriptor, old_parent_fd)
                if close_error is not None:
                    successor._close_pair(
                        successor._descriptor,
                        successor._parent_fd,
                    )
                    successor._descriptor = -1
                    successor._parent_fd = -1
                    successor._closed = True
                    raise BudgetContractError(
                        "HANDOFF_CLOSE_FAILED",
                        "retained staging source descriptor cleanup is uncertain",
                    ) from close_error
                return successor, handoff
            except BaseException:
                if duplicated_staging is not None:
                    try:
                        os.close(duplicated_staging)
                    except BaseException:
                        pass
                if duplicated_parent is not None:
                    try:
                        os.close(duplicated_parent)
                    except BaseException:
                        pass
                raise

    def detach_for_scm_rights(
        self,
        *,
        to_owner_nonce: str,
    ) -> tuple[int, int, dict[str, object], dict[str, object]]:
        """Irreversibly detach one exact FD pair for an SCM_RIGHTS handoff.

        The returned parent and staging descriptors have one caller owner.
        This object is invalidated before return and can never be retried.
        """

        target_owner = _safe_component(
            to_owner_nonce,
            label="to_owner_nonce",
        )
        with self._lock:
            self._require_open()
            before_record = self.record()
            parent_before = os.fstat(self._parent_fd)
            staging_before = os.fstat(self._descriptor)
            duplicated_parent: int | None = None
            duplicated_staging: int | None = None
            try:
                duplicated_parent = os.dup(self._parent_fd)
                duplicated_staging = os.dup(self._descriptor)
                if (
                    _signature(os.fstat(duplicated_parent))
                    != _signature(parent_before)
                    or _signature(os.fstat(duplicated_staging))
                    != _signature(staging_before)
                ):
                    raise BudgetContractError(
                        "HANDOFF_IDENTITY_DRIFT",
                        "detached retained staging descriptors differ",
                    )
                successor_record = {
                    **before_record,
                    "owner_nonce": target_owner,
                }
                handoff = {
                    "schema_version": BUDGET_OWNERSHIP_HANDOFF_SCHEMA,
                    "account_kind": "retained-staging",
                    "from_owner_nonce": self._owner_nonce,
                    "root_path": str(self.root),
                    "source_record_sha256": hashlib.sha256(
                        canonical_json_bytes(before_record)
                    ).hexdigest(),
                    "staging_path": self._staging_path,
                    "to_owner_nonce": target_owner,
                    "transfer_nonce": secrets.token_hex(16),
                }
                old_descriptor = self._descriptor
                old_parent_fd = self._parent_fd
                self._descriptor = -1
                self._parent_fd = -1
                self._closed = True
                close_error = self._close_pair(
                    old_descriptor,
                    old_parent_fd,
                )
                if close_error is not None:
                    self._close_pair(
                        duplicated_staging,
                        duplicated_parent,
                    )
                    duplicated_parent = None
                    duplicated_staging = None
                    raise BudgetContractError(
                        "HANDOFF_CLOSE_FAILED",
                        "retained staging source descriptor cleanup is uncertain",
                    ) from close_error
                result = (
                    duplicated_parent,
                    duplicated_staging,
                    successor_record,
                    handoff,
                )
                duplicated_parent = None
                duplicated_staging = None
                return result
            except BaseException:
                if duplicated_staging is not None:
                    try:
                        os.close(duplicated_staging)
                    except BaseException:
                        pass
                if duplicated_parent is not None:
                    try:
                        os.close(duplicated_parent)
                    except BaseException:
                        pass
                raise

    def publish_bytes(
        self,
        target_name: str,
        raw: bytes,
        *,
        acknowledgement: Callable[[dict[str, object]], object] | None = None,
    ) -> dict[str, object]:
        """Consume this extent in place and publish it with no replacement."""

        target = _safe_component(target_name, label="target_name")
        if not isinstance(raw, bytes) or len(raw) > self._maximum_bytes:
            raise BudgetContractError(
                "PAYLOAD_EXCEEDS_MAXIMUM",
                "retained staging payload exceeds its fixed extent",
            )
        with self._lock:
            self._require_open()
            _verify_retained_staging(self._descriptor)
            staging_name = PurePosixPath(self._staging_path).name
            published = False
            primary: BaseException | None = None
            try:
                _write_all_at(self._descriptor, raw)
                os.ftruncate(self._descriptor, len(raw))
                os.fsync(self._descriptor)
                digest = _sha256_descriptor(
                    self._descriptor,
                    size_bytes=len(raw),
                )
                os.fchmod(self._descriptor, 0o444)
                os.fsync(self._descriptor)
                _rename_noreplace(
                    self._parent_fd,
                    staging_name,
                    target,
                )
                published = True
                os.fsync(self._parent_fd)
                replay = FormalBudgetBroker._replay_published_at(
                    self._parent_fd,
                    target,
                    expected_size=len(raw),
                    expected_sha256=digest,
                )
                record = {
                    "schema_version": PUBLISHED_ARTIFACT_SCHEMA,
                    "arm_slot": self._arm_slot,
                    "artifact_class": self._artifact_class,
                    "maximum_bytes": self._maximum_bytes,
                    "path": str(
                        PurePosixPath(self._staging_path).parent / target
                    ),
                    "sha256": replay["sha256"],
                    "size_bytes": replay["size_bytes"],
                    "staging_name": staging_name,
                }
                if acknowledgement is not None:
                    try:
                        acknowledgement(dict(record))
                    except BaseException as exc:
                        raise BudgetContractError(
                            "ACKNOWLEDGEMENT_UNCERTAIN",
                            "retained staging target is published but its acknowledgement failed",
                        ) from exc
                return record
            except BaseException as exc:
                primary = exc
                if not published:
                    try:
                        os.fchmod(self._descriptor, 0o444)
                        os.fsync(self._descriptor)
                    except OSError:
                        pass
                raise
            finally:
                descriptor = self._descriptor
                parent_fd = self._parent_fd
                self._descriptor = -1
                self._parent_fd = -1
                self._closed = True
                close_error = self._close_pair(descriptor, parent_fd)
                if close_error is not None and primary is None:
                    raise close_error
                if close_error is not None and primary is not None:
                    try:
                        primary.add_note(
                            "retained staging descriptor cleanup also failed: "
                            f"{type(close_error).__name__}: {close_error}"
                        )
                    except Exception:
                        pass

    def close(self) -> None:
        with self._lock:
            self._require_open()
            descriptor = self._descriptor
            parent_fd = self._parent_fd
            self._descriptor = -1
            self._parent_fd = -1
            self._closed = True
            close_error = self._close_pair(descriptor, parent_fd)
            if close_error is not None:
                raise close_error


class RetainedDirectoryCapability:
    """One exact broker-created directory held across an owner handoff."""

    def __init__(
        self,
        *,
        root: Path,
        descriptor: int,
        relative_path: str,
        purpose: str,
        owner_nonce: str,
        identity: tuple[int, int, int, int],
    ) -> None:
        self.root = root
        self._descriptor = descriptor
        self._relative_path = relative_path
        self._purpose = purpose
        self._owner_nonce = owner_nonce
        self._identity = identity
        self._closed = False
        self._lock = threading.RLock()

    def _require_open(self) -> None:
        if self._closed:
            raise BudgetContractError(
                "DIRECTORY_CAPABILITY_CLOSED",
                "retained directory capability no longer has an owner",
            )

    def _recheck(self) -> os.stat_result:
        self._require_open()
        current = os.fstat(self._descriptor)
        if (
            _path_identity(current) != self._identity
            or not stat.S_ISDIR(current.st_mode)
            or stat.S_IMODE(current.st_mode) != 0o700
            or current.st_uid != os.getuid()
        ):
            raise BudgetContractError(
                "DIRECTORY_CAPABILITY_DRIFT",
                "retained directory capability identity drifted",
            )
        absolute = self.root / self._relative_path
        joined = _open_absolute_directory_no_symlinks(absolute)
        try:
            if _path_identity(os.fstat(joined)) != self._identity:
                raise BudgetContractError(
                    "DIRECTORY_CAPABILITY_PATH_DRIFT",
                    "absolute path no longer names the retained directory",
                )
        finally:
            os.close(joined)
        return current

    def fileno(self) -> int:
        with self._lock:
            self._recheck()
            return self._descriptor

    def record(self) -> dict[str, object]:
        with self._lock:
            current = self._recheck()
            return {
                "schema_version": BUDGET_RETAINED_DIRECTORY_SCHEMA,
                "directory_identity": list(_path_identity(current)),
                "directory_path": self._relative_path,
                "owner_nonce": self._owner_nonce,
                "purpose": self._purpose,
                "root_path": str(self.root),
            }

    def transfer_ownership(
        self,
        *,
        to_owner_nonce: str,
    ) -> tuple[RetainedDirectoryCapability, dict[str, object]]:
        target_owner = _safe_component(
            to_owner_nonce,
            label="to_owner_nonce",
        )
        with self._lock:
            before = self.record()
            duplicate: int | None = None
            try:
                duplicate = os.dup(self._descriptor)
                if _path_identity(os.fstat(duplicate)) != self._identity:
                    raise BudgetContractError(
                        "HANDOFF_IDENTITY_DRIFT",
                        "retained directory duplicate differs",
                    )
                successor = RetainedDirectoryCapability(
                    root=self.root,
                    descriptor=duplicate,
                    relative_path=self._relative_path,
                    purpose=self._purpose,
                    owner_nonce=target_owner,
                    identity=self._identity,
                )
                duplicate = None
                handoff = {
                    "schema_version": BUDGET_OWNERSHIP_HANDOFF_SCHEMA,
                    "account_kind": "retained-directory",
                    "directory_path": self._relative_path,
                    "from_owner_nonce": self._owner_nonce,
                    "root_path": str(self.root),
                    "source_record_sha256": hashlib.sha256(
                        canonical_json_bytes(before)
                    ).hexdigest(),
                    "to_owner_nonce": target_owner,
                    "transfer_nonce": secrets.token_hex(16),
                }
                original = self._descriptor
                self._descriptor = -1
                self._closed = True
                try:
                    os.close(original)
                except BaseException as exc:
                    try:
                        successor.close()
                    except BaseException:
                        pass
                    raise BudgetContractError(
                        "HANDOFF_CLOSE_FAILED",
                        "retained directory source cleanup is uncertain",
                    ) from exc
                return successor, handoff
            finally:
                if duplicate is not None:
                    try:
                        os.close(duplicate)
                    except BaseException:
                        pass

    def close(self) -> None:
        with self._lock:
            self._require_open()
            descriptor = self._descriptor
            self._descriptor = -1
            self._closed = True
            os.close(descriptor)


@dataclass
class _ArmAccount:
    category_limits: dict[str, int]
    category_remaining: dict[str, int]
    total_bytes: int


def canonical_json_bytes(value: object) -> bytes:
    """Return the sole JSON representation emitted by this primitive."""

    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def classify_consumption(*, scope: str, publication: str) -> str:
    """Return one of the four non-overlapping incomplete/terminal states."""

    if scope == "formal":
        if publication == "definitely-not-published":
            return FORMAL_MARKERLESS_INCOMPLETE
        if publication == "published-or-uncertain":
            return FORMAL_CONSUMED_INCOMPLETE
    elif scope == "arm":
        if publication == "definitely-not-published":
            return ARM_UNSELECTED_TERMINAL
        if publication == "published-or-uncertain":
            return ARM_CONSUMED_INCOMPLETE
    raise BudgetContractError(
        "INVALID_CONSUMPTION_STATE",
        f"unsupported scope/publication pair: {scope!r}/{publication!r}",
    )


def validate_closure_record(value: object) -> dict[str, object]:
    """Strictly validate one detached root-closure record."""

    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "closure_sha256",
        "entries",
        "root_path",
    }:
        raise BudgetContractError("INVALID_CLOSURE_RECORD", "closure record has the wrong shape")
    if value["schema_version"] != BUDGET_CLOSURE_SCHEMA:
        raise BudgetContractError("INVALID_CLOSURE_RECORD", "closure schema is not accepted")
    if not isinstance(value["root_path"], str) or not Path(value["root_path"]).is_absolute():
        raise BudgetContractError("INVALID_CLOSURE_RECORD", "closure root_path must be absolute")
    entries = value["entries"]
    if not isinstance(entries, list):
        raise BudgetContractError("INVALID_CLOSURE_RECORD", "closure entries must be a list")
    checked: list[dict[str, object]] = []
    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("type") not in {"directory", "regular"}:
            raise BudgetContractError("INVALID_CLOSURE_RECORD", "closure entry type is invalid")
        expected_keys = (
            {"mode_octal", "path", "type"}
            if entry["type"] == "directory"
            else {"mode_octal", "path", "sha256", "size_bytes", "type"}
        )
        if set(entry) != expected_keys:
            raise BudgetContractError("INVALID_CLOSURE_RECORD", "closure entry has the wrong shape")
        path = entry["path"]
        if (
            not isinstance(path, str)
            or str(PurePosixPath(*_relative_parts(path, allow_staging=True))) != path
        ):
            raise BudgetContractError("INVALID_CLOSURE_RECORD", "closure entry path is not canonical")
        if path in paths:
            raise BudgetContractError("INVALID_CLOSURE_RECORD", "closure entry paths are not unique")
        paths.add(path)
        mode = entry["mode_octal"]
        if not isinstance(mode, str) or len(mode) != 4 or any(character not in "01234567" for character in mode):
            raise BudgetContractError("INVALID_CLOSURE_RECORD", "closure entry mode is invalid")
        if entry["type"] == "regular":
            size = entry["size_bytes"]
            digest = entry["sha256"]
            _exact_nonnegative_int(size, label="closure size_bytes")
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise BudgetContractError("INVALID_CLOSURE_RECORD", "closure entry SHA-256 is invalid")
        checked.append(dict(entry))
    if checked != sorted(checked, key=lambda item: (str(item["path"]), str(item["type"]))):
        raise BudgetContractError("INVALID_CLOSURE_RECORD", "closure entries are not canonically ordered")
    expected_digest = hashlib.sha256(canonical_json_bytes(checked)).hexdigest()
    if value["closure_sha256"] != expected_digest:
        raise BudgetContractError("INVALID_CLOSURE_RECORD", "closure digest is invalid")
    return {
        "schema_version": BUDGET_CLOSURE_SCHEMA,
        "closure_sha256": expected_digest,
        "entries": checked,
        "root_path": value["root_path"],
    }


def _exact_nonnegative_int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BudgetContractError("INVALID_BUDGET", f"{label} must be an exact nonnegative integer")
    return value


def _validated_categories(
    values: Mapping[str, object],
    *,
    label: str,
    allow_zero_total: bool = False,
) -> dict[str, int]:
    if not isinstance(values, Mapping) or not values:
        raise BudgetContractError("INVALID_BUDGET", f"{label} must be a nonempty mapping")
    result: dict[str, int] = {}
    for name, value in values.items():
        if not isinstance(name, str) or name not in ARTIFACT_CLASSES:
            raise BudgetContractError("INVALID_ARTIFACT_CLASS", f"{label} contains {name!r}")
        result[name] = _exact_nonnegative_int(value, label=f"{label}.{name}")
    if not allow_zero_total and sum(result.values()) <= 0:
        raise BudgetContractError("INVALID_BUDGET", f"{label} must reserve at least one byte")
    return dict(sorted(result.items()))


def _relative_parts(
    value: str,
    *,
    allow_dot: bool = False,
    allow_staging: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise BudgetContractError("INVALID_RELATIVE_PATH", "path must be a nonempty portable relative path")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise BudgetContractError("INVALID_RELATIVE_PATH", "absolute paths are forbidden")
    parts = path.parts
    if allow_dot and parts in {(), (".",)}:
        return ()
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise BudgetContractError("INVALID_RELATIVE_PATH", f"unsafe relative path: {value!r}")
    if not allow_staging and parts[-1].startswith(_STAGING_PREFIX):
        raise BudgetContractError("RESERVED_PATH", "the hidden staging namespace is reserved")
    return parts


def _safe_component(value: str, *, label: str) -> str:
    parts = _relative_parts(value)
    if len(parts) != 1:
        raise BudgetContractError("INVALID_IDENTIFIER", f"{label} must be one portable path component")
    return parts[0]


def _signature(metadata: os.stat_result) -> tuple[int, int, int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode) | stat.S_IMODE(metadata.st_mode),
        metadata.st_uid,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _path_identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode) | stat.S_IMODE(metadata.st_mode),
        metadata.st_uid,
    )


def _open_absolute_directory_no_symlinks(path: Path) -> int:
    absolute = Path(os.path.abspath(path))
    if not absolute.is_absolute():
        raise BudgetContractError("ROOT_OPEN_FAILED", "root path did not become absolute")
    try:
        descriptor = os.open("/", _DIRECTORY_FLAGS)
    except OSError as exc:
        raise BudgetContractError("ROOT_OPEN_FAILED", "filesystem root cannot be opened safely") from exc
    try:
        for component in absolute.parts[1:]:
            try:
                next_descriptor = os.open(
                    component,
                    _DIRECTORY_FLAGS,
                    dir_fd=descriptor,
                )
            except OSError as exc:
                raise BudgetContractError(
                    "ROOT_OPEN_FAILED",
                    f"directory chain is unsafe: {absolute}",
                ) from exc
            previous_descriptor = descriptor
            descriptor = -1
            try:
                os.close(previous_descriptor)
            except BaseException as exc:
                try:
                    os.close(next_descriptor)
                except BaseException as close_exc:
                    exc.add_note(
                        "successor directory descriptor cleanup also failed: "
                        f"{type(close_exc).__name__}: {close_exc}"
                    )
                raise
            descriptor = next_descriptor
        result = descriptor
        descriptor = -1
        return result
    except BaseException as exc:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except BaseException as close_exc:
                exc.add_note(
                    "directory-chain cleanup also failed: "
                    f"{type(close_exc).__name__}: {close_exc}"
                )
        raise


def _open_parent_for_new_root(path: Path) -> tuple[int, str, Path]:
    absolute = Path(os.path.abspath(path))
    if absolute == Path("/"):
        raise BudgetContractError("INVALID_ROOT", "filesystem root cannot be an artifact root")
    return _open_absolute_directory_no_symlinks(absolute.parent), absolute.name, absolute


def _open_child_directory(parent_fd: int, name: str) -> int:
    try:
        return os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        raise BudgetContractError("DIRECTORY_OPEN_FAILED", f"unsafe or absent directory: {name}") from exc


def _open_directory_parts(root_fd: int, parts: tuple[str, ...]) -> int:
    try:
        descriptor = os.dup(root_fd)
    except OSError as exc:
        raise BudgetContractError(
            "DIRECTORY_OPEN_FAILED",
            "root directory descriptor cannot be duplicated",
        ) from exc
    try:
        for part in parts:
            next_descriptor = _open_child_directory(descriptor, part)
            previous_descriptor = descriptor
            descriptor = -1
            try:
                os.close(previous_descriptor)
            except BaseException as exc:
                try:
                    os.close(next_descriptor)
                except BaseException as close_exc:
                    exc.add_note(
                        "successor directory descriptor cleanup also failed: "
                        f"{type(close_exc).__name__}: {close_exc}"
                    )
                raise
            descriptor = next_descriptor
        result = descriptor
        descriptor = -1
        return result
    except BaseException as exc:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except BaseException as close_exc:
                exc.add_note(
                    "directory traversal cleanup also failed: "
                    f"{type(close_exc).__name__}: {close_exc}"
                )
        raise


def _sha256_descriptor(descriptor: int, *, size_bytes: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while offset < size_bytes:
        raw = os.pread(descriptor, min(_READ_CHUNK_BYTES, size_bytes - offset), offset)
        if not raw:
            raise BudgetContractError("SHORT_READ", "artifact descriptor ended before its stated size")
        digest.update(raw)
        offset += len(raw)
    if os.pread(descriptor, 1, size_bytes):
        raise BudgetContractError("SIZE_DRIFT", "artifact descriptor exceeds its stated size")
    return digest.hexdigest()


def _write_all_at(descriptor: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        written = os.pwrite(descriptor, raw[offset:], offset)
        if written <= 0:
            raise BudgetContractError("SHORT_WRITE", "artifact write made no progress")
        offset += written


def _verify_retained_staging(descriptor: int) -> None:
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
        or metadata.st_uid != os.getuid()
        or metadata.st_size <= 0
    ):
        raise BudgetContractError(
            "STAGING_IDENTITY_INVALID",
            "retained staging identity, mode, ownership, or extent is invalid",
        )


def _rename_noreplace(parent_fd: int, source: str, target: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    function = getattr(libc, "renameat2", None)
    if function is None:
        raise BudgetContractError("CAPABILITY_MISSING", "libc renameat2 is unavailable")
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    function.restype = ctypes.c_int
    result = function(
        parent_fd,
        os.fsencode(source),
        parent_fd,
        os.fsencode(target),
        _RENAME_NOREPLACE,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        if error_number == errno.EEXIST:
            raise BudgetContractError("TARGET_EXISTS", f"target already exists: {target}")
        raise BudgetContractError(
            "RENAME_NOREPLACE_FAILED",
            f"renameat2(RENAME_NOREPLACE) failed for {source!r} -> {target!r}: errno={error_number}",
        )


def require_capabilities() -> dict[str, object]:
    """Fail closed unless the unprivileged staging protocol is available."""

    required_os = ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW", "pread", "pwrite", "posix_fallocate")
    missing = [name for name in required_os if not hasattr(os, name)]
    function = getattr(ctypes.CDLL(None), "renameat2", None)
    if function is None:
        missing.append("libc.renameat2")
    if missing:
        raise BudgetContractError("CAPABILITY_MISSING", f"missing capabilities: {sorted(missing)!r}")
    return {
        "ordinary_user": True,
        "posix_fallocate": True,
        "pread_pwrite": True,
        "rename_noreplace": "libc-renameat2",
        "symlink_rejection": "descriptor-relative-O_NOFOLLOW",
    }


class FormalBudgetBroker:
    """The sole owner of a formal-root budget and its arm reservations."""

    def __init__(
        self,
        *,
        root: Path,
        root_fd: int,
        root_identity: tuple[int, int, int, int],
        category_limits: Mapping[str, int],
        owner_nonce: str,
    ) -> None:
        self.root = root
        self._root_fd = root_fd
        self._root_identity = root_identity
        self._root_limits = dict(category_limits)
        self._root_remaining = dict(category_limits)
        self._arms: dict[str, _ArmAccount] = {}
        self._arm_states: dict[str, str] = {}
        self._arm_seal_owner: tuple[str, int] | None = None
        self._registered_directories: set[tuple[str, ...]] = {()}
        self._registered_directory_modes: dict[tuple[str, ...], int] = {(): 0o700}
        self._published: list[PublishedArtifact] = []
        # Monotonic write-ahead inventory.  An O_EXCL-created staging inode is
        # registered before any fallocate/write operation.  Its entry is never
        # removed or reused: a successful no-replace publication changes only
        # the expected live path from the hidden staging name to the target.
        # Any uncertain transition therefore leaves the old expectation in
        # place and makes final root closure fail closed.
        self._staging_inventory: dict[str, dict[str, object]] = {}
        self._segment_next: dict[str, int] = {}
        self._closed = False
        self._lock = threading.RLock()
        self._owner_nonce = owner_nonce

    @classmethod
    def create(
        cls,
        root: Path | str,
        *,
        category_limits: Mapping[str, object],
        owner_nonce: str = "creator",
    ) -> FormalBudgetBroker:
        """Create and retain one empty no-overwrite formal artifact root."""

        require_capabilities()
        limits = _validated_categories(category_limits, label="category_limits")
        checked_owner_nonce = _safe_component(owner_nonce, label="owner_nonce")
        parent_fd, leaf, absolute = _open_parent_for_new_root(Path(root))
        root_fd: int | None = None
        created = False
        try:
            try:
                os.mkdir(leaf, 0o700, dir_fd=parent_fd)
            except FileExistsError as exc:
                raise BudgetContractError("ROOT_EXISTS", f"artifact root already exists: {absolute}") from exc
            created = True
            os.fsync(parent_fd)
            root_fd = os.open(leaf, _DIRECTORY_FLAGS, dir_fd=parent_fd)
            metadata = os.fstat(root_fd)
            if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700:
                raise BudgetContractError("ROOT_IDENTITY_INVALID", "new artifact root identity is invalid")
            if os.listdir(root_fd):
                raise BudgetContractError("ROOT_NOT_EMPTY", "new artifact root is not empty")
            result = cls(
                root=absolute,
                root_fd=root_fd,
                root_identity=_path_identity(metadata),
                category_limits=limits,
                owner_nonce=checked_owner_nonce,
            )
            root_fd = None
            return result
        except BaseException:
            if created:
                # A failed root remains allocated.  No deletion or name reuse is attempted.
                pass
            raise
        finally:
            if root_fd is not None:
                try:
                    os.close(root_fd)
                except OSError:
                    pass
            os.close(parent_fd)

    @property
    def total_bytes(self) -> int:
        return sum(self._root_limits.values())

    @property
    def remaining_bytes(self) -> int:
        with self._lock:
            return sum(self._root_remaining.values())

    @property
    def reserved_bytes(self) -> int:
        return self.total_bytes - self.remaining_bytes

    def remaining_by_class(self) -> dict[str, int]:
        with self._lock:
            return dict(self._root_remaining)

    def _require_open(self) -> None:
        if self._closed:
            raise BudgetContractError("BROKER_CLOSED", "budget broker is closed")

    def _require_root_identity(self) -> None:
        try:
            metadata = os.fstat(self._root_fd)
        except OSError as exc:
            raise BudgetContractError(
                "ROOT_IDENTITY_DRIFT",
                "retained artifact-root descriptor cannot be inspected",
            ) from exc
        if _path_identity(metadata) != self._root_identity:
            raise BudgetContractError("ROOT_IDENTITY_DRIFT", "retained artifact-root identity drifted")
        try:
            joined_fd = _open_absolute_directory_no_symlinks(self.root)
        except BudgetContractError as exc:
            raise BudgetContractError(
                "ROOT_PATH_DRIFT",
                "artifact-root path is absent, escaped, or traverses a symlink",
            ) from exc
        primary: BaseException | None = None
        try:
            if _path_identity(os.fstat(joined_fd)) != self._root_identity:
                raise BudgetContractError(
                    "ROOT_PATH_DRIFT",
                    "artifact-root path no longer names the retained root",
                )
        except BaseException as exc:
            primary = exc
            raise
        finally:
            try:
                os.close(joined_fd)
            except BaseException as close_exc:
                if primary is None:
                    raise
                primary.add_note(
                    "absolute root rejoin descriptor cleanup also failed: "
                    f"{type(close_exc).__name__}: {close_exc}"
                )

    def allocate_arm(
        self,
        arm_slot: str,
        *,
        category_limits: Mapping[str, object],
    ) -> dict[str, object]:
        """Atomically and non-refundably reserve one arm from root capacity."""

        slot = _safe_component(arm_slot, label="arm_slot")
        limits = _validated_categories(category_limits, label=f"arm[{slot}].category_limits")
        with self._lock:
            self._require_open()
            self._require_root_identity()
            if slot in self._arms:
                raise BudgetContractError("ARM_ALREADY_ALLOCATED", f"arm slot already allocated: {slot}")
            for category, amount in limits.items():
                if amount > self._root_remaining.get(category, 0):
                    raise BudgetContractError(
                        "ROOT_BUDGET_EXCEEDED",
                        f"arm {slot} requests {amount} {category} bytes but only "
                        f"{self._root_remaining.get(category, 0)} remain",
                    )
            for category, amount in limits.items():
                self._root_remaining[category] -= amount
            self._arms[slot] = _ArmAccount(
                category_limits=dict(limits),
                category_remaining=dict(limits),
                total_bytes=sum(limits.values()),
            )
            self._arm_states[slot] = "ACTIVE"
            return self.arm_account(slot)

    def arm_account(self, arm_slot: str) -> dict[str, object]:
        slot = _safe_component(arm_slot, label="arm_slot")
        with self._lock:
            self._require_open()
            try:
                account = self._arms[slot]
            except KeyError as exc:
                raise BudgetContractError("ARM_NOT_ALLOCATED", f"arm slot is not allocated: {slot}") from exc
            remaining = sum(account.category_remaining.values())
            return {
                "allocation_state": self._arm_states[slot],
                "arm_slot": slot,
                "category_limits": dict(account.category_limits),
                "category_remaining": dict(account.category_remaining),
                "reserved_bytes": account.total_bytes,
                "spent_or_stranded_bytes": account.total_bytes - remaining,
                "unspent_reserved_bytes": remaining,
            }

    def begin_arm_seal(self, arm_slot: str) -> None:
        """Enter the sole irreversible arm-seal transaction.

        The caller must retain ``_lock`` until it either calls
        :meth:`complete_arm_seal` after a successful acknowledgement or
        :meth:`fail_arm_seal` on every uncertain path.  While pending, only
        the owning thread may debit the final manifest/terminal extents.
        """

        slot = _safe_component(arm_slot, label="arm_slot")
        if not self._lock._is_owned():  # type: ignore[attr-defined]  # noqa: SLF001
            raise BudgetContractError(
                "ARM_SEAL_LOCK_MISSING",
                "arm sealing requires the retained broker lock",
            )
        self._require_open()
        if self._arm_states.get(slot) != "ACTIVE":
            raise BudgetContractError(
                "ARM_NOT_ACTIVE",
                f"arm slot cannot begin sealing from {self._arm_states.get(slot)!r}",
            )
        if self._arm_seal_owner is not None:
            raise BudgetContractError(
                "ARM_SEAL_ALREADY_PENDING",
                "another arm seal transaction is already pending",
            )
        self._arm_states[slot] = "SEALED_PENDING"
        self._arm_seal_owner = (slot, threading.get_ident())

    def mark_arm_seal_durable_pending_ack(self, arm_slot: str) -> None:
        """Record that both seal publications are durable but not acknowledged."""

        slot = _safe_component(arm_slot, label="arm_slot")
        if (
            not self._lock._is_owned()  # type: ignore[attr-defined]  # noqa: SLF001
            or self._arm_states.get(slot) != "SEALED_PENDING"
            or self._arm_seal_owner != (slot, threading.get_ident())
        ):
            raise BudgetContractError(
                "ARM_SEAL_STATE_DRIFT",
                "durable arm seal lacks its exact pending owner",
            )
        self._arm_states[slot] = "SEALED_PENDING_ACK"
        self._arm_seal_owner = None

    def complete_arm_seal(self, arm_slot: str) -> None:
        """Commit the seal ACK while retaining only post-seal closeout extents."""

        slot = _safe_component(arm_slot, label="arm_slot")
        if (
            not self._lock._is_owned()  # type: ignore[attr-defined]  # noqa: SLF001
            or self._arm_states.get(slot) != "SEALED_PENDING_ACK"
            or self._arm_seal_owner is not None
        ):
            raise BudgetContractError(
                "ARM_SEAL_STATE_DRIFT",
                "arm seal completion lacks its durable pending acknowledgement",
            )
        self._arm_states[slot] = "SEALED"

    def mark_arm_replay_published(self, arm_slot: str) -> None:
        """Advance after the pre-reserved outside replay is durably published."""

        slot = _safe_component(arm_slot, label="arm_slot")
        if (
            not self._lock._is_owned()  # type: ignore[attr-defined]  # noqa: SLF001
            or self._arm_states.get(slot) != "SEALED"
            or self._arm_seal_owner is not None
        ):
            raise BudgetContractError(
                "ARM_POST_SEAL_STATE_DRIFT",
                "outside replay publication does not follow the accepted seal",
            )
        self._arm_states[slot] = "POST_SEAL_REPLAY_PUBLISHED"

    def complete_arm_closeout(self, arm_slot: str) -> None:
        """Close one arm only after its pre-reserved consumption is durable."""

        slot = _safe_component(arm_slot, label="arm_slot")
        if (
            not self._lock._is_owned()  # type: ignore[attr-defined]  # noqa: SLF001
            or self._arm_states.get(slot)
            != "POST_SEAL_REPLAY_PUBLISHED"
            or self._arm_seal_owner is not None
        ):
            raise BudgetContractError(
                "ARM_POST_SEAL_STATE_DRIFT",
                "arm closeout lacks its durable outside replay",
            )
        self._arm_states[slot] = "CLOSED"

    def fail_arm_post_seal_closeout(self, arm_slot: str) -> None:
        """Permanently strand an accepted arm with uncertain post-seal output."""

        slot = _safe_component(arm_slot, label="arm_slot")
        if (
            not self._lock._is_owned()  # type: ignore[attr-defined]  # noqa: SLF001
            or self._arm_states.get(slot)
            not in {"SEALED", "POST_SEAL_REPLAY_PUBLISHED"}
            or self._arm_seal_owner is not None
        ):
            raise BudgetContractError(
                "ARM_POST_SEAL_STATE_DRIFT",
                "post-seal failure lacks the accepted arm state",
            )
        self._arm_states[slot] = "SEALED_INCOMPLETE"

    def fail_arm_seal(self, arm_slot: str) -> None:
        """Permanently strand one uncertain seal without refund or reuse."""

        slot = _safe_component(arm_slot, label="arm_slot")
        if (
            not self._lock._is_owned()  # type: ignore[attr-defined]  # noqa: SLF001
            or self._arm_states.get(slot)
            not in {"SEALED_PENDING", "SEALED_PENDING_ACK"}
            or (
                self._arm_states.get(slot) == "SEALED_PENDING"
                and self._arm_seal_owner != (slot, threading.get_ident())
            )
        ):
            raise BudgetContractError(
                "ARM_SEAL_STATE_DRIFT",
                "arm seal failure lacks its exact pending owner",
            )
        self._arm_states[slot] = "SEALED_INCOMPLETE"
        self._arm_seal_owner = None

    def register_directory(self, relative_path: str, *, mode: int = 0o700) -> str:
        """Create one fixed directory path and bind its final access mode."""

        parts = _relative_parts(relative_path, allow_dot=True)
        if isinstance(mode, bool) or not isinstance(mode, int) or mode not in {0o500, 0o700}:
            raise BudgetContractError(
                "DIRECTORY_MODE_INVALID",
                "registered directory mode must be exactly 0500 or 0700",
            )
        if not parts and mode != 0o700:
            raise BudgetContractError(
                "DIRECTORY_MODE_INVALID",
                "the retained formal root must remain mode 0700",
            )
        with self._lock:
            self._require_open()
            self._require_root_identity()
            descriptor = os.dup(self._root_fd)
            current: tuple[str, ...] = ()
            try:
                for part in parts:
                    candidate = (*current, part)
                    if candidate not in self._registered_directories:
                        try:
                            os.mkdir(part, 0o700, dir_fd=descriptor)
                        except FileExistsError as exc:
                            raise BudgetContractError(
                                "DIRECTORY_COLLISION",
                                f"unregistered directory already exists: {PurePosixPath(*candidate)}",
                            ) from exc
                        os.fsync(descriptor)
                        self._registered_directories.add(candidate)
                        self._registered_directory_modes[candidate] = 0o700
                    next_descriptor = _open_child_directory(descriptor, part)
                    os.close(descriptor)
                    descriptor = next_descriptor
                    current = candidate
                existing_mode = self._registered_directory_modes[current]
                if existing_mode != mode:
                    if existing_mode != 0o700:
                        raise BudgetContractError(
                            "DIRECTORY_MODE_DRIFT",
                            f"registered directory mode changed after sealing: {relative_path}",
                        )
                    os.fchmod(descriptor, mode)
                    os.fsync(descriptor)
                    self._registered_directory_modes[current] = mode
                observed = os.fstat(descriptor)
                if (
                    not stat.S_ISDIR(observed.st_mode)
                    or stat.S_IMODE(observed.st_mode) != mode
                    or observed.st_uid != os.getuid()
                ):
                    raise BudgetContractError(
                        "DIRECTORY_MODE_DRIFT",
                        f"registered directory mode or ownership differs: {relative_path}",
                    )
            finally:
                os.close(descriptor)
            return "." if not parts else str(PurePosixPath(*parts))

    def retain_directory(
        self,
        relative_path: str,
        *,
        purpose: str,
    ) -> RetainedDirectoryCapability:
        """Retain one registered 0700 directory for an exact later owner."""

        parts = _relative_parts(relative_path, allow_dot=True)
        checked_purpose = _safe_component(purpose, label="purpose")
        with self._lock:
            self._require_open()
            self._require_root_identity()
            if parts not in self._registered_directories:
                raise BudgetContractError(
                    "DIRECTORY_NOT_REGISTERED",
                    "retained directory was not broker-created",
                )
            if self._registered_directory_modes[parts] != 0o700:
                raise BudgetContractError(
                    "DIRECTORY_MODE_DRIFT",
                    "retained directory capability requires mode 0700",
                )
            descriptor = _open_directory_parts(self._root_fd, parts)
            transferred = False
            try:
                metadata = os.fstat(descriptor)
                if (
                    not stat.S_ISDIR(metadata.st_mode)
                    or stat.S_IMODE(metadata.st_mode) != 0o700
                    or metadata.st_uid != os.getuid()
                ):
                    raise BudgetContractError(
                        "DIRECTORY_CAPABILITY_DRIFT",
                        "retained directory identity is invalid",
                    )
                result = RetainedDirectoryCapability(
                    root=self.root,
                    descriptor=descriptor,
                    relative_path=(
                        "." if not parts else str(PurePosixPath(*parts))
                    ),
                    purpose=checked_purpose,
                    owner_nonce=self._owner_nonce,
                    identity=_path_identity(metadata),
                )
                transferred = True
                return result
            finally:
                if not transferred:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

    def _reserve(
        self,
        *,
        artifact_class: str,
        maximum_bytes: int,
        arm_slot: str | None,
    ) -> None:
        if artifact_class not in ARTIFACT_CLASSES:
            raise BudgetContractError("INVALID_ARTIFACT_CLASS", f"unknown class: {artifact_class!r}")
        if maximum_bytes <= 0:
            raise BudgetContractError("INVALID_BUDGET", "maximum_bytes must be positive")
        if arm_slot is None:
            remaining = self._root_remaining.get(artifact_class, 0)
            if maximum_bytes > remaining:
                raise BudgetContractError(
                    "ROOT_BUDGET_EXCEEDED",
                    f"{maximum_bytes} {artifact_class} bytes requested but {remaining} remain",
                )
            self._root_remaining[artifact_class] = remaining - maximum_bytes
            return
        try:
            account = self._arms[arm_slot]
        except KeyError as exc:
            raise BudgetContractError("ARM_NOT_ALLOCATED", f"arm slot is not allocated: {arm_slot}") from exc
        state = self._arm_states[arm_slot]
        if state != "ACTIVE" and not (
            state == "SEALED_PENDING"
            and self._arm_seal_owner == (arm_slot, threading.get_ident())
            and self._lock._is_owned()  # type: ignore[attr-defined]  # noqa: SLF001
        ):
            raise BudgetContractError(
                "ARM_NOT_ACTIVE",
                f"arm {arm_slot} cannot debit budget from state {state}",
            )
        remaining = account.category_remaining.get(artifact_class, 0)
        if maximum_bytes > remaining:
            raise BudgetContractError(
                "ARM_BUDGET_EXCEEDED",
                f"arm {arm_slot} requests {maximum_bytes} {artifact_class} bytes but {remaining} remain",
            )
        account.category_remaining[artifact_class] = remaining - maximum_bytes

    def _register_staging_inode(
        self,
        *,
        staging_path: str,
        target_path: str | None,
        descriptor: int,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None,
        purpose: str,
    ) -> None:
        """Record one freshly O_EXCL-created inode before it can be written."""

        if staging_path in self._staging_inventory:
            raise BudgetContractError(
                "STAGING_INVENTORY_COLLISION",
                "hidden staging path is already registered",
            )
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_uid != os.getuid()
        ):
            raise BudgetContractError(
                "STAGING_IDENTITY_INVALID",
                "fresh staging inode identity is invalid",
            )
        self._staging_inventory[staging_path] = {
            "arm_slot": arm_slot,
            "artifact_class": artifact_class,
            "expected_path": staging_path,
            "maximum_bytes": maximum_bytes,
            "purpose": purpose,
            "staging_path": staging_path,
            "staging_signature_at_creation": list(_signature(metadata)),
            "state": "STAGING_RETAINED",
            "target_path": target_path,
            "type": "regular",
        }

    def _mark_staging_published(
        self,
        *,
        staging_path: str,
        target_path: str,
    ) -> None:
        """Commit one known-successful staging-to-target transition."""

        try:
            entry = self._staging_inventory[staging_path]
        except KeyError as exc:
            raise BudgetContractError(
                "STAGING_INVENTORY_MISSING",
                "published staging inode was never registered",
            ) from exc
        if (
            entry["state"] != "STAGING_RETAINED"
            or entry["expected_path"] != staging_path
            or entry["target_path"] != target_path
        ):
            raise BudgetContractError(
                "STAGING_INVENTORY_DRIFT",
                "staging publication transition differs from its reservation",
            )
        entry["expected_path"] = target_path
        entry["state"] = "PUBLISHED_NO_REPLACE"

    def bind_retained_staging_target(
        self,
        *,
        staging_path: str,
        target_path: str,
    ) -> None:
        """Bind a fixed reservation to its package-declared publish path."""

        with self._lock:
            self._require_open()
            try:
                entry = self._staging_inventory[staging_path]
            except KeyError as exc:
                raise BudgetContractError(
                    "STAGING_INVENTORY_MISSING",
                    "fixed reservation staging path is unregistered",
                ) from exc
            if (
                entry["state"] != "STAGING_RETAINED"
                or entry["expected_path"] != staging_path
                or entry["target_path"] not in {None, target_path}
            ):
                raise BudgetContractError(
                    "STAGING_INVENTORY_DRIFT",
                    "fixed reservation target binding differs",
                )
            entry["target_path"] = target_path

    def mark_bound_target_published(self, target_path: str) -> None:
        """Commit the unique fixed reservation which published this target."""

        with self._lock:
            self._require_open()
            candidates = [
                staging_path
                for staging_path, entry in self._staging_inventory.items()
                if entry["target_path"] == target_path
                and entry["state"] == "STAGING_RETAINED"
            ]
            if len(candidates) != 1:
                raise BudgetContractError(
                    "STAGING_INVENTORY_DRIFT",
                    "published target does not identify one live reservation",
                )
            self._mark_staging_published(
                staging_path=candidates[0],
                target_path=target_path,
            )

    def expected_root_path_types(self) -> list[dict[str, str]]:
        """Return the immutable expected descendant path/type set.

        This is an arithmetic/layout expectation, not a scan of ambient root
        members.  The closure actor compares it with a fresh descriptor walk;
        unknown nodes can therefore never be adopted into the manifest.
        """

        with self._lock:
            self._require_open()
            result = [
                {
                    "path": str(PurePosixPath(*parts)),
                    "type": "directory",
                }
                for parts in self._registered_directories
                if parts
            ]
            result.extend(
                {
                    "path": cast(str, entry["expected_path"]),
                    "type": cast(str, entry["type"]),
                }
                for entry in self._staging_inventory.values()
            )
            result.sort(key=lambda item: (item["path"], item["type"]))
            if len({item["path"] for item in result}) != len(result):
                raise BudgetContractError(
                    "ROOT_INVENTORY_PATH_COLLISION",
                    "two registered descendants claim the same path",
                )
            return result

    def staging_inventory(self) -> list[dict[str, object]]:
        """Return a canonical diagnostic copy of the monotonic staging ledger."""

        with self._lock:
            self._require_open()
            return [
                dict(self._staging_inventory[path])
                for path in sorted(self._staging_inventory)
            ]

    def reserve_retained_staging(
        self,
        relative_parent: str,
        *,
        maximum_bytes: int,
        artifact_class: str,
        purpose: str,
        arm_slot: str | None = None,
    ) -> RetainedStagingReservation:
        """Debit and retain one physical hidden extent without publishing it.

        The returned object is the only owner of the staging and parent FDs.
        Every failure after the debit strands the credit and leaves any created
        staging inode immutable; this method never unlinks or refunds it.
        """

        maximum = _exact_nonnegative_int(
            maximum_bytes,
            label="maximum_bytes",
        )
        if maximum <= 0:
            raise BudgetContractError(
                "INVALID_BUDGET",
                "maximum_bytes must be positive",
            )
        parent_parts = _relative_parts(relative_parent, allow_dot=True)
        slot = (
            _safe_component(arm_slot, label="arm_slot")
            if arm_slot is not None
            else None
        )
        checked_purpose = _safe_component(purpose, label="purpose")
        staging_name = f"{_STAGING_PREFIX}{secrets.token_hex(16)}"
        with self._lock:
            self._require_open()
            self._require_root_identity()
            if parent_parts not in self._registered_directories:
                raise BudgetContractError(
                    "DIRECTORY_NOT_REGISTERED",
                    "retained staging parent is not broker-created",
                )
            self._reserve(
                artifact_class=artifact_class,
                maximum_bytes=maximum,
                arm_slot=slot,
            )
            parent_fd = _open_directory_parts(self._root_fd, parent_parts)
            descriptor: int | None = None
            transferred = False
            try:
                try:
                    descriptor = os.open(
                        staging_name,
                        _WRITE_FLAGS,
                        0o600,
                        dir_fd=parent_fd,
                    )
                except FileExistsError as exc:
                    raise BudgetContractError(
                        "STAGING_COLLISION",
                        "hidden retained staging name collided",
                    ) from exc
                try:
                    staging_path = str(
                        PurePosixPath(*parent_parts, staging_name)
                    )
                    self._register_staging_inode(
                        staging_path=staging_path,
                        target_path=None,
                        descriptor=descriptor,
                        maximum_bytes=maximum,
                        artifact_class=artifact_class,
                        arm_slot=slot,
                        purpose=checked_purpose,
                    )
                    os.posix_fallocate(descriptor, 0, maximum)
                    _verify_retained_staging(descriptor)
                    os.fsync(descriptor)
                    os.fsync(parent_fd)
                    reservation = RetainedStagingReservation(
                        root=self.root,
                        parent_fd=parent_fd,
                        descriptor=descriptor,
                        staging_path=str(
                            PurePosixPath(*parent_parts, staging_name)
                        ),
                        maximum_bytes=maximum,
                        artifact_class=artifact_class,
                        arm_slot=slot,
                        purpose=checked_purpose,
                        owner_nonce=self._owner_nonce,
                    )
                    transferred = True
                    return reservation
                except BaseException:
                    if descriptor is not None:
                        try:
                            os.fchmod(descriptor, 0o444)
                            os.fsync(descriptor)
                        except OSError:
                            pass
                    raise
            finally:
                if not transferred:
                    if descriptor is not None:
                        try:
                            os.close(descriptor)
                        except OSError:
                            pass
                    try:
                        os.close(parent_fd)
                    except OSError:
                        pass

    def transfer_ownership(
        self,
        *,
        to_owner_nonce: str,
    ) -> tuple[FormalBudgetBroker, dict[str, object]]:
        """Move the root/account FD and arithmetic to one successor owner."""

        target_owner = _safe_component(
            to_owner_nonce,
            label="to_owner_nonce",
        )
        with self._lock:
            self._require_open()
            self._require_root_identity()
            source_contract = self.contract_record()
            source_metadata = os.fstat(self._root_fd)
            successor_fd: int | None = None
            try:
                successor_fd = os.dup(self._root_fd)
                if _signature(os.fstat(successor_fd)) != _signature(
                    source_metadata
                ):
                    raise BudgetContractError(
                        "HANDOFF_IDENTITY_DRIFT",
                        "duplicated formal-root descriptor differs",
                    )
                successor = FormalBudgetBroker(
                    root=self.root,
                    root_fd=successor_fd,
                    root_identity=self._root_identity,
                    category_limits=self._root_limits,
                    owner_nonce=target_owner,
                )
                successor_fd = None
                successor._root_remaining = dict(self._root_remaining)
                successor._arms = {
                    slot: _ArmAccount(
                        category_limits=dict(account.category_limits),
                        category_remaining=dict(account.category_remaining),
                        total_bytes=account.total_bytes,
                    )
                    for slot, account in self._arms.items()
                }
                successor._arm_states = dict(self._arm_states)
                successor._arm_seal_owner = None
                successor._registered_directories = set(
                    self._registered_directories
                )
                successor._registered_directory_modes = dict(
                    self._registered_directory_modes
                )
                successor._published = list(self._published)
                successor._staging_inventory = {
                    path: dict(record)
                    for path, record in self._staging_inventory.items()
                }
                successor._segment_next = dict(self._segment_next)
                handoff = {
                    "schema_version": BUDGET_OWNERSHIP_HANDOFF_SCHEMA,
                    "account_kind": "formal-root",
                    "account_record_sha256": hashlib.sha256(
                        canonical_json_bytes(source_contract)
                    ).hexdigest(),
                    "from_owner_nonce": self._owner_nonce,
                    "root_path": str(self.root),
                    "root_signature": list(_signature(source_metadata)),
                    "to_owner_nonce": target_owner,
                    "transfer_nonce": secrets.token_hex(16),
                }
                old_fd = self._root_fd
                self._root_fd = -1
                self._closed = True
                try:
                    os.close(old_fd)
                except BaseException as exc:
                    try:
                        successor.close()
                    except BaseException:
                        pass
                    raise BudgetContractError(
                        "HANDOFF_CLOSE_FAILED",
                        "formal-root source descriptor cleanup is uncertain",
                    ) from exc
                return successor, handoff
            except BaseException:
                if successor_fd is not None:
                    try:
                        os.close(successor_fd)
                    except BaseException:
                        pass
                raise

    def publish_bytes(
        self,
        relative_path: str,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
        final_mode: int = 0o444,
        acknowledgement: Callable[[dict[str, object]], object] | None = None,
    ) -> dict[str, object]:
        """Publish one immutable artifact from preallocated same-directory staging."""

        if not isinstance(raw, bytes):
            raise BudgetContractError("INVALID_PAYLOAD", "payload must be exact bytes")
        maximum = _exact_nonnegative_int(maximum_bytes, label="maximum_bytes")
        if maximum <= 0 or len(raw) > maximum:
            raise BudgetContractError("PAYLOAD_EXCEEDS_MAXIMUM", "payload is larger than its fixed allocation")
        if isinstance(final_mode, bool) or final_mode not in {0o444, 0o555}:
            raise BudgetContractError(
                "INVALID_FINAL_MODE",
                "published artifact mode must be exactly 0444 or 0555",
            )
        parts = _relative_parts(relative_path)
        slot = _safe_component(arm_slot, label="arm_slot") if arm_slot is not None else None
        parent_parts = parts[:-1]
        target_name = parts[-1]
        staging_name = f"{_STAGING_PREFIX}{secrets.token_hex(16)}"
        with self._lock:
            self._require_open()
            self._require_root_identity()
            if parent_parts not in self._registered_directories:
                raise BudgetContractError(
                    "DIRECTORY_NOT_REGISTERED",
                    f"parent directory is not broker-created: {PurePosixPath(*parent_parts)}",
                )
            self._reserve(
                artifact_class=artifact_class,
                maximum_bytes=maximum,
                arm_slot=slot,
            )
            parent_fd = _open_directory_parts(self._root_fd, parent_parts)
            descriptor: int | None = None
            published = False
            try:
                try:
                    descriptor = os.open(staging_name, _WRITE_FLAGS, 0o600, dir_fd=parent_fd)
                except FileExistsError as exc:
                    raise BudgetContractError("STAGING_COLLISION", "hidden staging name collided") from exc
                try:
                    staging_path = str(
                        PurePosixPath(*parent_parts, staging_name)
                    )
                    target_path = str(PurePosixPath(*parts))
                    self._register_staging_inode(
                        staging_path=staging_path,
                        target_path=target_path,
                        descriptor=descriptor,
                        maximum_bytes=maximum,
                        artifact_class=artifact_class,
                        arm_slot=slot,
                        purpose=f"publish-{target_name}",
                    )
                    os.posix_fallocate(descriptor, 0, maximum)
                    _write_all_at(descriptor, raw)
                    os.fsync(descriptor)
                    os.ftruncate(descriptor, len(raw))
                    metadata = os.fstat(descriptor)
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != len(raw):
                        raise BudgetContractError("STAGING_IDENTITY_INVALID", "staging identity or size is invalid")
                    digest = _sha256_descriptor(descriptor, size_bytes=len(raw))
                    os.fchmod(descriptor, final_mode)
                    os.fsync(descriptor)
                    _rename_noreplace(parent_fd, staging_name, target_name)
                    published = True
                    os.fsync(parent_fd)
                    replay = self._replay_published_at(
                        parent_fd,
                        target_name,
                        expected_size=len(raw),
                        expected_sha256=digest,
                        expected_mode=final_mode,
                    )
                    self._mark_staging_published(
                        staging_path=staging_path,
                        target_path=target_path,
                    )
                    artifact = PublishedArtifact(
                        arm_slot=slot,
                        artifact_class=artifact_class,
                        maximum_bytes=maximum,
                        path=str(PurePosixPath(*parts)),
                        sha256=cast(str, replay["sha256"]),
                        size_bytes=cast(int, replay["size_bytes"]),
                        staging_name=staging_name,
                    )
                    self._published.append(artifact)
                    record = artifact.as_record()
                    if acknowledgement is not None:
                        try:
                            acknowledgement(dict(record))
                        except BaseException as exc:
                            raise BudgetContractError(
                                "ACKNOWLEDGEMENT_UNCERTAIN",
                                "artifact is published but its acknowledgement failed",
                            ) from exc
                    return record
                except BaseException:
                    if descriptor is not None and not published:
                        try:
                            os.fchmod(descriptor, 0o444)
                            os.fsync(descriptor)
                        except OSError:
                            pass
                    raise
                finally:
                    if descriptor is not None:
                        os.close(descriptor)
            finally:
                os.close(parent_fd)

    def publish_preverified_descriptor(
        self,
        relative_path: str,
        source_fd: int,
        *,
        size_bytes: int,
        expected_sha256: str,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
        acknowledgement: Callable[[dict[str, object]], object] | None = None,
    ) -> dict[str, object]:
        """Copy one caller-proved immutable descriptor into a reserved extent.

        The package-pinned broker is responsible for proving the source is a
        fully sealed memfd before calling this method.  This primitive still
        rechecks the source descriptor identity and digest before and after the
        copy; it never treats those checks as a substitute for the native seal
        proof.
        """

        size = _exact_nonnegative_int(size_bytes, label="size_bytes")
        maximum = _exact_nonnegative_int(maximum_bytes, label="maximum_bytes")
        if maximum <= 0 or size > maximum:
            raise BudgetContractError(
                "PAYLOAD_EXCEEDS_MAXIMUM",
                "descriptor payload is larger than its fixed allocation",
            )
        if (
            not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64
            or any(character not in "0123456789abcdef" for character in expected_sha256)
        ):
            raise BudgetContractError("INVALID_PAYLOAD_IDENTITY", "descriptor SHA-256 is malformed")
        try:
            source_before = os.fstat(source_fd)
        except OSError as exc:
            raise BudgetContractError("SOURCE_DESCRIPTOR_INVALID", "source descriptor cannot be inspected") from exc
        if not stat.S_ISREG(source_before.st_mode) or source_before.st_size != size:
            raise BudgetContractError("SOURCE_DESCRIPTOR_INVALID", "source descriptor identity or size is invalid")
        if _sha256_descriptor(source_fd, size_bytes=size) != expected_sha256:
            raise BudgetContractError("SOURCE_DESCRIPTOR_INVALID", "source descriptor SHA-256 differs")

        parts = _relative_parts(relative_path)
        slot = _safe_component(arm_slot, label="arm_slot") if arm_slot is not None else None
        parent_parts = parts[:-1]
        target_name = parts[-1]
        staging_name = f"{_STAGING_PREFIX}{secrets.token_hex(16)}"
        with self._lock:
            self._require_open()
            self._require_root_identity()
            if parent_parts not in self._registered_directories:
                raise BudgetContractError(
                    "DIRECTORY_NOT_REGISTERED",
                    f"parent directory is not broker-created: {PurePosixPath(*parent_parts)}",
                )
            self._reserve(
                artifact_class=artifact_class,
                maximum_bytes=maximum,
                arm_slot=slot,
            )
            parent_fd = _open_directory_parts(self._root_fd, parent_parts)
            descriptor: int | None = None
            published = False
            try:
                try:
                    descriptor = os.open(staging_name, _WRITE_FLAGS, 0o600, dir_fd=parent_fd)
                except FileExistsError as exc:
                    raise BudgetContractError("STAGING_COLLISION", "hidden staging name collided") from exc
                try:
                    staging_path = str(
                        PurePosixPath(*parent_parts, staging_name)
                    )
                    target_path = str(PurePosixPath(*parts))
                    self._register_staging_inode(
                        staging_path=staging_path,
                        target_path=target_path,
                        descriptor=descriptor,
                        maximum_bytes=maximum,
                        artifact_class=artifact_class,
                        arm_slot=slot,
                        purpose=f"publish-{target_name}",
                    )
                    os.posix_fallocate(descriptor, 0, maximum)
                    digest = hashlib.sha256()
                    offset = 0
                    while offset < size:
                        block = os.pread(source_fd, min(_READ_CHUNK_BYTES, size - offset), offset)
                        if not block:
                            raise BudgetContractError(
                                "SHORT_READ",
                                "source descriptor ended before its stated size",
                            )
                        view = memoryview(block)
                        block_offset = offset
                        while view:
                            written = os.pwrite(descriptor, view, block_offset)
                            if written <= 0:
                                raise BudgetContractError(
                                    "SHORT_WRITE",
                                    "artifact descriptor copy made no progress",
                                )
                            block_offset += written
                            view = view[written:]
                        digest.update(block)
                        offset += len(block)
                    if os.pread(source_fd, 1, size):
                        raise BudgetContractError(
                            "SIZE_DRIFT",
                            "source descriptor exceeds its stated size",
                        )
                    if digest.hexdigest() != expected_sha256:
                        raise BudgetContractError(
                            "SOURCE_DESCRIPTOR_INVALID",
                            "source descriptor changed during copy",
                        )
                    source_after = os.fstat(source_fd)
                    if _signature(source_after) != _signature(source_before):
                        raise BudgetContractError(
                            "SOURCE_DESCRIPTOR_INVALID",
                            "source descriptor identity drifted during copy",
                        )
                    os.fsync(descriptor)
                    os.ftruncate(descriptor, size)
                    metadata = os.fstat(descriptor)
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != size:
                        raise BudgetContractError(
                            "STAGING_IDENTITY_INVALID",
                            "staging identity or size is invalid",
                        )
                    staged_digest = _sha256_descriptor(descriptor, size_bytes=size)
                    if staged_digest != expected_sha256:
                        raise BudgetContractError(
                            "STAGING_IDENTITY_INVALID",
                            "staging SHA-256 differs from the sealed source",
                        )
                    os.fchmod(descriptor, 0o444)
                    os.fsync(descriptor)
                    _rename_noreplace(parent_fd, staging_name, target_name)
                    published = True
                    os.fsync(parent_fd)
                    replay = self._replay_published_at(
                        parent_fd,
                        target_name,
                        expected_size=size,
                        expected_sha256=expected_sha256,
                    )
                    self._mark_staging_published(
                        staging_path=staging_path,
                        target_path=target_path,
                    )
                    artifact = PublishedArtifact(
                        arm_slot=slot,
                        artifact_class=artifact_class,
                        maximum_bytes=maximum,
                        path=str(PurePosixPath(*parts)),
                        sha256=cast(str, replay["sha256"]),
                        size_bytes=cast(int, replay["size_bytes"]),
                        staging_name=staging_name,
                    )
                    self._published.append(artifact)
                    record = artifact.as_record()
                    if acknowledgement is not None:
                        try:
                            acknowledgement(dict(record))
                        except BaseException as exc:
                            raise BudgetContractError(
                                "ACKNOWLEDGEMENT_UNCERTAIN",
                                "artifact is published but its acknowledgement failed",
                            ) from exc
                    return record
                except BaseException:
                    if descriptor is not None and not published:
                        try:
                            os.fchmod(descriptor, 0o444)
                            os.fsync(descriptor)
                        except OSError:
                            pass
                    raise
                finally:
                    if descriptor is not None:
                        os.close(descriptor)
            finally:
                os.close(parent_fd)

    @staticmethod
    def _replay_published_at(
        parent_fd: int,
        name: str,
        *,
        expected_size: int,
        expected_sha256: str,
        expected_mode: int = 0o444,
    ) -> dict[str, object]:
        try:
            descriptor = os.open(name, _READ_FLAGS, dir_fd=parent_fd)
        except OSError as exc:
            raise BudgetContractError("SELF_REPLAY_FAILED", f"published target cannot be opened: {name}") from exc
        try:
            before = os.fstat(descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or stat.S_IMODE(before.st_mode) != expected_mode
                or before.st_nlink != 1
                or before.st_size != expected_size
            ):
                raise BudgetContractError("SELF_REPLAY_FAILED", "published target identity is invalid")
            digest = _sha256_descriptor(descriptor, size_bytes=expected_size)
            after = os.fstat(descriptor)
            if _signature(after) != _signature(before) or after.st_size != before.st_size:
                raise BudgetContractError("SELF_REPLAY_FAILED", "published target drifted during replay")
            if digest != expected_sha256:
                raise BudgetContractError("SELF_REPLAY_FAILED", "published target hash differs")
            return {"sha256": digest, "size_bytes": expected_size}
        finally:
            os.close(descriptor)

    def append_segment(
        self,
        channel: str,
        sequence: int,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
    ) -> dict[str, object]:
        """Append by publishing a new immutable segment, never by mutating a file."""

        channel_name = _safe_component(channel, label="channel")
        number = _exact_nonnegative_int(sequence, label="sequence")
        directory = f"channels/{channel_name}"
        with self._lock:
            self._require_open()
            expected = self._segment_next.get(channel_name, 0)
            if number != expected:
                raise BudgetContractError(
                    "SEGMENT_SEQUENCE_MISMATCH",
                    f"channel {channel_name} expected segment {expected}, received {number}",
                )
            if ("channels",) not in self._registered_directories:
                self.register_directory("channels")
            if ("channels", channel_name) not in self._registered_directories:
                self.register_directory(directory)
            record = self.publish_bytes(
                f"{directory}/segment-{number:08d}.bin",
                raw,
                maximum_bytes=maximum_bytes,
                artifact_class=artifact_class,
                arm_slot=arm_slot,
            )
            self._segment_next[channel_name] = number + 1
            return record

    def published_artifacts(self) -> list[dict[str, object]]:
        with self._lock:
            return [artifact.as_record() for artifact in self._published]

    def snapshot_root_closure(self) -> dict[str, object]:
        """Enumerate the exact retained-root descendant set and reject unsafe nodes."""

        with self._lock:
            self._require_open()
            self._require_root_identity()
            root_fd = os.dup(self._root_fd)
            retained: list[
                tuple[str, int, tuple[int, int, int, int, int, int, int, int], tuple[str, ...]]
            ] = []
            entries: list[dict[str, object]] = []
            try:
                retained.append(
                    (
                        ".",
                        root_fd,
                        _signature(os.fstat(root_fd)),
                        tuple(sorted(os.listdir(root_fd))),
                    )
                )
                index = 0
                while index < len(retained):
                    relative_directory, directory_fd, _identity, names = retained[index]
                    for name in names:
                        relative = name if relative_directory == "." else f"{relative_directory}/{name}"
                        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                        if stat.S_ISLNK(before.st_mode):
                            raise BudgetContractError("ROOT_CLOSURE_UNSAFE_NODE", f"symlink is forbidden: {relative}")
                        if stat.S_ISDIR(before.st_mode):
                            child_fd = _open_child_directory(directory_fd, name)
                            child_before = os.fstat(child_fd)
                            if _signature(child_before) != _signature(before):
                                os.close(child_fd)
                                raise BudgetContractError(
                                    "ROOT_CLOSURE_IDENTITY_DRIFT",
                                    f"directory changed while opening: {relative}",
                                )
                            child_names = tuple(sorted(os.listdir(child_fd)))
                            retained.append((relative, child_fd, _signature(child_before), child_names))
                            entries.append(
                                {
                                    "mode_octal": f"{stat.S_IMODE(child_before.st_mode):04o}",
                                    "path": relative,
                                    "type": "directory",
                                }
                            )
                        elif stat.S_ISREG(before.st_mode):
                            descriptor = os.open(name, _READ_FLAGS, dir_fd=directory_fd)
                            try:
                                opened = os.fstat(descriptor)
                                if (
                                    _signature(opened) != _signature(before)
                                    or opened.st_nlink != 1
                                ):
                                    raise BudgetContractError(
                                        "ROOT_CLOSURE_UNSAFE_NODE",
                                        f"file identity or link count is unsafe: {relative}",
                                    )
                                digest = _sha256_descriptor(descriptor, size_bytes=opened.st_size)
                                after = os.fstat(descriptor)
                                if (
                                    _signature(after) != _signature(opened)
                                    or after.st_size != opened.st_size
                                    or after.st_nlink != 1
                                ):
                                    raise BudgetContractError(
                                        "ROOT_CLOSURE_IDENTITY_DRIFT",
                                        f"file changed while hashing: {relative}",
                                    )
                                entries.append(
                                    {
                                        "mode_octal": f"{stat.S_IMODE(opened.st_mode):04o}",
                                        "path": relative,
                                        "sha256": digest,
                                        "size_bytes": opened.st_size,
                                        "type": "regular",
                                    }
                                )
                            finally:
                                os.close(descriptor)
                        else:
                            raise BudgetContractError(
                                "ROOT_CLOSURE_UNSAFE_NODE",
                                f"special node is forbidden: {relative}",
                            )
                    index += 1
                for relative, descriptor, identity, names in retained:
                    if _signature(os.fstat(descriptor)) != identity:
                        raise BudgetContractError(
                            "ROOT_CLOSURE_IDENTITY_DRIFT",
                            f"directory identity drifted: {relative}",
                        )
                    if tuple(sorted(os.listdir(descriptor))) != names:
                        raise BudgetContractError(
                            "ROOT_CLOSURE_MEMBER_DRIFT",
                            f"directory members drifted: {relative}",
                        )
                # The final linearization point rejoins the retained root to
                # its absolute no-symlink path only after every retained
                # directory signature and member set has been rechecked.
                self._require_root_identity()
                entries.sort(key=lambda item: (str(item["path"]), str(item["type"])))
                digest = hashlib.sha256(canonical_json_bytes(entries)).hexdigest()
                return {
                    "schema_version": BUDGET_CLOSURE_SCHEMA,
                    "closure_sha256": digest,
                    "entries": entries,
                    "root_path": str(self.root),
                }
            finally:
                for _relative, descriptor, _identity, _names in reversed(retained):
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

    def verify_root_closure(self, expected: object) -> dict[str, object]:
        """Fail closed unless the retained root still equals a strict snapshot."""

        checked = validate_closure_record(expected)
        if checked["root_path"] != str(self.root):
            raise BudgetContractError("ROOT_CLOSURE_MISMATCH", "closure record names a different root")
        observed = self.snapshot_root_closure()
        if observed != checked:
            raise BudgetContractError("ROOT_CLOSURE_MISMATCH", "artifact-root members or bytes drifted")
        return observed

    def contract_record(self) -> dict[str, object]:
        """Return the current hierarchical arithmetic without claiming authority."""

        with self._lock:
            self._require_open()
            return {
                "schema_version": BUDGET_CONTRACT_SCHEMA,
                "authority": {
                    "changes_certified_exact": False,
                    "changes_cut_state": False,
                    "changes_lower_bound": False,
                    "changes_production": False,
                    "changes_upper_bound": False,
                    "research_only": True,
                },
                "root": {
                    "category_limits": dict(self._root_limits),
                    "category_remaining_unassigned": dict(self._root_remaining),
                    "reserved_bytes": self.reserved_bytes,
                    "total_bytes": self.total_bytes,
                },
                "arms": {slot: self.arm_account(slot) for slot in sorted(self._arms)},
            }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                raise BudgetContractError("BROKER_ALREADY_CLOSED", "budget broker cannot close twice")
            self._closed = True
            os.close(self._root_fd)

    def __enter__(self) -> FormalBudgetBroker:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


__all__ = [
    "ARM_CONSUMED_INCOMPLETE",
    "ARM_UNSELECTED_TERMINAL",
    "ARTIFACT_CLASSES",
    "BUDGET_CLOSURE_SCHEMA",
    "BUDGET_CONTRACT_SCHEMA",
    "BUDGET_OWNERSHIP_HANDOFF_SCHEMA",
    "BUDGET_RETAINED_DIRECTORY_SCHEMA",
    "BUDGET_RETAINED_STAGING_SCHEMA",
    "BudgetContractError",
    "CONSUMPTION_STATES",
    "FORMAL_CONSUMED_INCOMPLETE",
    "FORMAL_MARKERLESS_INCOMPLETE",
    "FormalBudgetBroker",
    "PublishedArtifact",
    "RetainedDirectoryCapability",
    "RetainedStagingReservation",
    "canonical_json_bytes",
    "classify_consumption",
    "require_capabilities",
    "validate_closure_record",
]
