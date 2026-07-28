"""Minimal, reusable contracts for isolated research runs.

This module is developer/research infrastructure.  It deliberately knows
nothing about solver semantics, proof status, cuts, bounds, or production
authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import NoReturn, TypeAlias, cast


JsonScalar: TypeAlias = None | bool | int | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_CONFIG_SCHEMA = "research_run_config_v1"
_RECEIPT_SCHEMA = "research_run_receipt_v1"
_IDENTITY_GRAPH_SCHEMA = "artifact_identity_graph_v1"
ARTIFACT_ROOT_MANIFEST_SCHEMA = "research_artifact_root_manifest_v1"
ISOLATED_PYTHON_PROCESS_SCHEMA = "isolated_python_process_contract_v1"
TERMINAL_RECEIPT_PATH = "receipt.json"
_OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd
_SCANDIR_SUPPORTS_FD = os.scandir in os.supports_fd

_ARTIFACT_ROOT_ENTRY_TYPES = frozenset({"directory", "regular_file"})


class ResearchRunContractError(ValueError):
    """Fail-closed contract violation with a stable machine-readable code."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    """Detached identity of one regular file."""

    path: str
    sha256: str
    size_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class StableSnapshot:
    """Bytes and identity observed through one stable file descriptor."""

    identity: ArtifactIdentity
    data: bytes
    stat_signature: tuple[int, ...]

    @property
    def path(self) -> Path:
        return Path(self.identity.path)

    @property
    def sha256(self) -> str:
        return self.identity.sha256

    @property
    def size_bytes(self) -> int:
        return self.identity.size_bytes


@dataclass(frozen=True, slots=True)
class IdentityGraphReplay:
    """Verified snapshots plus a canonical digest of their detached identities."""

    snapshots: Mapping[str, StableSnapshot]
    graph_sha256: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema": _IDENTITY_GRAPH_SCHEMA,
            "artifacts": {
                label: self.snapshots[label].identity.as_dict()
                for label in sorted(self.snapshots)
            },
            "graph_sha256": self.graph_sha256,
        }


@dataclass(frozen=True, slots=True)
class IsolatedReplayObservation:
    """Raw subprocess observation; no experiment-specific status is inferred."""

    argv: tuple[str, ...]
    returncode: int | None
    timed_out: bool
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True, slots=True)
class ArtifactRootEntry:
    """One normalized descendant in a research artifact root."""

    path: str
    node_type: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "type": self.node_type}


def _fail(code: str, detail: str) -> NoReturn:
    raise ResearchRunContractError(code, detail)


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _stat_signature(item: os.stat_result) -> tuple[int, ...]:
    return (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_uid,
        item.st_gid,
        item.st_size,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )


def _validate_sha256(value: object, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail("SHA256_INVALID", label)
    return cast(str, value)


def _validate_size(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail("SIZE_INVALID", label)
    return cast(int, value)


def _validate_artifact_identity(
    value: ArtifactIdentity | Mapping[str, object],
    label: str,
) -> ArtifactIdentity:
    if isinstance(value, ArtifactIdentity):
        candidate = value.as_dict()
    elif isinstance(value, Mapping):
        candidate = dict(value)
    else:
        _fail("IDENTITY_INVALID", f"{label}: expected an artifact identity")
    if set(candidate) != {"path", "sha256", "size_bytes"}:
        _fail("IDENTITY_INVALID", f"{label}: identity keys differ")
    path = candidate["path"]
    if type(path) is not str or not Path(path).is_absolute():
        _fail("IDENTITY_INVALID", f"{label}: path must be absolute")
    return ArtifactIdentity(
        path=cast(str, path),
        sha256=_validate_sha256(candidate["sha256"], f"{label}.sha256"),
        size_bytes=_validate_size(candidate["size_bytes"], f"{label}.size_bytes"),
    )


def _validate_json_value(value: object, path: str = "$") -> JsonValue:
    if value is None:
        return None
    if type(value) is bool:
        return cast(bool, value)
    if type(value) is int:
        return cast(int, value)
    if type(value) is str:
        return cast(str, value)
    if type(value) is list:
        return [
            _validate_json_value(item, f"{path}[{index}]")
            for index, item in enumerate(cast(list[object], value))
        ]
    if type(value) is dict:
        result: dict[str, JsonValue] = {}
        for key, item in cast(dict[object, object], value).items():
            if type(key) is not str:
                _fail("NON_JSON_VALUE", f"{path}: object key is not a string")
            string_key = cast(str, key)
            result[string_key] = _validate_json_value(item, f"{path}.{string_key}")
        return result
    _fail("NON_JSON_VALUE", f"{path}: unsupported value type {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    """Encode the deliberately small JSON value domain with exactly one final LF."""

    normalized = _validate_json_value(value)
    try:
        rendered = json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return (rendered + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        _fail("NON_JSON_VALUE", str(exc))


def _reject_symlink_chain(path: Path, *, include_leaf: bool) -> None:
    """Reject known symlink components before an O_NOFOLLOW descriptor open."""

    parts = path.parts
    current = Path(parts[0])
    stop = len(parts) - 1
    for part in parts[1:stop]:
        current = current / part
        try:
            item = os.lstat(current)
        except FileNotFoundError:
            _fail("PATH_COMPONENT_MISSING", str(current))
        if stat.S_ISLNK(item.st_mode):
            _fail("SYMLINK_REJECTED", str(current))
        if not stat.S_ISDIR(item.st_mode):
            _fail("PATH_COMPONENT_NOT_DIRECTORY", str(current))
    if include_leaf:
        try:
            item = os.lstat(path)
        except FileNotFoundError:
            return
        if stat.S_ISLNK(item.st_mode):
            _fail("SYMLINK_REJECTED", str(path))


def _directory_open_flags() -> int:
    if (
        not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
        or not _OPEN_SUPPORTS_DIR_FD
        or not _SCANDIR_SUPPORTS_FD
    ):
        _fail(
            "PLATFORM_CAPABILITY_UNAVAILABLE",
            "descriptor-relative O_DIRECTORY|O_NOFOLLOW directory opens are required",
        )
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
    )


def _open_absolute_directory_no_symlinks(
    path: Path | str,
    *,
    error_code: str,
) -> int:
    """Open one absolute directory through descriptor-relative no-follow steps."""

    absolute = _absolute(path)
    parts = absolute.parts
    if not absolute.is_absolute() or not parts or not absolute.anchor:
        _fail(error_code, f"absolute directory path required: {absolute}")
    flags = _directory_open_flags()
    opened: list[int] = []
    try:
        opened.append(os.open(absolute.anchor, flags))
        for part in parts[1:]:
            opened.append(os.open(part, flags, dir_fd=opened[-1]))
    except BaseException as exc:
        for descriptor in reversed(opened):
            try:
                os.close(descriptor)
            except OSError:
                pass
        if isinstance(exc, OSError):
            _fail(error_code, f"{absolute}: {exc}")
        raise
    if not opened:
        _fail(error_code, f"{absolute}: directory open produced no descriptor")
    descriptor = opened.pop()
    close_error: OSError | None = None
    for ancestor_fd in reversed(opened):
        try:
            os.close(ancestor_fd)
        except OSError as exc:
            if close_error is None:
                close_error = exc
    if close_error is not None:
        try:
            os.close(descriptor)
        except OSError:
            pass
        _fail(error_code, f"{absolute}: ancestor descriptor close failed: {close_error}")
    return descriptor


def _close_descriptor_after_validation_failure(
    descriptor: int,
    detail: str,
) -> str:
    """Close an owned descriptor without replacing the stable contract error."""

    try:
        os.close(descriptor)
    except OSError as close_error:
        return f"{detail}; descriptor close failed: {close_error}"
    return detail


def _close_descriptor_preserving_error(
    descriptor: int,
    error: BaseException,
) -> None:
    """Release an owned descriptor while preserving a non-contract exception."""

    try:
        os.close(descriptor)
    except OSError as close_error:
        error.add_note(f"descriptor close failed: {close_error}")


def read_stable_snapshot(
    path: Path | str,
    *,
    expected_sha256: str | None = None,
    expected_size_bytes: int | None = None,
    max_bytes: int | None = None,
) -> StableSnapshot:
    """Read/hash one regular file through one descriptor and reject identity drift."""

    absolute = _absolute(path)
    _reject_symlink_chain(absolute, include_leaf=True)
    if expected_sha256 is not None:
        expected_sha256 = _validate_sha256(expected_sha256, "expected_sha256")
    if expected_size_bytes is not None:
        expected_size_bytes = _validate_size(expected_size_bytes, "expected_size_bytes")
    if max_bytes is not None:
        max_bytes = _validate_size(max_bytes, "max_bytes")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        _fail("INPUT_OPEN_FAILED", f"{absolute}: {exc}")
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            _fail("NON_REGULAR_INPUT", str(absolute))
        if before.st_size < 0:
            _fail("SIZE_INVALID", str(absolute))
        if max_bytes is not None and before.st_size > max_bytes:
            _fail("INPUT_TOO_LARGE", str(absolute))
        if expected_size_bytes is not None and before.st_size != expected_size_bytes:
            _fail("SIZE_MISMATCH", str(absolute))

        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1 << 20, remaining))
            if not chunk:
                _fail("INPUT_CHANGED", f"{absolute}: truncated during read")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            _fail("INPUT_CHANGED", f"{absolute}: grew during read")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    if _stat_signature(before) != _stat_signature(after):
        _fail("INPUT_CHANGED", f"{absolute}: descriptor identity drifted")
    data = b"".join(chunks)
    if len(data) != before.st_size:
        _fail("INPUT_CHANGED", f"{absolute}: byte count drifted")
    digest = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        _fail("SHA256_MISMATCH", str(absolute))
    return StableSnapshot(
        identity=ArtifactIdentity(
            path=str(absolute),
            sha256=digest,
            size_bytes=len(data),
        ),
        data=data,
        stat_signature=_stat_signature(after),
    )


def _relative_parts(relative: Path | str) -> tuple[str, ...]:
    candidate = Path(relative)
    if candidate.is_absolute():
        _fail("PATH_ESCAPE", f"absolute output path rejected: {candidate}")
    parts = candidate.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        _fail("PATH_ESCAPE", f"invalid root-relative path: {candidate}")
    return parts


@dataclass(frozen=True, slots=True)
class ExclusiveRunRoot:
    """An exclusively created run directory with root-scoped no-overwrite writes."""

    path: Path
    _device: int
    _inode: int

    @classmethod
    def create(cls, path: Path | str, *, mode: int = 0o700) -> "ExclusiveRunRoot":
        absolute = _absolute(path)
        if type(mode) is not int or mode < 0 or mode > 0o777:
            _fail("MODE_INVALID", str(mode))
        _reject_symlink_chain(absolute, include_leaf=False)
        try:
            os.mkdir(absolute, mode)
        except FileExistsError:
            _fail("NO_OVERWRITE_COLLISION", str(absolute))
        except OSError as exc:
            _fail("RUN_ROOT_CREATE_FAILED", f"{absolute}: {exc}")
        item = os.lstat(absolute)
        if not stat.S_ISDIR(item.st_mode) or stat.S_ISLNK(item.st_mode):
            _fail("RUN_ROOT_INVALID", str(absolute))
        return cls(path=absolute, _device=item.st_dev, _inode=item.st_ino)

    def _open_root(self) -> int:
        descriptor = _open_absolute_directory_no_symlinks(
            self.path,
            error_code="RUN_ROOT_OPEN_FAILED",
        )
        try:
            item = os.fstat(descriptor)
        except OSError as exc:
            detail = _close_descriptor_after_validation_failure(
                descriptor,
                f"{self.path}: {exc}",
            )
            _fail("RUN_ROOT_OPEN_FAILED", detail)
        if (
            not stat.S_ISDIR(item.st_mode)
            or item.st_dev != self._device
            or item.st_ino != self._inode
        ):
            detail = _close_descriptor_after_validation_failure(
                descriptor,
                str(self.path),
            )
            _fail("RUN_ROOT_IDENTITY_DRIFT", detail)
        return descriptor

    def _open_parent(self, parts: tuple[str, ...]) -> tuple[int, str]:
        descriptor = self._open_root()
        directory_flags = _directory_open_flags()
        try:
            for part in parts[:-1]:
                next_descriptor = os.open(part, directory_flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = next_descriptor
        except OSError as exc:
            os.close(descriptor)
            _fail("OUTPUT_PARENT_INVALID", f"{self.path.joinpath(*parts[:-1])}: {exc}")
        return descriptor, parts[-1]

    def mkdir(self, relative: Path | str, *, mode: int = 0o700) -> Path:
        """Create exactly one root-relative directory; parents must already exist."""

        if type(mode) is not int or mode < 0 or mode > 0o777:
            _fail("MODE_INVALID", str(mode))
        parts = _relative_parts(relative)
        parent_fd, leaf = self._open_parent(parts)
        try:
            try:
                os.mkdir(leaf, mode, dir_fd=parent_fd)
            except FileExistsError:
                _fail("NO_OVERWRITE_COLLISION", str(self.path.joinpath(*parts)))
            except OSError as exc:
                _fail("OUTPUT_DIRECTORY_CREATE_FAILED", str(exc))
        finally:
            os.close(parent_fd)
        return self.path.joinpath(*parts)

    def write_bytes(
        self,
        relative: Path | str,
        data: bytes,
        *,
        mode: int = 0o600,
    ) -> ArtifactIdentity:
        """Exclusively write bytes below this run root and return their identity."""

        if type(data) is not bytes:
            _fail("OUTPUT_BYTES_INVALID", type(data).__name__)
        if type(mode) is not int or mode < 0 or mode > 0o777:
            _fail("MODE_INVALID", str(mode))
        parts = _relative_parts(relative)
        parent_fd, leaf = self._open_parent(parts)
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            try:
                descriptor = os.open(leaf, flags, mode, dir_fd=parent_fd)
            except FileExistsError:
                _fail("NO_OVERWRITE_COLLISION", str(self.path.joinpath(*parts)))
            except OSError as exc:
                _fail("OUTPUT_OPEN_FAILED", str(exc))
            try:
                view = memoryview(data)
                while view:
                    written = os.write(descriptor, view)
                    if written <= 0:
                        _fail("OUTPUT_WRITE_FAILED", str(self.path.joinpath(*parts)))
                    view = view[written:]
                os.fsync(descriptor)
                item = os.fstat(descriptor)
            finally:
                os.close(descriptor)
        finally:
            os.close(parent_fd)
        if not stat.S_ISREG(item.st_mode) or item.st_size != len(data):
            _fail("OUTPUT_WRITE_FAILED", str(self.path.joinpath(*parts)))
        return ArtifactIdentity(
            path=str(self.path.joinpath(*parts)),
            sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
        )

    def write_json(
        self,
        relative: Path | str,
        value: object,
        *,
        mode: int = 0o600,
    ) -> ArtifactIdentity:
        return self.write_bytes(relative, canonical_json_bytes(value), mode=mode)


def _manifest_relative_path(
    value: object,
    label: str,
    *,
    allow_terminal_receipt: bool = False,
) -> str:
    if type(value) is not str or not value:
        _fail("ARTIFACT_ROOT_MANIFEST_INVALID", f"{label}: path must be non-empty text")
    path = cast(str, value)
    try:
        path.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        _fail("ARTIFACT_ROOT_MANIFEST_INVALID", f"{label}: path is not UTF-8 encodable")
    parts = path.split("/")
    if (
        path.startswith("/")
        or path.endswith("/")
        or "\\" in path
        or "\x00" in path
        or any(part in {"", ".", ".."} for part in parts)
    ):
        _fail("ARTIFACT_ROOT_PATH_ESCAPE", f"{label}: {path!r}")
    if parts[0] == TERMINAL_RECEIPT_PATH and (
        not allow_terminal_receipt or path != TERMINAL_RECEIPT_PATH
    ):
        _fail(
            "ARTIFACT_ROOT_RECEIPT_RESERVED",
            f"{label}: {TERMINAL_RECEIPT_PATH} is not a manifest member",
        )
    return path


def validate_artifact_root_manifest(value: object) -> dict[str, object]:
    """Validate the canonical path/type manifest excluding the terminal receipt."""

    if type(value) is not dict or set(value) != {"schema", "entries"}:
        _fail("ARTIFACT_ROOT_MANIFEST_INVALID", "manifest keys differ")
    record = cast(dict[str, object], value)
    if record["schema"] != ARTIFACT_ROOT_MANIFEST_SCHEMA:
        _fail("ARTIFACT_ROOT_MANIFEST_INVALID", "manifest schema differs")
    raw_entries = record["entries"]
    if type(raw_entries) is not list:
        _fail("ARTIFACT_ROOT_MANIFEST_INVALID", "entries must be an array")

    entries: list[dict[str, str]] = []
    entry_types: dict[str, str] = {}
    for index, raw_entry in enumerate(cast(list[object], raw_entries)):
        label = f"entries[{index}]"
        if type(raw_entry) is not dict or set(raw_entry) != {"path", "type"}:
            _fail("ARTIFACT_ROOT_MANIFEST_INVALID", f"{label}: keys differ")
        entry = cast(dict[str, object], raw_entry)
        path = _manifest_relative_path(entry["path"], f"{label}.path")
        node_type = entry["type"]
        if type(node_type) is not str or node_type not in _ARTIFACT_ROOT_ENTRY_TYPES:
            _fail("ARTIFACT_ROOT_MANIFEST_INVALID", f"{label}.type")
        if path in entry_types:
            _fail("ARTIFACT_ROOT_MANIFEST_INVALID", f"duplicate path: {path}")
        entry_types[path] = cast(str, node_type)
        entries.append({"path": path, "type": cast(str, node_type)})

    sorted_entries = sorted(entries, key=lambda item: item["path"])
    if entries != sorted_entries:
        _fail("ARTIFACT_ROOT_MANIFEST_INVALID", "entries are not path-sorted")
    for path in entry_types:
        parts = path.split("/")
        for depth in range(1, len(parts)):
            parent = "/".join(parts[:depth])
            if entry_types.get(parent) != "directory":
                _fail(
                    "ARTIFACT_ROOT_MANIFEST_INVALID",
                    f"{path}: parent {parent!r} is absent or not a directory",
                )
    return {
        "schema": ARTIFACT_ROOT_MANIFEST_SCHEMA,
        "entries": entries,
    }


def _open_artifact_root(
    root: ExclusiveRunRoot | Path | str,
) -> tuple[int, Path, tuple[int, ...]]:
    if isinstance(root, ExclusiveRunRoot):
        descriptor = root._open_root()
        root_path = root.path
    else:
        root_path = _absolute(root)
        descriptor = _open_absolute_directory_no_symlinks(
            root_path,
            error_code="ARTIFACT_ROOT_OPEN_FAILED",
        )
    try:
        item = os.fstat(descriptor)
        root_signature = _stat_signature(item)
    except OSError as exc:
        detail = _close_descriptor_after_validation_failure(
            descriptor,
            f"{root_path}: {exc}",
        )
        _fail("ARTIFACT_ROOT_OPEN_FAILED", detail)
    except BaseException as exc:
        _close_descriptor_preserving_error(descriptor, exc)
        raise
    if not stat.S_ISDIR(item.st_mode):
        detail = _close_descriptor_after_validation_failure(
            descriptor,
            str(root_path),
        )
        _fail("ARTIFACT_ROOT_INVALID", detail)
    return descriptor, root_path, root_signature


def _artifact_root_entries(
    root: ExclusiveRunRoot | Path | str,
) -> tuple[ArtifactRootEntry, ...]:
    directory_flags = _directory_open_flags()
    root_fd, root_path, root_signature = _open_artifact_root(root)
    entries: list[ArtifactRootEntry] = []
    opened_directories: list[tuple[int, tuple[str, ...], tuple[int, ...]]] = [
        (root_fd, (), root_signature)
    ]

    def walk(descriptor: int, prefix: tuple[str, ...]) -> None:
        try:
            with os.scandir(descriptor) as iterator:
                names = sorted(entry.name for entry in iterator)
        except OSError as exc:
            _fail(
                "ARTIFACT_ROOT_ENUMERATION_FAILED",
                f"{root_path.joinpath(*prefix)}: {exc}",
            )
        for name in names:
            relative = "/".join((*prefix, name))
            _manifest_relative_path(
                relative,
                "observed path",
                allow_terminal_receipt=True,
            )
            try:
                item = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except OSError as exc:
                _fail(
                    "ARTIFACT_ROOT_ENUMERATION_FAILED",
                    f"{root_path.joinpath(*prefix, name)}: {exc}",
                )
            if stat.S_ISLNK(item.st_mode):
                _fail(
                    "ARTIFACT_ROOT_SYMLINK_REJECTED",
                    str(root_path.joinpath(*prefix, name)),
                )
            if stat.S_ISREG(item.st_mode):
                entries.append(ArtifactRootEntry(relative, "regular_file"))
                continue
            if not stat.S_ISDIR(item.st_mode):
                _fail(
                    "ARTIFACT_ROOT_SPECIAL_NODE_REJECTED",
                    str(root_path.joinpath(*prefix, name)),
                )
            entries.append(ArtifactRootEntry(relative, "directory"))
            try:
                child_fd = os.open(name, directory_flags, dir_fd=descriptor)
            except OSError as exc:
                _fail(
                    "ARTIFACT_ROOT_ENUMERATION_FAILED",
                    f"{root_path.joinpath(*prefix, name)}: {exc}",
                )
            child_prefix = (*prefix, name)
            try:
                opened = os.fstat(child_fd)
                child_signature = _stat_signature(opened)
                if opened.st_dev != item.st_dev or opened.st_ino != item.st_ino:
                    _fail(
                        "ARTIFACT_ROOT_CHANGED",
                        str(root_path.joinpath(*prefix, name)),
                    )
                opened_directories.append(
                    (child_fd, child_prefix, child_signature)
                )
            except OSError as exc:
                detail = _close_descriptor_after_validation_failure(
                    child_fd,
                    f"{root_path.joinpath(*prefix, name)}: {exc}",
                )
                _fail(
                    "ARTIFACT_ROOT_CHANGED",
                    detail,
                )
            except BaseException as exc:
                _close_descriptor_preserving_error(child_fd, exc)
                raise
            walk(child_fd, child_prefix)

    primary_error: BaseException | None = None
    try:
        walk(root_fd, ())
    except BaseException as exc:
        primary_error = exc

    finalize_issues: list[str] = []
    for descriptor, prefix, initial_signature in reversed(opened_directories):
        display_path = str(root_path.joinpath(*prefix))
        try:
            final_signature = _stat_signature(os.fstat(descriptor))
        except OSError as exc:
            finalize_issues.append(f"{display_path}: fstat failed: {exc}")
        else:
            if final_signature != initial_signature:
                finalize_issues.append(f"{display_path}: signature changed")
        try:
            os.close(descriptor)
        except OSError as exc:
            finalize_issues.append(f"{display_path}: close failed: {exc}")

    if primary_error is not None:
        if finalize_issues:
            primary_error.add_note(
                f"artifact-root finalization issues: {finalize_issues!r}"
            )
        raise primary_error
    if finalize_issues:
        _fail(
            "ARTIFACT_ROOT_CHANGED",
            f"artifact-root finalization issues: {finalize_issues!r}",
        )
    return tuple(sorted(entries, key=lambda item: item.path))


def build_artifact_root_manifest(
    root: ExclusiveRunRoot | Path | str,
) -> dict[str, object]:
    """Enumerate a pre-receipt root and build its exact descendant manifest."""

    entries = _artifact_root_entries(root)
    if any(entry.path == TERMINAL_RECEIPT_PATH for entry in entries):
        _fail(
            "ARTIFACT_ROOT_RECEIPT_STATE_INVALID",
            f"{TERMINAL_RECEIPT_PATH} exists before manifest construction",
        )
    return {
        "schema": ARTIFACT_ROOT_MANIFEST_SCHEMA,
        "entries": [entry.as_dict() for entry in entries],
    }


def verify_artifact_root_closure(
    root: ExclusiveRunRoot | Path | str,
    manifest: object,
    *,
    receipt_present: bool,
) -> None:
    """Verify that the manifest plus the reserved receipt is the whole root."""

    if type(receipt_present) is not bool:
        _fail("ARTIFACT_ROOT_STATE_INVALID", "receipt_present must be bool")
    normalized = validate_artifact_root_manifest(manifest)
    expected = {
        cast(str, entry["path"]): cast(str, entry["type"])
        for entry in cast(list[dict[str, object]], normalized["entries"])
    }
    if receipt_present:
        expected[TERMINAL_RECEIPT_PATH] = "regular_file"
    observed = {
        entry.path: entry.node_type
        for entry in _artifact_root_entries(root)
    }
    if observed != expected:
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        type_mismatch = sorted(
            path
            for path in set(expected) & set(observed)
            if expected[path] != observed[path]
        )
        _fail(
            "ARTIFACT_ROOT_CLOSURE_MISMATCH",
            f"missing={missing!r}; extra={extra!r}; type_mismatch={type_mismatch!r}",
        )


def require_isolated_python_process() -> dict[str, object]:
    """Require interpreter-enforced isolation and bytecode suppression."""

    observed = {
        "isolated": sys.flags.isolated,
        "ignore_environment": sys.flags.ignore_environment,
        "no_user_site": sys.flags.no_user_site,
        "safe_path": bool(getattr(sys.flags, "safe_path", False)),
        "dont_write_bytecode_flag": sys.flags.dont_write_bytecode,
        "dont_write_bytecode_runtime": sys.dont_write_bytecode,
    }
    expected = {
        "isolated": 1,
        "ignore_environment": 1,
        "no_user_site": 1,
        "safe_path": True,
        "dont_write_bytecode_flag": 1,
        "dont_write_bytecode_runtime": True,
    }
    if observed != expected:
        _fail(
            "PYTHON_PROCESS_CONTRACT_INVALID",
            f"expected={expected!r}; observed={observed!r}",
        )
    return {
        "schema": ISOLATED_PYTHON_PROCESS_SCHEMA,
        "required_argv_flags": ["-I", "-B"],
        "observed": observed,
    }


def make_research_run_config(*, experiment_id: str, payload: object) -> dict[str, object]:
    """Construct a canonicalizable config envelope without interpreting payload."""

    if type(experiment_id) is not str or not experiment_id:
        _fail("EXPERIMENT_ID_INVALID", repr(experiment_id))
    return {
        "schema": _CONFIG_SCHEMA,
        "experiment_id": experiment_id,
        "payload": _validate_json_value(payload, "$.payload"),
    }


def validate_research_run_config(value: object) -> dict[str, object]:
    """Validate only the common config envelope; experiment payload stays opaque."""

    if type(value) is not dict or set(value) != {"schema", "experiment_id", "payload"}:
        _fail("CONFIG_ENVELOPE_INVALID", "config envelope keys differ")
    record = cast(dict[str, object], value)
    if record["schema"] != _CONFIG_SCHEMA:
        _fail("CONFIG_ENVELOPE_INVALID", "config schema differs")
    experiment_id = record["experiment_id"]
    if type(experiment_id) is not str:
        _fail("EXPERIMENT_ID_INVALID", repr(experiment_id))
    return make_research_run_config(
        experiment_id=cast(str, experiment_id),
        payload=record["payload"],
    )


def make_research_run_receipt(
    *,
    experiment_id: str,
    config_identity: ArtifactIdentity | Mapping[str, object],
    artifacts: Mapping[str, ArtifactIdentity | Mapping[str, object]],
    payload: object,
) -> dict[str, object]:
    """Construct a receipt binding one config and a named artifact identity graph."""

    if type(experiment_id) is not str or not experiment_id:
        _fail("EXPERIMENT_ID_INVALID", repr(experiment_id))
    normalized_artifacts: dict[str, object] = {}
    for label in sorted(artifacts):
        if type(label) is not str or not label:
            _fail("ARTIFACT_LABEL_INVALID", repr(label))
        normalized_artifacts[label] = _validate_artifact_identity(
            artifacts[label],
            f"artifacts.{label}",
        ).as_dict()
    return {
        "schema": _RECEIPT_SCHEMA,
        "experiment_id": experiment_id,
        "config_identity": _validate_artifact_identity(
            config_identity,
            "config_identity",
        ).as_dict(),
        "artifacts": normalized_artifacts,
        "payload": _validate_json_value(payload, "$.payload"),
    }


def validate_research_run_receipt(value: object) -> dict[str, object]:
    """Validate only the common receipt envelope and detached identities."""

    expected = {
        "schema",
        "experiment_id",
        "config_identity",
        "artifacts",
        "payload",
    }
    if type(value) is not dict or set(value) != expected:
        _fail("RECEIPT_ENVELOPE_INVALID", "receipt envelope keys differ")
    record = cast(dict[str, object], value)
    if record["schema"] != _RECEIPT_SCHEMA:
        _fail("RECEIPT_ENVELOPE_INVALID", "receipt schema differs")
    experiment_id = record["experiment_id"]
    if type(experiment_id) is not str:
        _fail("EXPERIMENT_ID_INVALID", repr(experiment_id))
    artifacts = record["artifacts"]
    if not isinstance(artifacts, Mapping):
        _fail("RECEIPT_ENVELOPE_INVALID", "artifacts must be an object")
    return make_research_run_receipt(
        experiment_id=cast(str, experiment_id),
        config_identity=cast(Mapping[str, object], record["config_identity"]),
        artifacts=cast(
            Mapping[str, ArtifactIdentity | Mapping[str, object]],
            artifacts,
        ),
        payload=record["payload"],
    )


def replay_identity_graph(
    artifacts: Mapping[str, ArtifactIdentity | Mapping[str, object]],
    *,
    max_bytes_per_artifact: int | None = None,
) -> IdentityGraphReplay:
    """Re-read all named artifacts, verify identities, and hash the identity graph."""

    snapshots: dict[str, StableSnapshot] = {}
    identities: dict[str, object] = {}
    for label in sorted(artifacts):
        if type(label) is not str or not label:
            _fail("ARTIFACT_LABEL_INVALID", repr(label))
        expected = _validate_artifact_identity(artifacts[label], label)
        snapshot = read_stable_snapshot(
            expected.path,
            expected_sha256=expected.sha256,
            expected_size_bytes=expected.size_bytes,
            max_bytes=max_bytes_per_artifact,
        )
        snapshots[label] = snapshot
        identities[label] = snapshot.identity.as_dict()
    graph = {
        "schema": _IDENTITY_GRAPH_SCHEMA,
        "artifacts": identities,
    }
    return IdentityGraphReplay(
        snapshots=snapshots,
        graph_sha256=hashlib.sha256(canonical_json_bytes(graph)).hexdigest(),
    )


def _captured_bytes(value: bytes | str | None) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8", errors="surrogateescape")


def run_isolated_replay(
    script: Path | str,
    arguments: Sequence[str] = (),
    *,
    cwd: Path | str | None = None,
    environment: Mapping[str, str] | None = None,
    stdin: bytes | None = None,
    timeout_seconds: int | float | None = None,
) -> IsolatedReplayObservation:
    """Run a Python replay with ``-I -B`` and an exact caller-controlled environment."""

    script_path = _absolute(script)
    if isinstance(arguments, (str, bytes)) or any(type(argument) is not str for argument in arguments):
        _fail("REPLAY_ARGUMENT_INVALID", "all arguments must be strings")
    if stdin is not None and type(stdin) is not bytes:
        _fail("REPLAY_STDIN_INVALID", type(stdin).__name__)
    if timeout_seconds is not None and (
        type(timeout_seconds) not in {int, float}
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        _fail("REPLAY_TIMEOUT_INVALID", repr(timeout_seconds))

    child_environment: dict[str, str] = {}
    if environment is not None:
        for key, value in environment.items():
            if (
                type(key) is not str
                or not key
                or "=" in key
                or "\x00" in key
                or type(value) is not str
                or "\x00" in value
            ):
                _fail("REPLAY_ENVIRONMENT_INVALID", repr(key))
            if key in {"PYTHONHOME", "PYTHONPATH"}:
                _fail("REPLAY_ENVIRONMENT_INVALID", f"{key} is forbidden")
            child_environment[key] = value

    argv = (str(_absolute(sys.executable)), "-I", "-B", str(script_path), *tuple(arguments))
    try:
        completed = subprocess.run(
            argv,
            cwd=None if cwd is None else _absolute(cwd),
            env=child_environment,
            input=b"" if stdin is None else stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
            shell=False,
            close_fds=True,
        )
    except OSError as exc:
        _fail("REPLAY_LAUNCH_FAILED", f"{argv[0]}: {exc}")
    except subprocess.TimeoutExpired as exc:
        return IsolatedReplayObservation(
            argv=argv,
            returncode=None,
            timed_out=True,
            stdout=_captured_bytes(exc.stdout),
            stderr=_captured_bytes(exc.stderr),
        )
    return IsolatedReplayObservation(
        argv=argv,
        returncode=completed.returncode,
        timed_out=False,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
