#!/usr/bin/env python3
"""Explicit AB16 pytest collection evidence protocol.

This module is research/developer infrastructure for the AB16 preflight only.
It does not authorize a campaign, a solver, or a certified result.

The caller creates one :class:`AB16CollectionSession`, passes that exact object
to the explicitly loaded AB16 pytest plugin, and validates the two records
after ``pytest.main`` returns.  No environment variable, ambient ``conftest``
hook, plugin-name lookup, or current-working-directory convention participates
in the handoff.
"""

from __future__ import annotations

from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import tempfile
from typing import BinaryIO, Mapping, Sequence


COLLECTION_STAGE_SCHEMA = "ab16-pytest-collection-stage-v1"
COLLECTION_TERMINAL_SCHEMA = "ab16-pytest-collection-terminal-v1"
COLLECTION_BINDING_SCHEMA = "noncert-cuts-ab16-pytest-collection-binding-v1"
COLLECTION_STDOUT_PREFIX = b"AB16_PYTEST_COLLECTION_RECORD="
COLLECTION_MANIFEST_DOMAIN = b"ab16-pytest-nodeid-path-manifest-v1\0"
COLLECTION_WORKFLOW = "full"
COLLECTION_MARKEXPR = "not slow"
COLLECTION_TRANSPORT_MAX_BYTES = 64 * 1024 * 1024

_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_NONCE_RE = re.compile(r"[0-9a-f]{64}\Z")
_STABLE_FD_FIELDS = (
    "st_dev",
    "st_ino",
    "st_mode",
    "st_nlink",
    "st_uid",
    "st_gid",
    "st_rdev",
)
_STABLE_READ_FIELDS = _STABLE_FD_FIELDS + (
    "st_size",
    "st_mtime_ns",
    "st_ctime_ns",
)


class AB16CollectionProtocolError(RuntimeError):
    """The explicit AB16 collection producer or transport failed closed."""


@dataclass(frozen=True)
class AB16CollectionExpectation:
    """Committed nodeid count and digest for the one full, non-slow lane."""

    count: int
    sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.count) is not int
            or self.count <= 0
            or type(self.sha256) is not str
            or _SHA256_RE.fullmatch(self.sha256) is None
        ):
            raise AB16CollectionProtocolError("pytest collection expectation is malformed")


@dataclass(frozen=True)
class AB16ValidatedCollection:
    """Validated two-record bytes and their receipt-safe exact projection."""

    raw: bytes
    stage_raw: bytes
    terminal_raw: bytes
    stage: Mapping[str, object]
    terminal: Mapping[str, object]
    projection: Mapping[str, object]

    def stdout_bytes(self) -> bytes:
        """Render the two canonical records for capture in preflight stdout."""

        return (
            COLLECTION_STDOUT_PREFIX
            + self.stage_raw
            + COLLECTION_STDOUT_PREFIX
            + self.terminal_raw
        )


def canonical_json_line(value: object) -> bytes:
    """Return one deterministic ASCII JSON line."""

    try:
        rendered = json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise AB16CollectionProtocolError("pytest collection record is not canonical JSON data") from exc
    return (rendered + "\n").encode("ascii")


def collection_manifest_sha256(items: object) -> str:
    """Hash the ordered nodeid/path manifest in its domain."""

    canonical = canonical_json_line(items)[:-1]
    return hashlib.sha256(COLLECTION_MANIFEST_DOMAIN + canonical).hexdigest()


def collection_nodeids_sha256(items: Sequence[Mapping[str, str]]) -> str:
    """Hash the ordered nodeid list exactly as the committed expectation does."""

    raw = ("\n".join(item["nodeid"] for item in items) + "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _fd_signature(value: os.stat_result, fields: Sequence[str]) -> tuple[int, ...]:
    return tuple(int(getattr(value, field)) for field in fields)


def _require_transport_shape(value: os.stat_result) -> None:
    if (
        not stat.S_ISREG(value.st_mode)
        or value.st_nlink != 0
        or value.st_uid != os.geteuid()
        or stat.S_IMODE(value.st_mode) != 0o600
        or value.st_size < 0
        or value.st_size > COLLECTION_TRANSPORT_MAX_BYTES
    ):
        raise AB16CollectionProtocolError(
            "pytest collection transport is not one anonymous retained 0600 regular file"
        )


class AB16AnonymousTransport:
    """Owned anonymous regular file used only for the two producer records.

    Construction takes ownership of ``stream`` immediately, including failure
    paths.
    """

    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream
        self._closed = False
        try:
            descriptor = stream.fileno()
            os.fchmod(descriptor, 0o600)
            metadata = os.fstat(descriptor)
            _require_transport_shape(metadata)
            if metadata.st_size != 0:
                raise AB16CollectionProtocolError(
                    "pytest collection transport is not initially empty"
                )
            if fcntl.fcntl(descriptor, fcntl.F_GETFD) & fcntl.FD_CLOEXEC == 0:
                raise AB16CollectionProtocolError(
                    "pytest collection transport lacks FD_CLOEXEC"
                )
            self._identity = _fd_signature(metadata, _STABLE_FD_FIELDS)
        except BaseException as exc:
            self._closed = True
            try:
                stream.close()
            except BaseException as close_error:
                exc.add_note(
                    "pytest collection transport cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
            raise

    @classmethod
    def create(cls) -> AB16AnonymousTransport:
        """Create an unlinked retained transport under the fixed system temp path."""

        stream: BinaryIO | None = None
        try:
            stream = tempfile.TemporaryFile(
                mode="w+b",
                buffering=0,
                prefix=".ab16-pytest-collection-",
                dir="/tmp",
            )
            transferred = stream
            stream = None
            return cls(transferred)
        except BaseException as exc:
            if stream is not None:
                try:
                    stream.close()
                except BaseException as close_error:
                    exc.add_note(
                        "pytest collection transport cleanup failed: "
                        f"{type(close_error).__name__}: {close_error}"
                    )
            if isinstance(exc, OSError):
                raise AB16CollectionProtocolError(
                    "pytest collection transport creation failed"
                ) from exc
            raise

    @property
    def closed(self) -> bool:
        """Whether ownership has been released."""

        return self._closed

    def fileno(self) -> int:
        """Return the retained descriptor after revalidating its fixed shape."""

        metadata = self._metadata()
        _require_transport_shape(metadata)
        return self._stream.fileno()

    def _metadata(self) -> os.stat_result:
        if self._closed:
            raise AB16CollectionProtocolError("pytest collection transport is closed")
        try:
            metadata = os.fstat(self._stream.fileno())
        except OSError as exc:
            raise AB16CollectionProtocolError("pytest collection transport fstat failed") from exc
        if _fd_signature(metadata, _STABLE_FD_FIELDS) != self._identity:
            raise AB16CollectionProtocolError("pytest collection transport identity drifted")
        return metadata

    def append(self, raw: bytes) -> None:
        """Append one bounded record through the retained descriptor."""

        if type(raw) is not bytes or not raw or len(raw) > COLLECTION_TRANSPORT_MAX_BYTES:
            raise AB16CollectionProtocolError("pytest collection transport append is malformed")
        before = self._metadata()
        _require_transport_shape(before)
        if before.st_size + len(raw) > COLLECTION_TRANSPORT_MAX_BYTES:
            raise AB16CollectionProtocolError("pytest collection transport exceeds its byte limit")
        descriptor = self._stream.fileno()
        try:
            offset = os.lseek(descriptor, 0, os.SEEK_END)
            if offset != before.st_size:
                raise AB16CollectionProtocolError("pytest collection transport offset drifted")
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("short write")
                view = view[written:]
            os.fsync(descriptor)
            after = os.fstat(descriptor)
        except AB16CollectionProtocolError:
            raise
        except OSError as exc:
            raise AB16CollectionProtocolError("pytest collection transport append failed") from exc
        _require_transport_shape(after)
        if (
            _fd_signature(after, _STABLE_FD_FIELDS) != self._identity
            or after.st_size != before.st_size + len(raw)
        ):
            raise AB16CollectionProtocolError("pytest collection transport changed during append")

    def read(self) -> bytes:
        """Read the complete bounded transport through its retained descriptor."""

        before = self._metadata()
        _require_transport_shape(before)
        descriptor = self._stream.fileno()
        chunks: list[bytes] = []
        remaining = before.st_size
        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            while remaining:
                chunk = os.read(descriptor, min(1 << 20, remaining))
                if not chunk:
                    raise AB16CollectionProtocolError(
                        "pytest collection transport truncated during read"
                    )
                chunks.append(chunk)
                remaining -= len(chunk)
            if os.read(descriptor, 1):
                raise AB16CollectionProtocolError("pytest collection transport grew during read")
            after = os.fstat(descriptor)
        except AB16CollectionProtocolError:
            raise
        except OSError as exc:
            raise AB16CollectionProtocolError("pytest collection transport read failed") from exc
        _require_transport_shape(after)
        if _fd_signature(before, _STABLE_READ_FIELDS) != _fd_signature(after, _STABLE_READ_FIELDS):
            raise AB16CollectionProtocolError("pytest collection transport changed during read")
        return b"".join(chunks)

    def close(self) -> None:
        """Release the retained descriptor exactly once; repeated close is inert."""

        if self._closed:
            return
        try:
            self._stream.close()
        except OSError as exc:
            self._closed = self._stream.closed
            raise AB16CollectionProtocolError("pytest collection transport close failed") from exc
        except BaseException:
            self._closed = self._stream.closed
            raise
        self._closed = True


def _strict_pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    record: dict[str, object] = {}
    for key, value in items:
        if key in record:
            raise AB16CollectionProtocolError(
                f"pytest collection record duplicates key {key!r}"
            )
        record[key] = value
    return record


def _reject_json_number(token: str) -> object:
    raise AB16CollectionProtocolError(
        f"pytest collection record contains forbidden number {token!r}"
    )


def _strict_record(raw: bytes, label: str) -> dict[str, object]:
    if (
        type(raw) is not bytes
        or not raw.endswith(b"\n")
        or b"\n" in raw[:-1]
        or b"\r" in raw
    ):
        raise AB16CollectionProtocolError(f"{label} is not one canonical line")
    try:
        value = json.loads(
            raw[:-1].decode("ascii"),
            object_pairs_hook=_strict_pairs,
            parse_float=_reject_json_number,
            parse_constant=_reject_json_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AB16CollectionProtocolError(f"{label} is malformed") from exc
    if type(value) is not dict or canonical_json_line(value) != raw:
        raise AB16CollectionProtocolError(f"{label} is not canonical")
    return value


def _safe_repository_relative(value: str) -> bool:
    parts = value.split("/")
    return (
        bool(value)
        and not value.startswith("/")
        and "\\" not in value
        and all(ord(character) >= 32 and ord(character) != 127 for character in value)
        and all(part not in {"", ".", ".."} for part in parts)
    )


def _validated_items(value: object) -> list[dict[str, str]]:
    if type(value) is not list:
        raise AB16CollectionProtocolError("pytest collection items are not a list")
    items: list[dict[str, str]] = []
    previous: tuple[str, str] | None = None
    nodeids: set[str] = set()
    for item in value:
        if type(item) is not dict or set(item) != {"nodeid", "path"}:
            raise AB16CollectionProtocolError("pytest collection item shape drifted")
        nodeid = item["nodeid"]
        path = item["path"]
        if (
            type(nodeid) is not str
            or type(path) is not str
            or not _safe_repository_relative(path)
            or not path.startswith("src/tests/")
            or not nodeid
            or any(ord(character) < 32 or ord(character) == 127 for character in nodeid)
            or not (nodeid == path or nodeid.startswith(path + "::"))
        ):
            raise AB16CollectionProtocolError("pytest collection item is unsafe")
        key = (nodeid, path)
        if previous is not None and key <= previous:
            raise AB16CollectionProtocolError(
                "pytest collection items are not strictly sorted and unique"
            )
        if nodeid in nodeids:
            raise AB16CollectionProtocolError("pytest collection nodeid is duplicated")
        previous = key
        nodeids.add(nodeid)
        items.append({"nodeid": nodeid, "path": path})
    return items


def _validated_module_origins(value: object, label: str) -> list[dict[str, str]]:
    """Validate diagnostic shape only; this is deliberately not an import closure."""

    if type(value) is not list:
        raise AB16CollectionProtocolError(f"{label} is not a list")
    records: list[dict[str, str]] = []
    previous: tuple[str, str, str, str] | None = None
    for item in value:
        if type(item) is not dict or set(item) != {
            "kind",
            "module",
            "path",
            "resolved_path",
        }:
            raise AB16CollectionProtocolError(f"{label} record shape drifted")
        if any(
            type(item[field]) is not str
            or not item[field]
            or any(
                ord(character) < 32 or ord(character) == 127
                for character in item[field]
            )
            for field in item
        ):
            raise AB16CollectionProtocolError(f"{label} record is malformed")
        if item["kind"] not in {"file", "package_path"}:
            raise AB16CollectionProtocolError(f"{label} kind is unsupported")
        key = (
            item["module"],
            item["kind"],
            item["path"],
            item["resolved_path"],
        )
        if previous is not None and key <= previous:
            raise AB16CollectionProtocolError(
                f"{label} is not strictly sorted and unique"
            )
        previous = key
        records.append(dict(item))
    return records


def validate_collection_records(
    raw: bytes,
    *,
    expectation: AB16CollectionExpectation,
    nonce: str,
    returncode: int,
) -> AB16ValidatedCollection:
    """Independently validate the producer's exact two-record terminal state."""

    if type(raw) is not bytes or len(raw) > COLLECTION_TRANSPORT_MAX_BYTES:
        raise AB16CollectionProtocolError("pytest collection transport bytes are malformed")
    if type(nonce) is not str or _NONCE_RE.fullmatch(nonce) is None:
        raise AB16CollectionProtocolError("pytest collection nonce is malformed")
    if type(returncode) is not int:
        raise AB16CollectionProtocolError("pytest return code is malformed")
    records = raw.splitlines(keepends=True)
    if len(records) != 2 or b"".join(records) != raw:
        raise AB16CollectionProtocolError(
            "pytest collection transport must contain exactly two records"
        )
    stage_raw, terminal_raw = records
    stage = _strict_record(stage_raw, "pytest collection stage")
    terminal = _strict_record(terminal_raw, "pytest collection terminal")
    if set(stage) != {
        "collection_count",
        "collection_sha256",
        "expected_count",
        "expected_sha256",
        "items",
        "manifest_sha256",
        "markexpr",
        "module_origins",
        "nonce",
        "schema_version",
        "workflow",
    } or set(terminal) != {
        "exitstatus",
        "module_origins",
        "nonce",
        "schema_version",
        "stage_sha256",
    }:
        raise AB16CollectionProtocolError("pytest collection record key set drifted")
    items = _validated_items(stage["items"])
    stage_origins = _validated_module_origins(
        stage["module_origins"],
        "pytest collection-stage module origins",
    )
    terminal_origins = _validated_module_origins(
        terminal["module_origins"],
        "pytest terminal module origins",
    )
    observed_sha256 = collection_nodeids_sha256(items)
    manifest_sha256 = collection_manifest_sha256(items)
    if (
        type(stage["collection_count"]) is not int
        or stage["collection_count"] != len(items)
        or type(stage["collection_sha256"]) is not str
        or stage["collection_sha256"] != observed_sha256
        or type(stage["expected_count"]) is not int
        or stage["expected_count"] != expectation.count
        or len(items) != expectation.count
        or type(stage["expected_sha256"]) is not str
        or stage["expected_sha256"] != expectation.sha256
        or observed_sha256 != expectation.sha256
        or type(stage["manifest_sha256"]) is not str
        or stage["manifest_sha256"] != manifest_sha256
        or stage["schema_version"] != COLLECTION_STAGE_SCHEMA
        or stage["workflow"] != COLLECTION_WORKFLOW
        or stage["markexpr"] != COLLECTION_MARKEXPR
        or stage["nonce"] != nonce
        or terminal["schema_version"] != COLLECTION_TERMINAL_SCHEMA
        or terminal["nonce"] != nonce
        or type(terminal["exitstatus"]) is not int
        or terminal["exitstatus"] != returncode
        or returncode != 0
        or type(terminal["stage_sha256"]) is not str
        or terminal["stage_sha256"] != hashlib.sha256(stage_raw).hexdigest()
    ):
        raise AB16CollectionProtocolError(
            "pytest collection records do not close the explicit expected PASS"
        )
    projection: dict[str, object] = {
        "collection_count": len(items),
        "collection_sha256": observed_sha256,
        "manifest_sha256": manifest_sha256,
        "markexpr": COLLECTION_MARKEXPR,
        "schema_version": COLLECTION_BINDING_SCHEMA,
        "stage_module_origin_count": len(stage_origins),
        "stage_sha256": hashlib.sha256(stage_raw).hexdigest(),
        "terminal_module_origin_count": len(terminal_origins),
        "terminal_sha256": hashlib.sha256(terminal_raw).hexdigest(),
        "workflow": COLLECTION_WORKFLOW,
    }
    return AB16ValidatedCollection(
        raw=raw,
        stage_raw=stage_raw,
        terminal_raw=terminal_raw,
        stage=stage,
        terminal=terminal,
        projection=projection,
    )


class AB16CollectionSession:
    """One explicit producer session shared with one pytest plugin instance."""

    def __init__(
        self,
        *,
        expectation: AB16CollectionExpectation,
        transport: AB16AnonymousTransport,
        nonce: str,
    ) -> None:
        if type(expectation) is not AB16CollectionExpectation:
            error = AB16CollectionProtocolError(
                "pytest collection expectation has the wrong type"
            )
            try:
                transport.close()
            except BaseException as close_error:
                error.add_note(
                    "pytest collection session cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
            raise error
        if type(nonce) is not str or _NONCE_RE.fullmatch(nonce) is None:
            error = AB16CollectionProtocolError("pytest collection nonce is malformed")
            try:
                transport.close()
            except BaseException as close_error:
                error.add_note(
                    "pytest collection session cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
            raise error
        self.expectation = expectation
        self.nonce = nonce
        self.workflow = COLLECTION_WORKFLOW
        self.markexpr = COLLECTION_MARKEXPR
        self._transport = transport
        self._stage_raw: bytes | None = None
        self._terminal_raw: bytes | None = None

    @classmethod
    def create(
        cls,
        *,
        expected_count: int,
        expected_sha256: str,
        nonce: str | None = None,
    ) -> AB16CollectionSession:
        """Create a fresh explicit session and its anonymous transport."""

        expectation = AB16CollectionExpectation(expected_count, expected_sha256)
        selected_nonce = secrets.token_hex(32) if nonce is None else nonce
        transport: AB16AnonymousTransport | None = None
        try:
            transport = AB16AnonymousTransport.create()
            transferred = transport
            transport = None
            return cls(
                expectation=expectation,
                transport=transferred,
                nonce=selected_nonce,
            )
        except BaseException as exc:
            if transport is not None:
                try:
                    transport.close()
                except BaseException as close_error:
                    exc.add_note(
                        "pytest collection session cleanup failed: "
                        f"{type(close_error).__name__}: {close_error}"
                    )
            raise

    @property
    def closed(self) -> bool:
        """Whether the session transport has been released."""

        return self._transport.closed

    def publish_stage(
        self,
        *,
        items: Sequence[Mapping[str, str]],
        module_origins: Sequence[Mapping[str, str]],
        workflow: str,
        markexpr: str,
    ) -> None:
        """Publish the collection-finish record exactly once."""

        if self._stage_raw is not None or self._terminal_raw is not None:
            raise AB16CollectionProtocolError("pytest collection stage was already published")
        normalized_items = _validated_items(list(items))
        normalized_origins = _validated_module_origins(
            list(module_origins),
            "pytest collection-stage module origins",
        )
        observed_sha256 = collection_nodeids_sha256(normalized_items)
        if (
            workflow != COLLECTION_WORKFLOW
            or markexpr != COLLECTION_MARKEXPR
            or len(normalized_items) != self.expectation.count
            or observed_sha256 != self.expectation.sha256
        ):
            raise AB16CollectionProtocolError(
                "pytest collection stage differs from the explicit expectation"
            )
        stage = {
            "collection_count": len(normalized_items),
            "collection_sha256": observed_sha256,
            "expected_count": self.expectation.count,
            "expected_sha256": self.expectation.sha256,
            "items": normalized_items,
            "manifest_sha256": collection_manifest_sha256(normalized_items),
            "markexpr": markexpr,
            "module_origins": normalized_origins,
            "nonce": self.nonce,
            "schema_version": COLLECTION_STAGE_SCHEMA,
            "workflow": workflow,
        }
        raw = canonical_json_line(stage)
        self._transport.append(raw)
        self._stage_raw = raw

    def publish_terminal(
        self,
        *,
        exitstatus: int,
        module_origins: Sequence[Mapping[str, str]],
    ) -> None:
        """Publish the session-finish record exactly once."""

        if self._stage_raw is None:
            raise AB16CollectionProtocolError(
                "pytest collection terminal cannot precede its stage"
            )
        if self._terminal_raw is not None:
            raise AB16CollectionProtocolError("pytest collection terminal was already published")
        if type(exitstatus) is not int:
            raise AB16CollectionProtocolError("pytest collection exitstatus is malformed")
        normalized_origins = _validated_module_origins(
            list(module_origins),
            "pytest terminal module origins",
        )
        terminal = {
            "exitstatus": exitstatus,
            "module_origins": normalized_origins,
            "nonce": self.nonce,
            "schema_version": COLLECTION_TERMINAL_SCHEMA,
            "stage_sha256": hashlib.sha256(self._stage_raw).hexdigest(),
        }
        raw = canonical_json_line(terminal)
        self._transport.append(raw)
        self._terminal_raw = raw

    def validate(self, *, returncode: int) -> AB16ValidatedCollection:
        """Read the retained transport and validate the exact terminal PASS."""

        raw = self._transport.read()
        return validate_collection_records(
            raw,
            expectation=self.expectation,
            nonce=self.nonce,
            returncode=returncode,
        )

    def close(self) -> None:
        """Release the anonymous transport."""

        self._transport.close()

    def __enter__(self) -> AB16CollectionSession:
        return self

    def __exit__(
        self,
        _exc_type: object,
        exc: BaseException | None,
        _traceback: object,
    ) -> None:
        try:
            self.close()
        except BaseException as close_error:
            if exc is None:
                raise
            exc.add_note(
                "pytest collection session cleanup failed: "
                f"{type(close_error).__name__}: {close_error}"
            )
