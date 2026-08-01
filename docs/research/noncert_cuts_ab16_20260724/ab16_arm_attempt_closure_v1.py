#!/usr/bin/env python3
"""Fail-closed closure and detached replay for one prospective AB16 arm attempt.

This module does not discover authority from the filesystem.  It accepts the
broker's monotonic ``expected_path_types`` projection, restricts that projection
to one exact arm-attempt prefix, and requires a descriptor-relative walk to be
identical.  The fixed terminal manifest excludes itself.  An outside replay
then re-enumerates the closed subtree and binds the exact authority/lifecycle
identities supplied by the formal supervisor.

Both publications use an already-authorized budget backend.  This module owns
no root/staging writable descriptor and grants no campaign, solver, cut,
witness, production, certified, or bound-changing authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Final, NoReturn, Protocol, cast


MANIFEST_SCHEMA: Final = (
    "noncert-cuts-ab16-organic-attempt-artifact-manifest-v1"
)
REPLAY_SCHEMA: Final = "noncert-cuts-ab16-organic-attempt-root-replay-v1"
ROOT_INVENTORY_SCHEMA: Final = "noncert-cuts-ab16-formal-root-inventory-v1"
ARM_BUDGET_TERMINAL_SCHEMA: Final = (
    "noncert-cuts-ab16-arm-budget-terminal-v1"
)
ARM_BUDGET_RECONCILE_SCHEMA: Final = (
    "noncert-cuts-ab16-arm-budget-reconcile-v1"
)
BROKER_JOURNAL_SCHEMA: Final = (
    "noncert-cuts-ab16-budget-broker-journal-event-v1"
)
PRIOR_RESPONSE_ACCEPTED_ACTION: Final = "PRIOR_RESPONSE_ACCEPTED"
PENDING_TERMINAL_STATUS: Final = "SEAL_DURABLE_PENDING_ACK"
PENDING_ALLOCATION_STATE: Final = "SEALED_PENDING_ACK"
AUTHORITY_SCOPE: Final = "AB16_RESEARCH_ONLY"
TERMINAL_MANIFEST_NAME: Final = "attempt-artifact-manifest.json"
ARM_BUDGET_TERMINAL_DIRECTORY: Final = "budget/arm-terminals"
ARM_REPLAY_DIRECTORY: Final = "replays/arm-attempt-roots"
STAGING_PREFIX: Final = ".ab16-budget-stage-"
MANIFEST_BUDGET_LABEL: Final = "AB16 organic attempt artifact manifest"
REPLAY_BUDGET_LABEL: Final = "AB16 organic attempt root replay"
CONSUMPTION_BUDGET_LABEL: Final = "organic arm consumption"
MANIFEST_ARTIFACT_CLASS: Final = "publication"
REPLAY_ARTIFACT_CLASS: Final = "closeout"
CONSUMPTION_ARTIFACT_CLASS: Final = "closeout"
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

FALSE_AUTHORIZATIONS: Final = {
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

BINDING_KEYS: Final = frozenset(
    {
        "arm_allocation_identity",
        "arm_arithmetic_replay_identity",
        "arm_credibility_identity",
        "arm_result_identity",
        "arm_selection_identity",
        "detached_resource_terminal_identity",
        "lifecycle_cleanup_identity",
        "lifecycle_inner_identity",
        "lifecycle_preterminal_identity",
        "lifecycle_release_identity",
        "lifecycle_terminal_identity",
    }
)

_IDENTITY_KEYS: Final = frozenset({"path", "sha256", "size_bytes"})
_SHA256_RE: Final = re.compile(r"[0-9a-f]{64}\Z")
_SAFE_TOKEN_RE: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_DIRECTORY_FLAGS: Final = (
    os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
)
_READ_FLAGS: Final = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
_READ_CHUNK_BYTES: Final = 1024 * 1024


class ArmAttemptClosureError(RuntimeError):
    """One inventory, topology, publication, or replay invariant failed."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


class BudgetPublicationBackend(Protocol):
    """The already-authorized, no-overwrite budget publication surface."""

    def maximum_bytes(self, label: str, *, artifact_class: str) -> int: ...

    def publish_bytes(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        artifact_class: str,
        label: str,
    ) -> Mapping[str, object]: ...


class ArmManifestSealBackend(Protocol):
    """One indivisible manifest-publication and arm-seal transition.

    The implementation is the package-pinned persistent broker.  Once this
    method is entered for an allocated arm, any publication, fsync, response,
    or acknowledgement uncertainty permanently consumes that arm as
    ``SEALED_INCOMPLETE``.  A successful return means that both the terminal
    manifest and its outside-subtree budget terminal are durable and that all
    subsequent arm writes are rejected before the acknowledgement is sent.
    """

    def maximum_bytes(self, label: str, *, artifact_class: str) -> int: ...

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
    ) -> Mapping[str, object]: ...


class PostSealReplayBackend(Protocol):
    """The sole retained extent for the accepted arm's outside replay."""

    def maximum_bytes(self, label: str, *, artifact_class: str) -> int: ...

    def publish_accepted_arm_replay(
        self,
        path: Path,
        raw: bytes,
        *,
        maximum_bytes: int,
        label: str,
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class _Snapshot:
    entries: tuple[dict[str, object], ...]
    terminal_raw: bytes | None
    root_signature: tuple[int, ...]

    @property
    def path_types(self) -> dict[str, str]:
        return {
            cast(str, entry["path"]): cast(str, entry["type"])
            for entry in self.entries
        }


def _fail(code: str, detail: str) -> NoReturn:
    raise ArmAttemptClosureError(code, detail)


def _canonical_json(value: object) -> bytes:
    _require_json(value, "$")
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


def _require_json(value: object, label: str) -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is list:
        for index, member in enumerate(cast(list[object], value)):
            _require_json(member, f"{label}[{index}]")
        return
    if type(value) is dict:
        for key, member in cast(dict[object, object], value).items():
            if type(key) is not str:
                _fail("JSON_DOMAIN_INVALID", f"{label}: non-string key")
            _require_json(member, f"{label}.{key}")
        return
    _fail("JSON_DOMAIN_INVALID", f"{label}: {type(value).__name__}")


def _strict_json(raw: bytes, label: str) -> dict[str, object]:
    def unique(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                _fail("JSON_INVALID", f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject(token: str) -> NoReturn:
        _fail("JSON_INVALID", f"{label}: non-integer token {token!r}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        _fail("JSON_INVALID", f"{label}: {exc}")
    if type(value) is not dict or _canonical_json(value) != raw:
        _fail("JSON_INVALID", f"{label}: bytes are not canonical")
    return cast(dict[str, object], value)


def _relative_parts(value: object, label: str) -> tuple[str, ...]:
    if type(value) is not str or not value or "\x00" in value or "\\" in value:
        _fail("PATH_INVALID", f"{label}: not one portable relative path")
    path = PurePosixPath(cast(str, value))
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        _fail("PATH_INVALID", f"{label}: {value!r}")
    return tuple(path.parts)


def _identity(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict or set(cast(dict[str, object], value)) != _IDENTITY_KEYS:
        _fail("IDENTITY_INVALID", f"{label}: key set")
    record = cast(dict[str, object], value)
    if (
        type(record["path"]) is not str
        or not Path(cast(str, record["path"])).is_absolute()
        or type(record["sha256"]) is not str
        or _SHA256_RE.fullmatch(cast(str, record["sha256"])) is None
        or type(record["size_bytes"]) is not int
        or cast(int, record["size_bytes"]) < 0
    ):
        _fail("IDENTITY_INVALID", label)
    return dict(record)


def _content_identity(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail("IDENTITY_INVALID", f"{label}: not an object")
    record = cast(dict[str, object], value)
    if set(record) != {"sha256", "size_bytes"}:
        _fail("IDENTITY_INVALID", f"{label}: key set")
    digest = record["sha256"]
    size = record["size_bytes"]
    if (
        type(digest) is not str
        or _SHA256_RE.fullmatch(cast(str, digest)) is None
        or type(size) is not int
        or cast(int, size) <= 0
    ):
        _fail("IDENTITY_INVALID", f"{label}: value domain")
    return dict(record)


def _bindings(value: object) -> dict[str, dict[str, object]]:
    if type(value) is not dict or set(cast(dict[str, object], value)) != BINDING_KEYS:
        _fail("BINDINGS_INVALID", "authority/lifecycle identity set drifted")
    return {
        key: (
            _content_identity(member, key)
            if key == "arm_allocation_identity"
            else _identity(member, key)
        )
        for key, member in sorted(cast(dict[str, object], value).items())
    }


def _signature(item: os.stat_result) -> tuple[int, ...]:
    return (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_uid,
        item.st_gid,
        item.st_size,
        item.st_blocks,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )


def _root_signature(item: os.stat_result) -> tuple[int, ...]:
    return (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_uid,
        item.st_gid,
        item.st_mtime_ns,
        item.st_ctime_ns,
    )


def _directory_identity(item: os.stat_result) -> tuple[int, ...]:
    return (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_uid,
        item.st_gid,
    )


def _close_preserving(descriptor: int, primary: BaseException | None, label: str) -> None:
    try:
        os.close(descriptor)
    except BaseException as close_error:
        if primary is None:
            raise
        primary.add_note(
            f"{label} close failed: {type(close_error).__name__}: {close_error}"
        )


def _open_absolute_directory(path: Path) -> int:
    if not path.is_absolute():
        _fail("ROOT_PATH_INVALID", f"{path}: not absolute")
    descriptors = [os.open("/", _DIRECTORY_FLAGS)]
    primary: BaseException | None = None
    try:
        for part in path.parts[1:]:
            if part in {"", ".", ".."}:
                _fail("ROOT_PATH_INVALID", str(path))
            descriptors.append(
                os.open(part, _DIRECTORY_FLAGS, dir_fd=descriptors[-1])
            )
    except OSError as exc:
        primary = ArmAttemptClosureError("ROOT_OPEN_FAILED", f"{path}: {exc}")
    except BaseException as exc:
        primary = exc
    if primary is None:
        result = descriptors.pop()
    else:
        result = -1
    for descriptor in reversed(descriptors):
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if primary is None:
                primary = close_error
            else:
                primary.add_note(
                    "directory-chain cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
    if primary is not None:
        raise primary
    return result


def _read_regular(
    parent_fd: int,
    name: str,
    before: os.stat_result,
    relative: str,
    *,
    capture: bool,
) -> tuple[str, bytes | None]:
    descriptor = -1
    primary: BaseException | None = None
    try:
        descriptor = os.open(name, _READ_FLAGS, dir_fd=parent_fd)
        opened = os.fstat(descriptor)
        if _signature(opened) != _signature(before):
            _fail("ROOT_CHANGED", relative)
        digest = hashlib.sha256()
        captured = bytearray() if capture else None
        offset = 0
        while offset < before.st_size:
            block = os.pread(
                descriptor,
                min(_READ_CHUNK_BYTES, before.st_size - offset),
                offset,
            )
            if not block:
                _fail("ROOT_CHANGED", f"{relative}: short read")
            digest.update(block)
            if captured is not None:
                captured.extend(block)
            offset += len(block)
        if os.pread(descriptor, 1, before.st_size):
            _fail("ROOT_CHANGED", f"{relative}: grew during read")
        if _signature(os.fstat(descriptor)) != _signature(before):
            _fail("ROOT_CHANGED", relative)
        result = (digest.hexdigest(), None if captured is None else bytes(captured))
    except BaseException as exc:
        primary = exc
        result = None
    if descriptor >= 0:
        _close_preserving(descriptor, primary, f"{relative} descriptor")
    if primary is not None:
        raise primary
    assert result is not None
    return result


def _snapshot(root: Path, *, capture_terminal: bool) -> _Snapshot:
    root_fd = _open_absolute_directory(root)
    retained: list[
        tuple[int, str, tuple[int, ...], tuple[str, ...]]
    ] = []
    entries: list[dict[str, object]] = []
    file_inodes: set[tuple[int, int]] = set()
    terminal_raw: bytes | None = None
    primary: BaseException | None = None
    final_error: BaseException | None = None
    root_stat: os.stat_result | None = None

    def record_error(error: BaseException, detail: str) -> None:
        nonlocal final_error
        if primary is not None:
            primary.add_note(detail)
        elif final_error is None:
            final_error = error
        else:
            final_error.add_note(detail)

    def walk(descriptor: int, prefix: tuple[str, ...]) -> None:
        nonlocal terminal_raw
        try:
            names = tuple(sorted(os.listdir(descriptor), key=os.fsencode))
            current = os.fstat(descriptor)
        except OSError as exc:
            _fail("ROOT_ENUMERATION_FAILED", f"{root.joinpath(*prefix)}: {exc}")
        retained.append(
            (
                descriptor,
                "/".join(prefix),
                _signature(current),
                names,
            )
        )
        for name in names:
            if name in {"", ".", ".."} or "/" in name or "\x00" in name:
                _fail("ROOT_PATH_INVALID", repr(name))
            relative = "/".join((*prefix, name))
            if name.startswith(STAGING_PREFIX):
                _fail("STAGING_PRESENT", relative)
            try:
                item = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            except OSError as exc:
                _fail("ROOT_ENUMERATION_FAILED", f"{relative}: {exc}")
            if stat.S_ISLNK(item.st_mode):
                _fail("SYMLINK_REJECTED", relative)
            if stat.S_ISDIR(item.st_mode):
                child = -1
                try:
                    child = os.open(name, _DIRECTORY_FLAGS, dir_fd=descriptor)
                    opened = os.fstat(child)
                    if (
                        opened.st_dev != item.st_dev
                        or opened.st_ino != item.st_ino
                        or not stat.S_ISDIR(opened.st_mode)
                    ):
                        _fail("ROOT_CHANGED", relative)
                    entries.append(
                        {
                            "mode_octal": f"{stat.S_IMODE(opened.st_mode):04o}",
                            "path": relative,
                            "type": "directory",
                        }
                    )
                    walk(child, (*prefix, name))
                    child = -1  # retained list owns it
                finally:
                    if child >= 0:
                        os.close(child)
                continue
            if not stat.S_ISREG(item.st_mode):
                _fail("SPECIAL_NODE_REJECTED", relative)
            inode = (item.st_dev, item.st_ino)
            if item.st_nlink != 1 or inode in file_inodes:
                _fail("HARDLINK_REJECTED", relative)
            file_inodes.add(inode)
            digest, captured = _read_regular(
                descriptor,
                name,
                item,
                relative,
                capture=capture_terminal and relative == TERMINAL_MANIFEST_NAME,
            )
            if captured is not None:
                terminal_raw = captured
            entries.append(
                {
                    "mode_octal": f"{stat.S_IMODE(item.st_mode):04o}",
                    "path": relative,
                    "sha256": digest,
                    "size_bytes": item.st_size,
                    "type": "regular",
                }
            )

    try:
        root_stat = os.fstat(root_fd)
        if not stat.S_ISDIR(root_stat.st_mode):
            _fail("ROOT_INVALID", str(root))
        walk(root_fd, ())
        root_fd = -1  # retained list owns it
    except BaseException as exc:
        primary = exc

    for descriptor, relative, initial_signature, initial_names in reversed(retained):
        display = str(root if not relative else root / relative)
        try:
            if (
                _signature(os.fstat(descriptor)) != initial_signature
                or tuple(sorted(os.listdir(descriptor), key=os.fsencode))
                != initial_names
            ):
                error = ArmAttemptClosureError("ROOT_CHANGED", display)
                record_error(error, str(error))
        except BaseException as exc:
            record_error(exc, f"final directory validation failed for {display}: {exc}")
        try:
            os.close(descriptor)
        except BaseException as exc:
            record_error(exc, f"directory close failed for {display}: {exc}")
    if root_fd >= 0:
        _close_preserving(root_fd, primary, "attempt root")

    if root_stat is not None:
        try:
            rejoined = _open_absolute_directory(root)
            try:
                if _root_signature(os.fstat(rejoined)) != _root_signature(root_stat):
                    _fail("ROOT_CHANGED", f"{root}: final absolute join")
            finally:
                os.close(rejoined)
        except BaseException as exc:
            record_error(exc, f"final absolute join failed for {root}: {exc}")

    if primary is not None:
        raise primary
    if final_error is not None:
        raise final_error
    assert root_stat is not None
    return _Snapshot(
        entries=tuple(sorted(entries, key=lambda entry: cast(str, entry["path"]))),
        terminal_raw=terminal_raw,
        root_signature=_root_signature(root_stat),
    )


def _inventory(
    value: object,
    *,
    attempt_prefix: str,
    terminal_present: bool,
) -> tuple[
    tuple[dict[str, str], ...],
    tuple[dict[str, str], ...],
    dict[str, str],
    str,
]:
    if type(value) is not list:
        _fail("INVENTORY_INVALID", "expected_path_types is not one array")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, member in enumerate(cast(list[object], value)):
        if type(member) is not dict or set(cast(dict[str, object], member)) != {
            "path",
            "type",
        }:
            _fail("INVENTORY_INVALID", f"entry {index}: key set")
        item = cast(dict[str, object], member)
        parts = _relative_parts(item["path"], f"inventory entry {index}")
        path = "/".join(parts)
        node_type = item["type"]
        if node_type not in {"directory", "regular"} or path in seen:
            _fail("INVENTORY_INVALID", f"entry {index}: type or duplicate")
        seen.add(path)
        rows.append({"path": path, "type": cast(str, node_type)})
    if rows != sorted(rows, key=lambda item: (item["path"], item["type"])):
        _fail("INVENTORY_INVALID", "entries are not canonical sorted")

    prefix_parts = _relative_parts(attempt_prefix, "attempt prefix")
    prefix = "/".join(prefix_parts)
    prefix_row = {"path": prefix, "type": "directory"}
    if prefix_row not in rows:
        _fail("INVENTORY_PREFIX_MISSING", prefix)
    selected = [
        row
        for row in rows
        if row["path"] == prefix or row["path"].startswith(f"{prefix}/")
    ]
    relative_types: dict[str, str] = {}
    for row in selected:
        if row["path"] == prefix:
            continue
        relative = row["path"][len(prefix) + 1 :]
        parts = _relative_parts(relative, "arm inventory descendant")
        if any(part.startswith(STAGING_PREFIX) for part in parts):
            _fail("STAGING_PRESENT", relative)
        relative_types[relative] = row["type"]
    terminal_type = relative_types.get(TERMINAL_MANIFEST_NAME)
    if terminal_present and terminal_type != "regular":
        _fail("INVENTORY_TERMINAL_MISSING", TERMINAL_MANIFEST_NAME)
    if not terminal_present and terminal_type is not None:
        _fail("INVENTORY_TERMINAL_PREEXISTS", TERMINAL_MANIFEST_NAME)
    for relative, node_type in relative_types.items():
        parts = PurePosixPath(relative).parts
        for end in range(1, len(parts)):
            parent = "/".join(parts[:end])
            if relative_types.get(parent) != "directory":
                _fail(
                    "INVENTORY_PARENT_MISSING",
                    f"{relative}: {parent}",
                )
        if node_type == "directory" and relative == TERMINAL_MANIFEST_NAME:
            _fail("INVENTORY_INVALID", "terminal is a directory")
    selected_tuple = tuple(selected)
    digest = hashlib.sha256(_canonical_json(list(selected_tuple))).hexdigest()
    return tuple(rows), selected_tuple, relative_types, digest


def _inventory_digest(rows: Sequence[Mapping[str, object]]) -> str:
    return hashlib.sha256(
        _canonical_json([dict(row) for row in rows])
    ).hexdigest()


def _add_inventory_regular(
    rows: Sequence[Mapping[str, str]],
    path: str,
) -> tuple[dict[str, str], ...]:
    parts = _relative_parts(path, "inventory publication target")
    canonical_path = "/".join(parts)
    if any(row["path"] == canonical_path for row in rows):
        _fail("INVENTORY_TARGET_PREEXISTS", canonical_path)
    parents = {
        row["path"]
        for row in rows
        if row["type"] == "directory"
    }
    for end in range(1, len(parts)):
        parent = "/".join(parts[:end])
        if parent not in parents:
            _fail(
                "INVENTORY_PARENT_MISSING",
                f"{canonical_path}: {parent}",
            )
    return tuple(
        sorted(
            (
                *({"path": row["path"], "type": row["type"]} for row in rows),
                {"path": canonical_path, "type": "regular"},
            ),
            key=lambda row: (row["path"], row["type"]),
        )
    )


def _publication_identity(path: Path, raw: bytes) -> dict[str, object]:
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _publish(
    backend: BudgetPublicationBackend,
    *,
    path: Path,
    raw: bytes,
    label: str,
    artifact_class: str,
) -> dict[str, object]:
    maximum = backend.maximum_bytes(label, artifact_class=artifact_class)
    if type(maximum) is not int or maximum <= 0 or len(raw) > maximum:
        _fail("BUDGET_INVALID", f"{label}: fixed maximum")
    try:
        receipt = dict(
            backend.publish_bytes(
                path,
                raw,
                maximum_bytes=maximum,
                artifact_class=artifact_class,
                label=label,
            )
        )
    except BaseException as exc:
        raise ArmAttemptClosureError(
            "PUBLICATION_FAILED_OR_UNCERTAIN",
            f"{label}: {type(exc).__name__}: {exc}",
        ) from exc
    expected = _publication_identity(path, raw)
    if (
        receipt.get("path") != expected["path"]
        or receipt.get("sha256") != expected["sha256"]
        or receipt.get("size_bytes") != expected["size_bytes"]
        or receipt.get("maximum_bytes") != maximum
    ):
        _fail("PUBLICATION_RECEIPT_DRIFT", label)
    return receipt


def _require_snapshot_types(
    snapshot: _Snapshot,
    expected: Mapping[str, str],
    label: str,
) -> None:
    if snapshot.path_types != dict(expected):
        missing = sorted(set(expected) - set(snapshot.path_types))
        extra = sorted(set(snapshot.path_types) - set(expected))
        mismatched = sorted(
            path
            for path in set(expected) & set(snapshot.path_types)
            if expected[path] != snapshot.path_types[path]
        )
        _fail(
            "ROOT_CLOSURE_MISMATCH",
            f"{label}: missing={missing!r}; extra={extra!r}; "
            f"type_mismatch={mismatched!r}",
        )


def _manifest_record(
    *,
    arm_slot: str,
    attempt_prefix: str,
    final_inventory_digest: str,
    entries: Sequence[Mapping[str, object]],
    bindings: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    return {
        "arm_attempt_prefix": attempt_prefix,
        "arm_slot": arm_slot,
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "bindings": {
            key: dict(value) for key, value in sorted(bindings.items())
        },
        "entries": [dict(entry) for entry in entries],
        "inventory": {
            "schema_version": ROOT_INVENTORY_SCHEMA,
            "arm_expected_path_types_sha256": final_inventory_digest,
        },
        "schema_version": MANIFEST_SCHEMA,
        "status": "CLOSED_NO_GLOBAL_AUTHORITY",
        "terminal_self_exclusion": {
            "manifest_contains_own_sha256": False,
            "manifest_contains_own_size": False,
            "manifest_path": TERMINAL_MANIFEST_NAME,
            "manifest_path_excluded_from_entries": True,
        },
    }


def _exact_nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or cast(int, value) < 0:
        _fail("ARM_BUDGET_TERMINAL_INVALID", f"{label}: nonnegative integer")
    return cast(int, value)


def _category_map(value: object, label: str) -> dict[str, int]:
    if type(value) is not dict or not value:
        _fail("ARM_BUDGET_TERMINAL_INVALID", f"{label}: category map")
    result: dict[str, int] = {}
    for key, member in cast(dict[object, object], value).items():
        if type(key) is not str or key not in ARTIFACT_CLASSES:
            _fail(
                "ARM_BUDGET_TERMINAL_INVALID",
                f"{label}: artifact class {key!r}",
            )
        result[cast(str, key)] = _exact_nonnegative_int(
            member,
            f"{label}.{key}",
        )
    return dict(sorted(result.items()))


def _arm_budget_reconcile(
    value: object,
    *,
    arm_slot: str,
) -> dict[str, object]:
    if type(value) is not dict or set(cast(dict[str, object], value)) != {
        "arm_slot",
        "category_limits",
        "category_remaining",
        "reserved_bytes",
        "schema_version",
        "spent_or_stranded_bytes",
        "unspent_reserved_bytes",
    }:
        _fail("ARM_BUDGET_TERMINAL_INVALID", "budget reconcile key set")
    record = cast(dict[str, object], value)
    limits = _category_map(record["category_limits"], "category_limits")
    remaining = _category_map(
        record["category_remaining"],
        "category_remaining",
    )
    if (
        record["schema_version"] != ARM_BUDGET_RECONCILE_SCHEMA
        or record["arm_slot"] != arm_slot
        or set(limits) != set(remaining)
        or any(remaining[key] > limits[key] for key in limits)
    ):
        _fail("ARM_BUDGET_TERMINAL_INVALID", "budget reconcile boundary")
    reserved = _exact_nonnegative_int(
        record["reserved_bytes"],
        "reserved_bytes",
    )
    spent = _exact_nonnegative_int(
        record["spent_or_stranded_bytes"],
        "spent_or_stranded_bytes",
    )
    unspent = _exact_nonnegative_int(
        record["unspent_reserved_bytes"],
        "unspent_reserved_bytes",
    )
    if (
        reserved != sum(limits.values())
        or unspent != sum(remaining.values())
        or spent != reserved - unspent
    ):
        _fail("ARM_BUDGET_TERMINAL_INVALID", "budget reconcile arithmetic")
    return {
        "arm_slot": arm_slot,
        "category_limits": limits,
        "category_remaining": remaining,
        "reserved_bytes": reserved,
        "schema_version": ARM_BUDGET_RECONCILE_SCHEMA,
        "spent_or_stranded_bytes": spent,
        "unspent_reserved_bytes": unspent,
    }


def _journal_sequence_snapshot(value: object) -> dict[str, int]:
    if type(value) is not dict or set(cast(dict[str, object], value)) != {
        "next_event_sequence",
        "sealing_intent_event_sequence",
    }:
        _fail("ARM_BUDGET_TERMINAL_INVALID", "journal snapshot key set")
    record = cast(dict[str, object], value)
    intent = _exact_nonnegative_int(
        record["sealing_intent_event_sequence"],
        "sealing_intent_event_sequence",
    )
    next_sequence = _exact_nonnegative_int(
        record["next_event_sequence"],
        "next_event_sequence",
    )
    if next_sequence != intent + 1:
        _fail("ARM_BUDGET_TERMINAL_INVALID", "journal snapshot is not adjacent")
    return {
        "next_event_sequence": next_sequence,
        "sealing_intent_event_sequence": intent,
    }


def _response_authentication(value: object) -> dict[str, object]:
    if type(value) is not dict or set(cast(dict[str, object], value)) != {
        "nonce",
        "response_sequence",
        "response_sha256",
    }:
        _fail("ARM_SEAL_ACK_INVALID", "response authentication key set")
    record = cast(dict[str, object], value)
    if (
        type(record["nonce"]) is not str
        or not cast(str, record["nonce"])
        or type(record["response_sha256"]) is not str
        or _SHA256_RE.fullmatch(cast(str, record["response_sha256"])) is None
        or type(record["response_sequence"]) is not int
        or cast(int, record["response_sequence"]) <= 0
    ):
        _fail("ARM_SEAL_ACK_INVALID", "response authentication boundary")
    return dict(record)


def _expected_manifest_debit(
    *,
    attempt_prefix: str,
    maximum_bytes: int,
) -> dict[str, object]:
    return {
        "artifact_class": MANIFEST_ARTIFACT_CLASS,
        "maximum_bytes": maximum_bytes,
        "path": f"{attempt_prefix}/{TERMINAL_MANIFEST_NAME}",
    }


def _expected_arm_budget_terminal(
    *,
    arm_slot: str,
    attempt_prefix: str,
    allocation_identity: Mapping[str, object],
    manifest_identity: Mapping[str, object],
    arm_expected_path_types: Sequence[Mapping[str, object]],
    arm_expected_path_types_digest: str,
    manifest_allocation_debit: Mapping[str, object],
    arm_budget_reconcile: Mapping[str, object],
    sealing_intent_identity: Mapping[str, object],
    global_journal_sequence_snapshot: Mapping[str, object],
    terminal_relative_path: str,
    replay_maximum_bytes: int,
    consumption_maximum_bytes: int,
) -> dict[str, object]:
    return {
        "allocation_state": PENDING_ALLOCATION_STATE,
        "arm_allocation_identity": dict(allocation_identity),
        "arm_attempt_prefix": attempt_prefix,
        "arm_budget_reconcile": dict(arm_budget_reconcile),
        "arm_expected_path_types": [
            dict(row) for row in arm_expected_path_types
        ],
        "arm_expected_path_types_sha256": arm_expected_path_types_digest,
        "arm_slot": arm_slot,
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "global_journal_sequence_snapshot": dict(
            global_journal_sequence_snapshot
        ),
        "manifest_identity": dict(manifest_identity),
        "manifest_allocation_debit": dict(manifest_allocation_debit),
        "post_seal_reservations": {
            "consumption": {
                "artifact_class": CONSUMPTION_ARTIFACT_CLASS,
                "maximum_bytes": consumption_maximum_bytes,
                "path": (
                    f"prospective/consumptions/{arm_slot}.json"
                ),
            },
            "replay": {
                "artifact_class": REPLAY_ARTIFACT_CLASS,
                "maximum_bytes": replay_maximum_bytes,
                "path": f"{ARM_REPLAY_DIRECTORY}/{arm_slot}.json",
            },
        },
        "schema_version": ARM_BUDGET_TERMINAL_SCHEMA,
        "sealing_intent_identity": dict(sealing_intent_identity),
        "status": PENDING_TERMINAL_STATUS,
        "terminal_self_exclusion": {
            "terminal_contains_own_sha256": False,
            "terminal_contains_own_size": False,
            "terminal_path": terminal_relative_path,
            "terminal_path_excluded_from_arm_expected_path_types": True,
        },
    }


def _validate_arm_budget_terminal_ack(
    value: object,
    *,
    arm_slot: str,
    attempt_prefix: str,
    allocation_identity: Mapping[str, object],
    manifest_identity: Mapping[str, object],
    arm_expected_path_types: Sequence[Mapping[str, object]],
    arm_expected_path_types_digest: str,
    manifest_maximum_bytes: int,
    replay_maximum_bytes: int,
    consumption_maximum_bytes: int,
    terminal_relative_path: str,
    expected_terminal_path: Path,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    if type(value) is not dict or set(cast(dict[str, object], value)) != {
        "response_authentication",
        "terminal",
        "terminal_identity",
    }:
        _fail("ARM_SEAL_ACK_INVALID", "wrapper key set")
    wrapper = cast(dict[str, object], value)
    terminal = wrapper["terminal"]
    if type(terminal) is not dict:
        _fail("ARM_BUDGET_TERMINAL_INVALID", "terminal is not an object")
    terminal_record = cast(dict[str, object], terminal)
    if set(terminal_record) != {
        "allocation_state",
        "arm_allocation_identity",
        "arm_attempt_prefix",
        "arm_budget_reconcile",
        "arm_expected_path_types",
        "arm_expected_path_types_sha256",
        "arm_slot",
        "authority_scope",
        "authorizations",
        "global_journal_sequence_snapshot",
        "manifest_allocation_debit",
        "manifest_identity",
        "post_seal_reservations",
        "schema_version",
        "sealing_intent_identity",
        "status",
        "terminal_self_exclusion",
    }:
        _fail("ARM_BUDGET_TERMINAL_INVALID", "terminal key set")
    reconcile = _arm_budget_reconcile(
        terminal_record["arm_budget_reconcile"],
        arm_slot=arm_slot,
    )
    sealing_intent = _identity(
        terminal_record["sealing_intent_identity"],
        "sealing intent identity",
    )
    journal_snapshot = _journal_sequence_snapshot(
        terminal_record["global_journal_sequence_snapshot"]
    )
    expected_terminal = _expected_arm_budget_terminal(
        arm_slot=arm_slot,
        attempt_prefix=attempt_prefix,
        allocation_identity=allocation_identity,
        manifest_identity=manifest_identity,
        arm_expected_path_types=arm_expected_path_types,
        arm_expected_path_types_digest=arm_expected_path_types_digest,
        manifest_allocation_debit=_expected_manifest_debit(
            attempt_prefix=attempt_prefix,
            maximum_bytes=manifest_maximum_bytes,
        ),
        arm_budget_reconcile=reconcile,
        sealing_intent_identity=sealing_intent,
        global_journal_sequence_snapshot=journal_snapshot,
        terminal_relative_path=terminal_relative_path,
        replay_maximum_bytes=replay_maximum_bytes,
        consumption_maximum_bytes=consumption_maximum_bytes,
    )
    if terminal_record != expected_terminal:
        _fail("ARM_BUDGET_TERMINAL_INVALID", "terminal payload drift")
    checked_identity = _identity(
        wrapper["terminal_identity"],
        "arm budget terminal identity",
    )
    if checked_identity["path"] != str(expected_terminal_path):
        _fail("ARM_BUDGET_TERMINAL_INVALID", "terminal path drift")
    return (
        dict(terminal_record),
        checked_identity,
        _response_authentication(wrapper["response_authentication"]),
    )


def _read_identity_bound_regular(
    path: Path,
    *,
    expected_identity: Mapping[str, object],
    expected_raw: bytes | None,
    label: str,
) -> bytes:
    parent_fd = _open_absolute_directory(path.parent)
    primary: BaseException | None = None
    try:
        try:
            metadata = os.stat(
                path.name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            _fail("PUBLISHED_IDENTITY_OPEN_FAILED", f"{label}: {exc}")
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            _fail("PUBLISHED_IDENTITY_NODE_INVALID", label)
        digest, raw = _read_regular(
            parent_fd,
            path.name,
            metadata,
            label,
            capture=True,
        )
        if (
            (expected_raw is not None and raw != expected_raw)
            or digest != expected_identity["sha256"]
            or metadata.st_size != expected_identity["size_bytes"]
        ):
            _fail("PUBLISHED_IDENTITY_DRIFT", label)
        initial_parent = _directory_identity(os.fstat(parent_fd))
        rejoined = _open_absolute_directory(path.parent)
        try:
            if _directory_identity(os.fstat(rejoined)) != initial_parent:
                _fail("PUBLISHED_PARENT_CHANGED", str(path.parent))
        finally:
            os.close(rejoined)
    except BaseException as exc:
        primary = exc
    _close_preserving(parent_fd, primary, f"{label} parent")
    if primary is not None:
        raise primary
    assert raw is not None
    return raw


def _validate_prior_response_accepted(
    formal_root: Path,
    attempt_root: Path,
    *,
    accepted_result: Mapping[str, object],
    identity: Mapping[str, object],
    response_authentication: Mapping[str, object],
    arm_slot: str,
    manifest_identity: Mapping[str, object],
    terminal_identity: Mapping[str, object],
    expected_event_sequence: int,
    expected_continuation: str,
    expected_successor_arm_slot: str | None,
) -> dict[str, object]:
    checked_identity = _identity(
        identity,
        "prior-response-accepted journal identity",
    )
    path = Path(cast(str, checked_identity["path"]))
    try:
        path.relative_to(formal_root)
    except ValueError:
        _fail("PRIOR_RESPONSE_ACCEPTED_INVALID", "journal is outside formal root")
    try:
        path.relative_to(attempt_root)
    except ValueError:
        pass
    else:
        _fail("PRIOR_RESPONSE_ACCEPTED_INVALID", "journal is inside arm subtree")
    raw = _read_identity_bound_regular(
        path,
        expected_identity=checked_identity,
        expected_raw=None,
        label="prior-response-accepted journal",
    )
    parsed = _strict_json(raw, "prior-response-accepted journal")
    if set(parsed) != {
        "action",
        "actor",
        "event_sequence",
        "nonce",
        "request_sha256",
        "result",
        "schema_version",
    }:
        _fail("PRIOR_RESPONSE_ACCEPTED_INVALID", "journal key set")
    result = parsed["result"]
    if type(result) is not dict or set(cast(dict[str, object], result)) != {
        "arm_attempt_prefix",
        "arm_slot",
        "continuation",
        "manifest_identity",
        "prior_response_authentication",
        "schema_version",
        "state",
        "successor_arm_slot",
        "terminal_identity",
    }:
        _fail("PRIOR_RESPONSE_ACCEPTED_INVALID", "journal result key set")
    expected_result = {
        "arm_attempt_prefix": str(attempt_root.relative_to(formal_root)),
        "arm_slot": arm_slot,
        "continuation": expected_continuation,
        "manifest_identity": dict(manifest_identity),
        "prior_response_authentication": dict(response_authentication),
        "schema_version": (
            "noncert-cuts-ab16-prior-arm-seal-response-accepted-v1"
        ),
        "state": "PRIOR_RESPONSE_ACCEPTED",
        "successor_arm_slot": expected_successor_arm_slot,
        "terminal_identity": dict(terminal_identity),
    }
    if (
        expected_continuation == "next-arm"
        and (
            type(expected_successor_arm_slot) is not str
            or _SAFE_TOKEN_RE.fullmatch(expected_successor_arm_slot) is None
            or expected_successor_arm_slot == arm_slot
        )
    ):
        _fail("PRIOR_RESPONSE_ACCEPTED_INVALID", "successor arm boundary")
    if (
        expected_continuation == "formal-finalize"
        and expected_successor_arm_slot is not None
    ):
        _fail("PRIOR_RESPONSE_ACCEPTED_INVALID", "finalize successor boundary")
    if expected_continuation not in {"next-arm", "formal-finalize"}:
        _fail("PRIOR_RESPONSE_ACCEPTED_INVALID", "continuation boundary")
    if (
        parsed["schema_version"] != BROKER_JOURNAL_SCHEMA
        or parsed["action"] != PRIOR_RESPONSE_ACCEPTED_ACTION
        or type(parsed["actor"]) is not dict
        or not cast(dict[str, object], parsed["actor"])
        or parsed["event_sequence"] != expected_event_sequence
        or parsed["nonce"] != response_authentication["nonce"]
        or type(parsed["request_sha256"]) is not str
        or _SHA256_RE.fullmatch(cast(str, parsed["request_sha256"])) is None
        or result != expected_result
        or dict(accepted_result) != expected_result
    ):
        _fail("PRIOR_RESPONSE_ACCEPTED_INVALID", "journal boundary or join")
    return parsed


def publish_arm_attempt_manifest(
    formal_root: Path | str,
    *,
    arm_attempt_prefix: str,
    arm_slot: str,
    bindings: Mapping[str, object],
    expected_path_types_before: Sequence[Mapping[str, object]],
    budget_backend: ArmManifestSealBackend,
) -> dict[str, object]:
    """Atomically publish the self-excluded manifest and irreversibly seal.

    This function deliberately has no generic publication fallback.  The
    package-pinned broker must publish the manifest, publish the arm budget
    terminal outside the attempt subtree, and reject every later arm write
    before returning one acknowledgement.
    """

    if type(arm_slot) is not str or _SAFE_TOKEN_RE.fullmatch(arm_slot) is None:
        _fail("ARM_SLOT_INVALID", repr(arm_slot))
    checked_bindings = _bindings(bindings)
    root = Path(os.path.abspath(formal_root))
    if not Path(formal_root).is_absolute():
        _fail("ROOT_PATH_INVALID", str(formal_root))
    prefix_parts = _relative_parts(arm_attempt_prefix, "attempt prefix")
    prefix = "/".join(prefix_parts)
    attempt_root = root.joinpath(*prefix_parts)
    terminal_path = attempt_root / TERMINAL_MANIFEST_NAME
    terminal_relative = f"{ARM_BUDGET_TERMINAL_DIRECTORY}/{arm_slot}.json"
    arm_budget_terminal_path = root.joinpath(
        *_relative_parts(terminal_relative, "arm budget terminal path")
    )
    try:
        arm_budget_terminal_path.relative_to(attempt_root)
    except ValueError:
        pass
    else:
        _fail(
            "ARM_BUDGET_TERMINAL_PATH_INVALID",
            "arm budget terminal is inside attempt subtree",
        )

    all_before_rows, _before_rows, before_types, _before_digest = _inventory(
        list(expected_path_types_before),
        attempt_prefix=prefix,
        terminal_present=False,
    )
    initial = _snapshot(attempt_root, capture_terminal=False)
    _require_snapshot_types(initial, before_types, "prepublication")
    if initial.terminal_raw is not None:
        _fail("MANIFEST_PREEXISTS", str(terminal_path))

    predicted_all_rows = _add_inventory_regular(
        all_before_rows,
        f"{prefix}/{TERMINAL_MANIFEST_NAME}",
    )
    predicted_all_rows = _add_inventory_regular(
        predicted_all_rows,
        terminal_relative,
    )
    (
        _validated_all_rows,
        predicted_rows,
        predicted_types,
        predicted_digest,
    ) = _inventory(
        list(predicted_all_rows),
        attempt_prefix=prefix,
        terminal_present=True,
    )
    manifest = _manifest_record(
        arm_slot=arm_slot,
        attempt_prefix=prefix,
        final_inventory_digest=predicted_digest,
        entries=initial.entries,
        bindings=checked_bindings,
    )
    raw = _canonical_json(manifest)
    maximum = budget_backend.maximum_bytes(
        MANIFEST_BUDGET_LABEL,
        artifact_class=MANIFEST_ARTIFACT_CLASS,
    )
    replay_maximum = budget_backend.maximum_bytes(
        REPLAY_BUDGET_LABEL,
        artifact_class=REPLAY_ARTIFACT_CLASS,
    )
    consumption_maximum = budget_backend.maximum_bytes(
        CONSUMPTION_BUDGET_LABEL,
        artifact_class=CONSUMPTION_ARTIFACT_CLASS,
    )
    if type(maximum) is not int or maximum <= 0 or len(raw) > maximum:
        _fail("BUDGET_INVALID", f"{MANIFEST_BUDGET_LABEL}: fixed maximum")
    allocation_identity = checked_bindings["arm_allocation_identity"]
    manifest_identity = _publication_identity(terminal_path, raw)
    try:
        acknowledgement = budget_backend.publish_arm_manifest_and_seal(
            terminal_path,
            raw,
            maximum_bytes=maximum,
            artifact_class=MANIFEST_ARTIFACT_CLASS,
            label=MANIFEST_BUDGET_LABEL,
            arm_slot=arm_slot,
            arm_attempt_prefix=prefix,
            arm_allocation_identity=allocation_identity,
            expected_path_types_before=all_before_rows,
        )
    except BaseException as exc:
        raise ArmAttemptClosureError(
            "ARM_SEAL_FAILED_OR_UNCERTAIN",
            f"{type(exc).__name__}: {exc}",
        ) from exc
    (
        arm_budget_terminal,
        arm_budget_terminal_identity,
        seal_response_authentication,
    ) = (
        _validate_arm_budget_terminal_ack(
            acknowledgement,
            arm_slot=arm_slot,
            attempt_prefix=prefix,
            allocation_identity=allocation_identity,
            manifest_identity=manifest_identity,
            arm_expected_path_types=predicted_rows,
            arm_expected_path_types_digest=predicted_digest,
            manifest_maximum_bytes=maximum,
            replay_maximum_bytes=replay_maximum,
            consumption_maximum_bytes=consumption_maximum,
            terminal_relative_path=terminal_relative,
            expected_terminal_path=arm_budget_terminal_path,
        )
    )
    terminal_raw = _canonical_json(arm_budget_terminal)
    if (
        arm_budget_terminal_identity["sha256"]
        != hashlib.sha256(terminal_raw).hexdigest()
        or arm_budget_terminal_identity["size_bytes"] != len(terminal_raw)
    ):
        _fail("ARM_BUDGET_TERMINAL_INVALID", "terminal byte identity drift")
    _read_identity_bound_regular(
        arm_budget_terminal_path,
        expected_identity=arm_budget_terminal_identity,
        expected_raw=terminal_raw,
        label="arm budget terminal",
    )
    final = _snapshot(attempt_root, capture_terminal=True)
    _require_snapshot_types(final, predicted_types, "post-seal")
    if final.terminal_raw != raw:
        _fail("MANIFEST_PUBLICATION_DRIFT", str(terminal_path))
    if tuple(
        entry
        for entry in final.entries
        if entry["path"] != TERMINAL_MANIFEST_NAME
    ) != initial.entries:
        _fail("ROOT_CHANGED", "arm descendants changed during manifest publication")
    return {
        "arm_budget_terminal": arm_budget_terminal,
        "arm_budget_terminal_identity": arm_budget_terminal_identity,
        "arm_seal_response_authentication": seal_response_authentication,
        "manifest": manifest,
        "manifest_identity": manifest_identity,
    }


def _validate_manifest(
    raw: bytes,
    *,
    arm_slot: str,
    attempt_prefix: str,
    bindings: Mapping[str, Mapping[str, object]],
    inventory_digest: str,
    expected_entries: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    record = _strict_json(raw, "arm attempt manifest")
    if set(record) != {
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
    }:
        _fail("MANIFEST_INVALID", "key set")
    if (
        record["schema_version"] != MANIFEST_SCHEMA
        or record["status"] != "CLOSED_NO_GLOBAL_AUTHORITY"
        or record["authority_scope"] != AUTHORITY_SCOPE
        or record["authorizations"] != FALSE_AUTHORIZATIONS
        or record["arm_slot"] != arm_slot
        or record["arm_attempt_prefix"] != attempt_prefix
        or record["bindings"] != {
            key: dict(value) for key, value in sorted(bindings.items())
        }
        or record["entries"] != [dict(entry) for entry in expected_entries]
        or record["inventory"]
        != {
            "schema_version": ROOT_INVENTORY_SCHEMA,
            "arm_expected_path_types_sha256": inventory_digest,
        }
        or record["terminal_self_exclusion"]
        != {
            "manifest_contains_own_sha256": False,
            "manifest_contains_own_size": False,
            "manifest_path": TERMINAL_MANIFEST_NAME,
            "manifest_path_excluded_from_entries": True,
        }
    ):
        _fail("MANIFEST_INVALID", "boundary or join")
    if any(
        type(entry) is not dict
        or cast(dict[str, object], entry).get("path") == TERMINAL_MANIFEST_NAME
        for entry in cast(list[object], record["entries"])
    ):
        _fail("MANIFEST_SELF_REFERENCE", TERMINAL_MANIFEST_NAME)
    return record


def _safe_publish_outside(
    backend: PostSealReplayBackend,
    *,
    path: Path,
    arm_root: Path,
    raw: bytes,
) -> dict[str, object]:
    if not path.is_absolute():
        _fail("REPLAY_PATH_INVALID", str(path))
    try:
        path.relative_to(arm_root)
    except ValueError:
        pass
    else:
        _fail("REPLAY_PATH_INVALID", "outside replay is inside arm subtree")
    parent_fd = _open_absolute_directory(path.parent)
    primary: BaseException | None = None
    try:
        parent_identity = _directory_identity(os.fstat(parent_fd))
        try:
            os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        except OSError as exc:
            _fail("REPLAY_PATH_CHECK_FAILED", f"{path}: {exc}")
        else:
            _fail("REPLAY_PREEXISTS", str(path))
        maximum = backend.maximum_bytes(
            REPLAY_BUDGET_LABEL,
            artifact_class=REPLAY_ARTIFACT_CLASS,
        )
        if type(maximum) is not int or maximum <= 0 or len(raw) > maximum:
            _fail("BUDGET_INVALID", f"{REPLAY_BUDGET_LABEL}: fixed maximum")
        receipt = dict(
            backend.publish_accepted_arm_replay(
                path,
                raw,
                maximum_bytes=maximum,
                label=REPLAY_BUDGET_LABEL,
            )
        )
        if receipt != _publication_identity(path, raw):
            _fail("BUDGET_PUBLICATION_DRIFT", REPLAY_BUDGET_LABEL)
        try:
            metadata = os.stat(
                path.name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            _fail("REPLAY_PUBLICATION_DRIFT", f"{path}: {exc}")
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            _fail("REPLAY_PUBLICATION_DRIFT", f"{path}: node type")
        digest, captured = _read_regular(
            parent_fd,
            path.name,
            metadata,
            path.name,
            capture=True,
        )
        if captured != raw or digest != hashlib.sha256(raw).hexdigest():
            _fail("REPLAY_PUBLICATION_DRIFT", str(path))
        rejoined = _open_absolute_directory(path.parent)
        try:
            if _directory_identity(os.fstat(rejoined)) != parent_identity:
                _fail("REPLAY_PARENT_CHANGED", str(path.parent))
        finally:
            os.close(rejoined)
        result = receipt
    except BaseException as exc:
        primary = exc
        result = None
    _close_preserving(parent_fd, primary, "outside replay parent")
    if primary is not None:
        raise primary
    assert result is not None
    return result


def replay_and_publish_arm_attempt_root(
    formal_root: Path | str,
    *,
    arm_attempt_prefix: str,
    arm_slot: str,
    bindings: Mapping[str, object],
    expected_path_types: Sequence[Mapping[str, object]],
    expected_manifest_identity: Mapping[str, object],
    expected_arm_budget_terminal: Mapping[str, object],
    expected_arm_budget_terminal_identity: Mapping[str, object],
    expected_arm_seal_response_authentication: Mapping[str, object],
    prior_response_accepted_result: Mapping[str, object],
    prior_response_accepted_identity: Mapping[str, object],
    accepted_continuation: str,
    accepted_successor_arm_slot: str | None,
    replay_path: Path | str,
    budget_backend: PostSealReplayBackend,
) -> dict[str, object]:
    """Independently re-enumerate one closed arm and publish an outside replay."""

    if type(arm_slot) is not str or _SAFE_TOKEN_RE.fullmatch(arm_slot) is None:
        _fail("ARM_SLOT_INVALID", repr(arm_slot))
    checked_bindings = _bindings(bindings)
    root = Path(os.path.abspath(formal_root))
    if not Path(formal_root).is_absolute():
        _fail("ROOT_PATH_INVALID", str(formal_root))
    prefix_parts = _relative_parts(arm_attempt_prefix, "attempt prefix")
    prefix = "/".join(prefix_parts)
    attempt_root = root.joinpath(*prefix_parts)
    manifest_path = attempt_root / TERMINAL_MANIFEST_NAME
    terminal_relative = f"{ARM_BUDGET_TERMINAL_DIRECTORY}/{arm_slot}.json"
    arm_budget_terminal_path = root.joinpath(
        *_relative_parts(terminal_relative, "arm budget terminal path")
    )
    checked_manifest_identity = _identity(
        expected_manifest_identity,
        "expected manifest identity",
    )
    if checked_manifest_identity["path"] != str(manifest_path):
        _fail("MANIFEST_IDENTITY_DRIFT", "path")
    checked_terminal_identity = _identity(
        expected_arm_budget_terminal_identity,
        "expected arm budget terminal identity",
    )
    if checked_terminal_identity["path"] != str(arm_budget_terminal_path):
        _fail("ARM_BUDGET_TERMINAL_INVALID", "identity path drift")

    _all_rows, arm_rows, expected_types, inventory_digest = _inventory(
        list(expected_path_types),
        attempt_prefix=prefix,
        terminal_present=True,
    )
    response_authentication = _response_authentication(
        expected_arm_seal_response_authentication
    )
    manifest_maximum = budget_backend.maximum_bytes(
        MANIFEST_BUDGET_LABEL,
        artifact_class=MANIFEST_ARTIFACT_CLASS,
    )
    replay_maximum = budget_backend.maximum_bytes(
        REPLAY_BUDGET_LABEL,
        artifact_class=REPLAY_ARTIFACT_CLASS,
    )
    consumption_maximum = budget_backend.maximum_bytes(
        CONSUMPTION_BUDGET_LABEL,
        artifact_class=CONSUMPTION_ARTIFACT_CLASS,
    )
    if type(manifest_maximum) is not int or manifest_maximum <= 0:
        _fail("BUDGET_INVALID", f"{MANIFEST_BUDGET_LABEL}: fixed maximum")
    (
        expected_terminal_record,
        _validated_terminal_identity,
        _validated_response_authentication,
    ) = _validate_arm_budget_terminal_ack(
        {
            "response_authentication": response_authentication,
            "terminal": dict(expected_arm_budget_terminal),
            "terminal_identity": checked_terminal_identity,
        },
        arm_slot=arm_slot,
        attempt_prefix=prefix,
        allocation_identity=checked_bindings["arm_allocation_identity"],
        manifest_identity=checked_manifest_identity,
        arm_expected_path_types=arm_rows,
        arm_expected_path_types_digest=inventory_digest,
        manifest_maximum_bytes=manifest_maximum,
        replay_maximum_bytes=replay_maximum,
        consumption_maximum_bytes=consumption_maximum,
        terminal_relative_path=terminal_relative,
        expected_terminal_path=arm_budget_terminal_path,
    )
    terminal_raw = _canonical_json(expected_terminal_record)
    if (
        checked_terminal_identity["sha256"]
        != hashlib.sha256(terminal_raw).hexdigest()
        or checked_terminal_identity["size_bytes"] != len(terminal_raw)
    ):
        _fail("ARM_BUDGET_TERMINAL_INVALID", "detached identity drift")
    _read_identity_bound_regular(
        arm_budget_terminal_path,
        expected_identity=checked_terminal_identity,
        expected_raw=terminal_raw,
        label="arm budget terminal replay input",
    )
    journal_snapshot = cast(
        dict[str, object],
        expected_terminal_record["global_journal_sequence_snapshot"],
    )
    accepted_journal = _validate_prior_response_accepted(
        root,
        attempt_root,
        accepted_result=prior_response_accepted_result,
        identity=prior_response_accepted_identity,
        response_authentication=response_authentication,
        arm_slot=arm_slot,
        manifest_identity=checked_manifest_identity,
        terminal_identity=checked_terminal_identity,
        expected_event_sequence=cast(
            int,
            journal_snapshot["next_event_sequence"],
        ),
        expected_continuation=accepted_continuation,
        expected_successor_arm_slot=accepted_successor_arm_slot,
    )
    checked_accepted_identity = _identity(
        prior_response_accepted_identity,
        "prior-response-accepted identity",
    )
    first = _snapshot(attempt_root, capture_terminal=True)
    _require_snapshot_types(first, expected_types, "independent replay")
    if first.terminal_raw is None:
        _fail("MANIFEST_MISSING", str(manifest_path))
    manifest_identity = _publication_identity(manifest_path, first.terminal_raw)
    if manifest_identity != checked_manifest_identity:
        _fail("MANIFEST_IDENTITY_DRIFT", str(manifest_path))
    manifest_entries = tuple(
        entry
        for entry in first.entries
        if entry["path"] != TERMINAL_MANIFEST_NAME
    )
    manifest = _validate_manifest(
        first.terminal_raw,
        arm_slot=arm_slot,
        attempt_prefix=prefix,
        bindings=checked_bindings,
        inventory_digest=inventory_digest,
        expected_entries=manifest_entries,
    )
    replay = {
        "acknowledgement_continuation": {
            "continuation": accepted_continuation,
            "successor_arm_slot": accepted_successor_arm_slot,
        },
        "arm_attempt_prefix": prefix,
        "arm_slot": arm_slot,
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "bindings": {
            key: dict(value) for key, value in sorted(checked_bindings.items())
        },
        "inventory": {
            "schema_version": ROOT_INVENTORY_SCHEMA,
            "arm_expected_path_types_sha256": inventory_digest,
        },
        "arm_budget_terminal_identity": checked_terminal_identity,
        "prior_response_accepted_identity": checked_accepted_identity,
        "seal_response_authentication": response_authentication,
        "manifest_identity": manifest_identity,
        "root_observation": {
            "entry_count_including_manifest": len(first.entries),
            "root_signature": list(first.root_signature),
        },
        "schema_version": REPLAY_SCHEMA,
        "status": "REPLAY_ACCEPTED_NO_GLOBAL_AUTHORITY",
    }
    replay_raw = _canonical_json(replay)
    outside_path = Path(os.path.abspath(replay_path))
    if not Path(replay_path).is_absolute():
        _fail("REPLAY_PATH_INVALID", str(replay_path))
    expected_outside_path = root.joinpath(
        *_relative_parts(
            f"{ARM_REPLAY_DIRECTORY}/{arm_slot}.json",
            "fixed replay path",
        )
    )
    if outside_path != expected_outside_path:
        _fail("REPLAY_PATH_INVALID", "path differs from fixed replay target")
    publication = _safe_publish_outside(
        budget_backend,
        path=outside_path,
        arm_root=attempt_root,
        raw=replay_raw,
    )
    second = _snapshot(attempt_root, capture_terminal=True)
    if second != first:
        _fail("ROOT_CHANGED", "arm subtree changed during outside replay publication")
    # Re-parse after all joins so a future record-shape change cannot turn the
    # constructor's own object into its acceptance authority.
    _validate_manifest(
        cast(bytes, second.terminal_raw),
        arm_slot=arm_slot,
        attempt_prefix=prefix,
        bindings=checked_bindings,
        inventory_digest=inventory_digest,
        expected_entries=manifest_entries,
    )
    return {
        "manifest": manifest,
        "prior_response_accepted": accepted_journal,
        "replay": replay,
        "replay_identity": _publication_identity(outside_path, replay_raw),
        "publication": publication,
    }


def verify_published_arm_attempt_replay(
    replay_path: Path | str,
    *,
    expected_replay_identity: Mapping[str, object],
    expected_manifest_identity: Mapping[str, object],
    expected_arm_budget_terminal_identity: Mapping[str, object],
    expected_arm_seal_response_authentication: Mapping[str, object],
    expected_prior_response_accepted_identity: Mapping[str, object],
    expected_accepted_continuation: str,
    expected_accepted_successor_arm_slot: str | None,
    arm_attempt_prefix: str,
    arm_slot: str,
    bindings: Mapping[str, object],
) -> dict[str, object]:
    """Read a detached replay through stable descriptors and reject tampering."""

    path = Path(os.path.abspath(replay_path))
    if not Path(replay_path).is_absolute():
        _fail("REPLAY_PATH_INVALID", str(replay_path))
    checked_replay = _identity(expected_replay_identity, "expected replay identity")
    checked_manifest = _identity(
        expected_manifest_identity,
        "expected manifest identity",
    )
    checked_terminal = _identity(
        expected_arm_budget_terminal_identity,
        "expected arm budget terminal identity",
    )
    checked_response_authentication = _response_authentication(
        expected_arm_seal_response_authentication
    )
    checked_accepted = _identity(
        expected_prior_response_accepted_identity,
        "expected prior-response-accepted identity",
    )
    checked_bindings = _bindings(bindings)
    if checked_replay["path"] != str(path):
        _fail("REPLAY_IDENTITY_DRIFT", "path")
    parent_fd = _open_absolute_directory(path.parent)
    primary: BaseException | None = None
    try:
        parent_identity = _directory_identity(os.fstat(parent_fd))
        try:
            metadata = os.stat(
                path.name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            _fail("REPLAY_OPEN_FAILED", f"{path}: {exc}")
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            _fail("REPLAY_NODE_INVALID", str(path))
        digest, raw = _read_regular(
            parent_fd,
            path.name,
            metadata,
            path.name,
            capture=True,
        )
        assert raw is not None
        if _publication_identity(path, raw) != checked_replay:
            _fail("REPLAY_IDENTITY_DRIFT", str(path))
        record = _strict_json(raw, "arm attempt replay")
        if set(record) != {
            "acknowledgement_continuation",
            "arm_budget_terminal_identity",
            "arm_attempt_prefix",
            "arm_slot",
            "authority_scope",
            "authorizations",
            "bindings",
            "inventory",
            "manifest_identity",
            "prior_response_accepted_identity",
            "root_observation",
            "schema_version",
            "seal_response_authentication",
            "status",
        }:
            _fail("REPLAY_INVALID", "key set")
        if (
            record["schema_version"] != REPLAY_SCHEMA
            or record["status"] != "REPLAY_ACCEPTED_NO_GLOBAL_AUTHORITY"
            or record["authority_scope"] != AUTHORITY_SCOPE
            or record["authorizations"] != FALSE_AUTHORIZATIONS
            or record["arm_attempt_prefix"] != arm_attempt_prefix
            or record["arm_slot"] != arm_slot
            or record["manifest_identity"] != checked_manifest
            or record["arm_budget_terminal_identity"] != checked_terminal
            or record["prior_response_accepted_identity"] != checked_accepted
            or record["seal_response_authentication"]
            != checked_response_authentication
            or record["acknowledgement_continuation"]
            != {
                "continuation": expected_accepted_continuation,
                "successor_arm_slot": (
                    expected_accepted_successor_arm_slot
                ),
            }
            or record["bindings"]
            != {
                key: dict(value)
                for key, value in sorted(checked_bindings.items())
            }
            or digest != checked_replay["sha256"]
        ):
            _fail("REPLAY_INVALID", "boundary or join")
        rejoined = _open_absolute_directory(path.parent)
        try:
            if _directory_identity(os.fstat(rejoined)) != parent_identity:
                _fail("REPLAY_PARENT_CHANGED", str(path.parent))
        finally:
            os.close(rejoined)
        result = record
    except BaseException as exc:
        primary = exc
        result = None
    _close_preserving(parent_fd, primary, "replay verification parent")
    if primary is not None:
        raise primary
    assert result is not None
    return result
