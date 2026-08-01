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
    descriptor = os.open("/", _DIRECTORY_FLAGS)
    transferred = False
    try:
        for component in absolute.parts[1:]:
            next_descriptor = os.open(component, _DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        transferred = True
        return descriptor
    except OSError as exc:
        raise BudgetContractError("ROOT_OPEN_FAILED", f"directory chain is unsafe: {absolute}") from exc
    finally:
        if not transferred:
            try:
                os.close(descriptor)
            except OSError:
                pass


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
    descriptor = os.dup(root_fd)
    transferred = False
    try:
        for part in parts:
            next_descriptor = _open_child_directory(descriptor, part)
            os.close(descriptor)
            descriptor = next_descriptor
        transferred = True
        return descriptor
    finally:
        if not transferred:
            try:
                os.close(descriptor)
            except OSError:
                pass


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
    ) -> None:
        self.root = root
        self._root_fd = root_fd
        self._root_identity = root_identity
        self._root_limits = dict(category_limits)
        self._root_remaining = dict(category_limits)
        self._arms: dict[str, _ArmAccount] = {}
        self._registered_directories: set[tuple[str, ...]] = {()}
        self._published: list[PublishedArtifact] = []
        self._segment_next: dict[str, int] = {}
        self._closed = False
        self._lock = threading.RLock()

    @classmethod
    def create(
        cls,
        root: Path | str,
        *,
        category_limits: Mapping[str, object],
    ) -> FormalBudgetBroker:
        """Create and retain one empty no-overwrite formal artifact root."""

        require_capabilities()
        limits = _validated_categories(category_limits, label="category_limits")
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
        metadata = os.fstat(self._root_fd)
        if _path_identity(metadata) != self._root_identity:
            raise BudgetContractError("ROOT_IDENTITY_DRIFT", "retained artifact-root identity drifted")
        try:
            path_metadata = os.stat(self.root, follow_symlinks=False)
        except OSError as exc:
            raise BudgetContractError("ROOT_PATH_DRIFT", "artifact-root path is absent") from exc
        if _path_identity(path_metadata) != self._root_identity:
            raise BudgetContractError("ROOT_PATH_DRIFT", "artifact-root path no longer names the retained root")

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
                "arm_slot": slot,
                "category_limits": dict(account.category_limits),
                "category_remaining": dict(account.category_remaining),
                "reserved_bytes": account.total_bytes,
                "spent_or_stranded_bytes": account.total_bytes - remaining,
                "unspent_reserved_bytes": remaining,
            }

    def register_directory(self, relative_path: str) -> str:
        """Create a fixed directory path without accepting pre-existing members."""

        parts = _relative_parts(relative_path, allow_dot=True)
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
                    next_descriptor = _open_child_directory(descriptor, part)
                    os.close(descriptor)
                    descriptor = next_descriptor
                    current = candidate
            finally:
                os.close(descriptor)
            return "." if not parts else str(PurePosixPath(*parts))

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
        remaining = account.category_remaining.get(artifact_class, 0)
        if maximum_bytes > remaining:
            raise BudgetContractError(
                "ARM_BUDGET_EXCEEDED",
                f"arm {arm_slot} requests {maximum_bytes} {artifact_class} bytes but {remaining} remain",
            )
        account.category_remaining[artifact_class] = remaining - maximum_bytes

    def publish_bytes(
        self,
        relative_path: str,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        arm_slot: str | None = None,
        acknowledgement: Callable[[dict[str, object]], object] | None = None,
    ) -> dict[str, object]:
        """Publish one immutable artifact from preallocated same-directory staging."""

        if not isinstance(raw, bytes):
            raise BudgetContractError("INVALID_PAYLOAD", "payload must be exact bytes")
        maximum = _exact_nonnegative_int(maximum_bytes, label="maximum_bytes")
        if maximum <= 0 or len(raw) > maximum:
            raise BudgetContractError("PAYLOAD_EXCEEDS_MAXIMUM", "payload is larger than its fixed allocation")
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
                    os.posix_fallocate(descriptor, 0, maximum)
                    _write_all_at(descriptor, raw)
                    os.fsync(descriptor)
                    os.ftruncate(descriptor, len(raw))
                    metadata = os.fstat(descriptor)
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != len(raw):
                        raise BudgetContractError("STAGING_IDENTITY_INVALID", "staging identity or size is invalid")
                    digest = _sha256_descriptor(descriptor, size_bytes=len(raw))
                    os.fchmod(descriptor, 0o444)
                    os.fsync(descriptor)
                    _rename_noreplace(parent_fd, staging_name, target_name)
                    published = True
                    os.fsync(parent_fd)
                    replay = self._replay_published_at(
                        parent_fd,
                        target_name,
                        expected_size=len(raw),
                        expected_sha256=digest,
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
    ) -> dict[str, object]:
        try:
            descriptor = os.open(name, _READ_FLAGS, dir_fd=parent_fd)
        except OSError as exc:
            raise BudgetContractError("SELF_REPLAY_FAILED", f"published target cannot be opened: {name}") from exc
        try:
            before = os.fstat(descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or stat.S_IMODE(before.st_mode) != 0o444
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
                                if _signature(opened) != _signature(before):
                                    raise BudgetContractError(
                                        "ROOT_CLOSURE_IDENTITY_DRIFT",
                                        f"file changed while opening: {relative}",
                                    )
                                digest = _sha256_descriptor(descriptor, size_bytes=opened.st_size)
                                after = os.fstat(descriptor)
                                if _signature(after) != _signature(opened) or after.st_size != opened.st_size:
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
    "BudgetContractError",
    "CONSUMPTION_STATES",
    "FORMAL_CONSUMED_INCOMPLETE",
    "FORMAL_MARKERLESS_INCOMPLETE",
    "FormalBudgetBroker",
    "PublishedArtifact",
    "canonical_json_bytes",
    "classify_consumption",
    "require_capabilities",
    "validate_closure_record",
]
