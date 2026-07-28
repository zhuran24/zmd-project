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
        flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            descriptor = os.open(self.path, flags)
        except OSError as exc:
            _fail("RUN_ROOT_OPEN_FAILED", f"{self.path}: {exc}")
        item = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(item.st_mode)
            or item.st_dev != self._device
            or item.st_ino != self._inode
        ):
            os.close(descriptor)
            _fail("RUN_ROOT_IDENTITY_DRIFT", str(self.path))
        return descriptor

    def _open_parent(self, parts: tuple[str, ...]) -> tuple[int, str]:
        descriptor = self._open_root()
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
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
    """Run a Python replay with ``-I`` and an exact, caller-controlled environment."""

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

    argv = (sys.executable, "-I", str(script_path), *tuple(arguments))
    try:
        completed = subprocess.run(
            argv,
            cwd=None if cwd is None else _absolute(cwd),
            env=child_environment,
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
            shell=False,
            close_fds=True,
        )
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
