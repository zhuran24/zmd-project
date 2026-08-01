#!/usr/bin/env python3
"""Campaign-root authority for the non-certified cuts Gate 1 v4 campaign.

This module owns byte identity and topology only.  It does not start a unit or
solver.  Qualification receipts prove byte consistency; the package-external
campaign root is the launch-authority root.  Gate 1 may issue a continuation
authorization for the reserved prospective A/B child, but it never closes the
campaign or launches an organic arm.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import os
import re
import stat
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


PACKAGE_SCHEMA = "noncert-cuts-campaign-authority-package-v4"
PACKAGE_MANIFEST_SCHEMA = "noncert-cuts-campaign-authority-manifest-v4"
MANAGER_EPOCH_SCHEMA = "noncert-cuts-manager-boot-epoch-v4"
MANAGER_EPOCH_TRANSCRIPT_SCHEMA = "noncert-cuts-manager-boot-epoch-capture-transcript-v4"
ATTESTOR_SCHEMA = "noncert-cuts-privileged-manager-attestation-v4"
ATTESTOR_AUDIT_SCHEMA = "noncert-cuts-read-only-attestor-audit-v4"
CAMPAIGN_ROOT_SCHEMA = "noncert-cuts-campaign-root-v4"
GATE1_SELECTION_SCHEMA = "noncert-cuts-gate1-v4-child-selection-v1"
CONTINUATION_SCHEMA = "noncert-cuts-gate1-v4-continuation-authorization-v1"
GATE_ADMISSION_EPOCH_SCHEMA = "noncert-cuts-gate1-v4-manager-epoch-checkpoint-v2"

GATE1_PURPOSE = "gate1_v4_child_suite"
CAMPAIGN_PURPOSE = "cuts_credibility_mandatory_campaign"
GATE1_SLOTS = (
    "q-success",
    "q-postseal-fail",
    "forced-control",
    "forced-treatment",
)
GATE_ADMISSION_CAPTURE_TOOL_ROLES = frozenset(
    {
        "attestor_python",
        "busctl",
        "campaign_authority_v4",
        "gate1_campaign_driver_v4",
        "manager_attestor_v4",
        "sudo",
    }
)
REQUIRED_GATE1_TOOL_ROLES = frozenset(
    {
        "attestor_python",
        "busctl",
        "campaign_authority_v4",
        "gate1_campaign_bootstrap_v4",
        "gate1_campaign_driver_v4",
        "gate1_campaign_execution_v4",
        "gate1_payload_v4",
        "gate1_unit_orchestrator_v4",
        "independent_arithmetic_v4",
        "manager_attestor_v4",
        "positive_control_formal_v4",
        "positive_control_v4",
        "positive_control_gate_v4",
        "python3_13",
        "resource_lifecycle_v4",
        "resource_verifier_v4",
        "sudo",
        "systemctl",
        "systemd_run",
    }
)
REQUIRED_GATE1_INPUT_ROLES = frozenset(
    {
        "candidate_placements",
        "canonical_rules",
        "cuts_mandatory_schedule",
        "history_freeze_manifest",
        "mandatory_instances",
        "project_lock",
    }
)
AB16_CONFIGURATIONS = (
    "region-capacity",
    "shape-packing-hall",
    "power-hitting-set",
    "bundle",
)
AB16_ORDERS = ("ab", "ba")
AB16_ARMS = ("control", "treatment")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
DBUS_OWNER_RE = re.compile(r":[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\Z")
ROLE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
UNIT_NAMESPACE_RE = re.compile(r"cuts-g1v4-[0-9a-f]{12}\Z")

RESOURCE_CONTRACT: dict[str, object] = {
    "kill_mode": "control-group",
    "memory_high_bytes": 35 * 1024**3,
    "memory_max_bytes": 39 * 1024**3,
    "memory_swap_max_bytes": 16 * 1024**3,
    "oom_policy": "continue",
    "profiles": {
        "formal": {
            "internal_timeout_seconds": 1470,
            "keeper_timeout_seconds": 1490,
            "runtime_max_seconds": 1500,
        },
        "synthetic": {
            "internal_timeout_seconds": 30,
            "keeper_timeout_seconds": 90,
            "runtime_max_seconds": 120,
        },
    },
    "send_sigkill": True,
}

_LOADER = (
    "import sys;"
    "_source=sys.stdin.buffer.read();"
    "_namespace={'__name__':'__main__','__file__':'<cuts-manager-attestor-stdin>',"
    "'__package__':None};"
    "exec(compile(_source,'<cuts-manager-attestor-stdin>','exec',"
    "dont_inherit=True),_namespace,_namespace)"
)


class AuthorityError(RuntimeError):
    """Fail-closed authority construction or replay failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Snapshot:
    """One byte stream captured through a stable O_NOFOLLOW descriptor."""

    path: Path
    data: bytes
    sha256: str
    stat_result: os.stat_result

    @property
    def size(self) -> int:
        return len(self.data)


@dataclass(frozen=True)
class SourceSpec:
    """One package source and its package-local role."""

    role: str
    path: Path
    parse_json: bool = False


def canonical_json(value: object) -> bytes:
    """Return the sole accepted JSON byte representation."""

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


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def strict_loads(raw: bytes, label: str) -> object:
    """Parse strict UTF-8 JSON, rejecting duplicates, floats, and NaN."""

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise AuthorityError("JSON_DUPLICATE_KEY", f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject_float(value: str) -> object:
        raise AuthorityError("JSON_FLOAT_REJECTED", f"{label}: floating point value {value!r}")

    def reject_constant(value: str) -> object:
        raise AuthorityError("JSON_CONSTANT_REJECTED", f"{label}: invalid constant {value!r}")

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=reject_constant,
            parse_float=reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthorityError("JSON_INVALID", f"{label}: invalid strict JSON: {exc}") from exc


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _stat_signature(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _reject_symlink_chain(path: Path, *, missing_leaf: bool = False) -> None:
    absolute = _absolute(path)
    current = Path(absolute.anchor)
    parts = absolute.parts[1:]
    for index, part in enumerate(parts):
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if missing_leaf and index == len(parts) - 1:
                return
            raise AuthorityError("PATH_MISSING", f"path component is missing: {current}") from None
        if stat.S_ISLNK(metadata.st_mode):
            raise AuthorityError("SYMLINK_REJECTED", f"symlink path component rejected: {current}")


def snapshot_regular(
    path: Path | str,
    *,
    after_read: Callable[[Path], None] | None = None,
    size_limit: int = 1 << 31,
) -> Snapshot:
    """Read/hash one regular file using a single stable O_NOFOLLOW FD."""

    absolute = _absolute(path)
    _reject_symlink_chain(absolute)
    if not hasattr(os, "O_NOFOLLOW"):
        raise AuthorityError("NOFOLLOW_UNAVAILABLE", "O_NOFOLLOW is required")
    before_path = os.stat(absolute, follow_symlinks=False)
    if not stat.S_ISREG(before_path.st_mode):
        raise AuthorityError("NON_REGULAR_INPUT", f"input is not regular: {absolute}")
    if before_path.st_size < 0 or before_path.st_size > size_limit:
        raise AuthorityError("INPUT_SIZE_LIMIT", f"input size is outside the fixed cap: {absolute}")
    descriptor = os.open(
        absolute,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        before_fd = os.fstat(descriptor)
        if _stat_signature(before_path) != _stat_signature(before_fd):
            raise AuthorityError("INPUT_RACE", f"input changed before read: {absolute}")
        chunks: list[bytes] = []
        remaining = before_fd.st_size
        while remaining:
            block = os.read(descriptor, min(1 << 20, remaining))
            if not block:
                raise AuthorityError("INPUT_RACE", f"input truncated during read: {absolute}")
            chunks.append(block)
            remaining -= len(block)
        if os.read(descriptor, 1):
            raise AuthorityError("INPUT_RACE", f"input grew during read: {absolute}")
        if after_read is not None:
            after_read(absolute)
        after_fd = os.fstat(descriptor)
        after_path = os.stat(absolute, follow_symlinks=False)
        if _stat_signature(before_fd) != _stat_signature(after_fd):
            raise AuthorityError("INPUT_RACE", f"descriptor changed during read: {absolute}")
        if _stat_signature(after_fd) != _stat_signature(after_path):
            raise AuthorityError("INPUT_RACE", f"path identity changed during read: {absolute}")
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    if len(raw) != before_fd.st_size:
        raise AuthorityError("INPUT_RACE", f"input byte count drifted: {absolute}")
    return Snapshot(
        path=absolute,
        data=raw,
        sha256=sha256_bytes(raw),
        stat_result=after_fd,
    )


def detached_identity(snapshot: Snapshot) -> dict[str, object]:
    return {
        "path": str(snapshot.path),
        "sha256": snapshot.sha256,
        "size_bytes": snapshot.size,
    }


def full_identity(snapshot: Snapshot, *, requested_path: str | None = None) -> dict[str, object]:
    mode = stat.S_IMODE(snapshot.stat_result.st_mode)
    result: dict[str, object] = {
        "device": snapshot.stat_result.st_dev,
        "inode": snapshot.stat_result.st_ino,
        "mode": mode,
        "mode_octal": f"{mode:04o}",
        "path": str(snapshot.path),
        "sha256": snapshot.sha256,
        "size_bytes": snapshot.size,
    }
    if requested_path is not None:
        result["requested_path"] = requested_path
    return result


def snapshot_tool(path: Path | str, *, size_limit: int = 1 << 30) -> tuple[bytes, dict[str, object]]:
    """Resolve one tool once and bind both requested and real path."""

    requested = str(_absolute(path))
    resolved = os.path.realpath(requested)
    if not os.path.isabs(resolved):
        raise AuthorityError("TOOL_PATH_INVALID", f"tool did not resolve absolutely: {requested}")
    snapshot = snapshot_regular(resolved, size_limit=size_limit)
    if os.path.realpath(requested) != resolved:
        raise AuthorityError("TOOL_PATH_RACE", f"tool symlink chain changed: {requested}")
    return snapshot.data, full_identity(snapshot, requested_path=requested)


def validate_detached_identity(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256", "size_bytes"}:
        raise AuthorityError("IDENTITY_INVALID", f"{label}: detached identity key set drifted")
    if (
        type(value["path"]) is not str
        or not Path(value["path"]).is_absolute()
        or type(value["size_bytes"]) is not int
        or value["size_bytes"] < 0
        or type(value["sha256"]) is not str
        or SHA256_RE.fullmatch(value["sha256"]) is None
    ):
        raise AuthorityError("IDENTITY_INVALID", f"{label}: detached identity is malformed")
    return value


def identity_from_bytes(path: Path | str, raw: bytes) -> dict[str, object]:
    return {
        "path": str(_absolute(path)),
        "sha256": sha256_bytes(raw),
        "size_bytes": len(raw),
    }


def replay_detached_identity(value: Mapping[str, object], label: str) -> Snapshot:
    """Reopen one named file only to prove it still has the bound identity."""

    expected = validate_detached_identity(value, label)
    current = snapshot_regular(expected["path"])
    if detached_identity(current) != expected:
        raise AuthorityError("DETACHED_IDENTITY_DRIFT", f"{label}: current bytes drifted")
    return current


def verify_bytes_identity(
    raw: bytes,
    expected: Mapping[str, object],
    *,
    path: Path | str | None = None,
) -> None:
    record = validate_detached_identity(expected, "expected identity")
    if len(raw) != record["size_bytes"] or sha256_bytes(raw) != record["sha256"]:
        raise AuthorityError("DETACHED_IDENTITY_DRIFT", "detached byte size/SHA-256 drifted")
    if path is not None and str(_absolute(path)) != record["path"]:
        raise AuthorityError("DETACHED_IDENTITY_DRIFT", "detached canonical path drifted")


def write_exclusive(path: Path | str, raw: bytes, *, mode: int = 0o600) -> dict[str, object]:
    """Write one immutable file relative to an already-open no-symlink parent."""

    absolute = _absolute(path)
    parent = absolute.parent
    _reject_symlink_chain(parent)
    if not parent.is_dir():
        raise AuthorityError("OUTPUT_PARENT_INVALID", f"output parent is not a directory: {parent}")
    parent_fd = os.open(
        parent,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        descriptor = os.open(
            absolute.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            mode,
            dir_fd=parent_fd,
        )
        try:
            offset = 0
            while offset < len(raw):
                written = os.write(descriptor, raw[offset:])
                if written <= 0:
                    raise AuthorityError("OUTPUT_SHORT_WRITE", f"short write: {absolute}")
                offset += written
            os.fsync(descriptor)
            metadata = os.fstat(descriptor)
            if metadata.st_size != len(raw):
                raise AuthorityError("OUTPUT_SHORT_WRITE", f"output size mismatch: {absolute}")
        finally:
            os.close(descriptor)
        os.fsync(parent_fd)
    except FileExistsError as exc:
        raise AuthorityError("NO_OVERWRITE_COLLISION", f"refusing to overwrite: {absolute}") from exc
    finally:
        os.close(parent_fd)
    return detached_identity(snapshot_regular(absolute))


def mkdir_exclusive(path: Path | str, *, mode: int = 0o755) -> Path:
    absolute = _absolute(path)
    _reject_symlink_chain(absolute.parent)
    try:
        os.mkdir(absolute, mode)
    except FileExistsError as exc:
        raise AuthorityError("NO_OVERWRITE_COLLISION", f"directory already exists: {absolute}") from exc
    return absolute


def _exact_keys(value: object, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise AuthorityError("SCHEMA_DRIFT", f"{label}: exact key set drifted")
    return value


def _identity_map(value: object, label: str) -> Mapping[str, Mapping[str, object]]:
    if not isinstance(value, Mapping) or not value:
        raise AuthorityError("IDENTITY_INVALID", f"{label}: expected non-empty identity map")
    result: dict[str, Mapping[str, object]] = {}
    for role, identity in value.items():
        if type(role) is not str or ROLE_RE.fullmatch(role) is None:
            raise AuthorityError("IDENTITY_INVALID", f"{label}: unsafe role")
        result[role] = validate_detached_identity(identity, f"{label}.{role}")
    return result


def _utc(value: object, label: str) -> str:
    if type(value) is not str:
        raise AuthorityError("TIMESTAMP_INVALID", f"{label}: expected UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthorityError("TIMESTAMP_INVALID", f"{label}: invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise AuthorityError("TIMESTAMP_INVALID", f"{label}: timestamp must carry UTC")
    return value


def _digest_without(record: Mapping[str, object], key: str) -> str:
    payload = dict(record)
    payload.pop(key, None)
    return sha256_bytes(canonical_json(payload))


def _campaign_digest(record: Mapping[str, object]) -> str:
    """Hash a root while normalizing its digest-derived unit namespace."""

    namespace = record.get("unit_namespace")
    if type(namespace) is not str:
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "campaign unit namespace is invalid")

    def normalize(value: object) -> object:
        if isinstance(value, Mapping):
            return {key: "" if key == "campaign_id" else normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, str):
            return value.replace(namespace, "cuts-g1v4-<campaign-token>")
        return value

    return sha256_bytes(canonical_json(normalize(record)))


def audit_attestor_source(raw: bytes) -> dict[str, object]:
    """Statically prove the privileged helper stays inside its read-only role."""

    try:
        source = raw.decode("utf-8", "strict")
        tree = ast.parse(source, filename="<cuts-manager-attestor-v4>", mode="exec")
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise AuthorityError("ATTESTOR_AST_INVALID", f"attestor source is invalid: {exc}") from exc

    allowed_import_roots = {
        "__future__",
        "collections",
        "hashlib",
        "json",
        "os",
        "re",
        "stat",
        "sys",
    }
    banned_roots = {
        "asyncio",
        "ctypes",
        "http",
        "pathlib",
        "shutil",
        "signal",
        "socket",
        "subprocess",
        "tempfile",
        "urllib",
    }
    banned_calls = {
        "__import__",
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "getattr",
        "globals",
        "locals",
        "open",
        "os.chmod",
        "os.chown",
        "os.execv",
        "os.execve",
        "os.fork",
        "os.kill",
        "os.link",
        "os.mkdir",
        "os.mknod",
        "os.openpty",
        "os.popen",
        "os.remove",
        "os.rename",
        "os.replace",
        "os.rmdir",
        "os.spawnv",
        "os.symlink",
        "os.system",
        "os.truncate",
        "os.unlink",
        "os.write",
        "setattr",
        "vars",
    }
    allowed_module_calls = {
        "hashlib.sha256",
        "json.dumps",
        "os.close",
        "os.fsencode",
        "os.fstat",
        "os.lseek",
        "os.open",
        "os.path.isabs",
        "os.read",
        "os.readlink",
        "os.stat",
        "re.compile",
        "stat.S_IMODE",
        "stat.S_ISREG",
        "sys.stdout.write",
    }
    banned_flag_names = {
        "O_APPEND",
        "O_CREAT",
        "O_EXCL",
        "O_RDWR",
        "O_TMPFILE",
        "O_TRUNC",
        "O_WRONLY",
    }
    banned_nodes = (
        ast.AsyncFor,
        ast.AsyncFunctionDef,
        ast.AsyncWith,
        ast.Await,
        ast.Delete,
        ast.Global,
        ast.Lambda,
        ast.Nonlocal,
        ast.Yield,
        ast.YieldFrom,
    )

    def qualified(node: ast.AST) -> str | None:
        parts: list[str] = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if not isinstance(current, ast.Name):
            return None
        parts.append(current.id)
        return ".".join(reversed(parts))

    saw_read_only_flag = False
    for node in ast.walk(tree):
        if isinstance(node, banned_nodes):
            raise AuthorityError("ATTESTOR_POLICY", f"attestor contains banned AST node {type(node).__name__}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in allowed_import_roots or root in banned_roots:
                    raise AuthorityError("ATTESTOR_POLICY", f"attestor import is not allowed: {alias.name}")
        if isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root not in allowed_import_roots or root in banned_roots:
                raise AuthorityError("ATTESTOR_POLICY", f"attestor import is not allowed: {node.module}")
        if isinstance(node, ast.Attribute):
            if node.attr in banned_flag_names:
                raise AuthorityError("ATTESTOR_POLICY", f"attestor uses write-capable open flag {node.attr}")
            if qualified(node) == "os.O_RDONLY":
                saw_read_only_flag = True
        if isinstance(node, ast.Call):
            name = qualified(node.func)
            if name in banned_calls:
                raise AuthorityError("ATTESTOR_POLICY", f"attestor call is not read-only: {name}")
            if name is not None and name.split(".", 1)[0] in banned_roots:
                raise AuthorityError("ATTESTOR_POLICY", f"attestor call root is not allowed: {name}")
            if (
                name is not None
                and name.split(".", 1)[0] in {"hashlib", "json", "os", "re", "stat", "sys"}
                and name not in allowed_module_calls
            ):
                raise AuthorityError("ATTESTOR_POLICY", f"attestor module call is outside the allowlist: {name}")
    if not saw_read_only_flag:
        raise AuthorityError("ATTESTOR_POLICY", "attestor contains no explicit O_RDONLY")
    return {
        "ast_node_count": sum(1 for _ in ast.walk(tree)),
        "policy": ATTESTOR_AUDIT_SCHEMA,
        "source_sha256": sha256_bytes(raw),
        "source_size_bytes": len(raw),
        "status": "PASS",
    }


def _validate_full_tool_identity(value: object, label: str) -> Mapping[str, object]:
    required = {
        "device",
        "inode",
        "mode",
        "mode_octal",
        "path",
        "sha256",
        "size_bytes",
    }
    allowed_key_sets = (required, required | {"requested_path"})
    if not isinstance(value, Mapping) or set(value) not in allowed_key_sets:
        raise AuthorityError("TOOL_IDENTITY_INVALID", f"{label}: tool identity key set drifted")
    if (
        type(value["path"]) is not str
        or not Path(value["path"]).is_absolute()
        or type(value["size_bytes"]) is not int
        or value["size_bytes"] <= 0
        or type(value["sha256"]) is not str
        or SHA256_RE.fullmatch(value["sha256"]) is None
        or type(value["mode"]) is not int
        or value["mode_octal"] != f"{value['mode']:04o}"
        or type(value["device"]) is not int
        or value["device"] < 0
        or type(value["inode"]) is not int
        or value["inode"] <= 0
    ):
        raise AuthorityError("TOOL_IDENTITY_INVALID", f"{label}: malformed tool identity")
    if "requested_path" in value and (
        type(value["requested_path"]) is not str or not Path(value["requested_path"]).is_absolute()
    ):
        raise AuthorityError("TOOL_IDENTITY_INVALID", f"{label}: invalid requested path")
    return value


def validate_manager_epoch(value: object) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "attestation_toolchain",
            "attestor_ast_audit",
            "boot_id",
            "capture_protocol",
            "dbus_unique_owner",
            "manager_executable",
            "manager_features",
            "manager_pid",
            "manager_pid_starttime",
            "manager_version",
            "observation_toolchain",
            "schema",
        },
        "manager epoch",
    )
    if (
        record["schema"] != MANAGER_EPOCH_SCHEMA
        or type(record["boot_id"]) is not str
        or BOOT_ID_RE.fullmatch(record["boot_id"]) is None
        or type(record["dbus_unique_owner"]) is not str
        or DBUS_OWNER_RE.fullmatch(record["dbus_unique_owner"]) is None
        or type(record["manager_pid"]) is not int
        or record["manager_pid"] <= 0
        or type(record["manager_pid_starttime"]) is not int
        or record["manager_pid_starttime"] <= 0
        or type(record["manager_version"]) is not str
        or not record["manager_version"]
        or type(record["manager_features"]) is not str
        or not record["manager_features"]
        or record["capture_protocol"] != "double-unprivileged-join-plus-read-only-sudo-attestation-v4"
    ):
        raise AuthorityError("MANAGER_EPOCH_INVALID", "manager epoch scalar fields are invalid")
    _validate_full_tool_identity(record["manager_executable"], "manager executable")
    observation = _exact_keys(record["observation_toolchain"], {"busctl"}, "observation toolchain")
    _validate_full_tool_identity(observation["busctl"], "observation busctl")
    attestation = _exact_keys(
        record["attestation_toolchain"],
        {"attestor", "python", "sudo"},
        "attestation toolchain",
    )
    for role in ("attestor", "python", "sudo"):
        _validate_full_tool_identity(attestation[role], f"attestation {role}")
    audit = _exact_keys(
        record["attestor_ast_audit"],
        {
            "ast_node_count",
            "policy",
            "source_sha256",
            "source_size_bytes",
            "status",
        },
        "attestor AST audit",
    )
    if (
        audit["policy"] != ATTESTOR_AUDIT_SCHEMA
        or audit["status"] != "PASS"
        or type(audit["ast_node_count"]) is not int
        or audit["ast_node_count"] <= 0
        or audit["source_sha256"] != attestation["attestor"]["sha256"]
        or audit["source_size_bytes"] != attestation["attestor"]["size_bytes"]
    ):
        raise AuthorityError("MANAGER_EPOCH_INVALID", "attestor audit does not bind attestor bytes")
    return record


def same_manager_epoch(left: object, right: object) -> bool:
    """Return true only for complete and byte-equivalent epoch records."""

    try:
        return canonical_json(validate_manager_epoch(left)) == canonical_json(validate_manager_epoch(right))
    except AuthorityError:
        return False


def assemble_manager_epoch(
    *,
    unprivileged_before: Mapping[str, object],
    attestation: Mapping[str, object],
    unprivileged_after: Mapping[str, object],
    observation_toolchain: Mapping[str, object],
    attestation_toolchain: Mapping[str, object],
    attestor_ast_audit: Mapping[str, object],
) -> dict[str, object]:
    """Join one before/privileged/after observation into a strict epoch."""

    state_keys = {
        "boot_id",
        "dbus_unique_owner",
        "manager_features",
        "manager_pid",
        "manager_pid_starttime",
        "manager_version",
    }
    if set(unprivileged_before) != state_keys or dict(unprivileged_before) != dict(unprivileged_after):
        raise AuthorityError("MANAGER_EPOCH_DRIFT", "unprivileged manager state drifted")
    attestation_record = _exact_keys(
        attestation,
        {"manager_executable", "request", "schema", "status"},
        "privileged attestation",
    )
    request = {
        "boot_id": unprivileged_before["boot_id"],
        "dbus_unique_owner": unprivileged_before["dbus_unique_owner"],
        "manager_pid": unprivileged_before["manager_pid"],
        "manager_pid_starttime": unprivileged_before["manager_pid_starttime"],
    }
    if (
        attestation_record["schema"] != ATTESTOR_SCHEMA
        or attestation_record["status"] != "PASS"
        or attestation_record["request"] != request
    ):
        raise AuthorityError("ATTESTATION_JOIN_FAILED", "privileged attestation did not join the manager request")
    result = {
        "attestation_toolchain": dict(attestation_toolchain),
        "attestor_ast_audit": dict(attestor_ast_audit),
        **dict(unprivileged_after),
        "capture_protocol": "double-unprivileged-join-plus-read-only-sudo-attestation-v4",
        "manager_executable": attestation_record["manager_executable"],
        "observation_toolchain": dict(observation_toolchain),
        "schema": MANAGER_EPOCH_SCHEMA,
    }
    validate_manager_epoch(result)
    return result


def validate_manager_epoch_capture_transcript(
    value: object,
    *,
    expected_epoch: Mapping[str, object] | None = None,
) -> Mapping[str, Any]:
    """Strictly replay both live before/attestor/after observation rounds.

    The transcript preserves the evidence intentionally omitted from the
    stable manager-epoch schema: both unprivileged observations, the exact
    privileged response, the selected toolchain, and the complete attestor
    argv/stdout join.  It is therefore suitable for phase-local replay without
    changing the campaign's manager-epoch schema.
    """

    transcript = _exact_keys(
        value,
        {"capture_protocol", "rounds", "schema"},
        "manager epoch capture transcript",
    )
    if (
        transcript["schema"] != MANAGER_EPOCH_TRANSCRIPT_SCHEMA
        or transcript["capture_protocol"] != "two-round-before-read-only-attestor-after-transcript-v4"
        or not isinstance(transcript["rounds"], list)
        or len(transcript["rounds"]) != 2
    ):
        raise AuthorityError(
            "MANAGER_TRANSCRIPT_INVALID",
            "manager epoch capture transcript framing drifted",
        )
    replayed_epochs: list[dict[str, object]] = []
    for expected_index, untyped_round in enumerate(transcript["rounds"], start=1):
        round_record = _exact_keys(
            untyped_round,
            {
                "attestation_toolchain",
                "attestor_ast_audit",
                "attestor_invocation",
                "observation_toolchain",
                "observation_finished_monotonic_ns",
                "observation_started_monotonic_ns",
                "privileged_attestation",
                "round_index",
                "unprivileged_after",
                "unprivileged_before",
            },
            f"manager epoch transcript round {expected_index}",
        )
        if type(round_record["round_index"]) is not int or round_record["round_index"] != expected_index:
            raise AuthorityError(
                "MANAGER_TRANSCRIPT_INVALID",
                "manager epoch transcript round order drifted",
            )
        if (
            type(round_record["observation_started_monotonic_ns"]) is not int
            or type(round_record["observation_finished_monotonic_ns"]) is not int
            or round_record["observation_started_monotonic_ns"] <= 0
            or round_record["observation_finished_monotonic_ns"] <= round_record["observation_started_monotonic_ns"]
        ):
            raise AuthorityError(
                "MANAGER_TRANSCRIPT_INVALID",
                "manager epoch transcript observation clock is invalid",
            )
        if (
            expected_index > 1
            and round_record["observation_started_monotonic_ns"]
            <= transcript["rounds"][expected_index - 2]["observation_finished_monotonic_ns"]
        ):
            raise AuthorityError(
                "MANAGER_TRANSCRIPT_INVALID",
                "manager epoch transcript rounds overlap or are out of order",
            )
        before = _exact_keys(
            round_record["unprivileged_before"],
            {
                "boot_id",
                "dbus_unique_owner",
                "manager_features",
                "manager_pid",
                "manager_pid_starttime",
                "manager_version",
            },
            f"manager epoch transcript round {expected_index} before",
        )
        after = _exact_keys(
            round_record["unprivileged_after"],
            set(before),
            f"manager epoch transcript round {expected_index} after",
        )
        observation = _exact_keys(
            round_record["observation_toolchain"],
            {"busctl"},
            f"manager epoch transcript round {expected_index} observation tools",
        )
        _validate_full_tool_identity(
            observation["busctl"],
            f"manager epoch transcript round {expected_index} busctl",
        )
        attestation_tools = _exact_keys(
            round_record["attestation_toolchain"],
            {"attestor", "python", "sudo"},
            f"manager epoch transcript round {expected_index} attestation tools",
        )
        for role in ("attestor", "python", "sudo"):
            _validate_full_tool_identity(
                attestation_tools[role],
                f"manager epoch transcript round {expected_index} {role}",
            )
        audit = _exact_keys(
            round_record["attestor_ast_audit"],
            {
                "ast_node_count",
                "policy",
                "source_sha256",
                "source_size_bytes",
                "status",
            },
            f"manager epoch transcript round {expected_index} attestor audit",
        )
        invocation = _exact_keys(
            round_record["attestor_invocation"],
            {
                "argv",
                "exit_code",
                "stdin_sha256",
                "stdin_size_bytes",
                "stdout_base64",
            },
            f"manager epoch transcript round {expected_index} attestor invocation",
        )
        expected_argv = [
            str(attestation_tools["sudo"]["path"]),
            "-n",
            "--",
            str(attestation_tools["python"]["path"]),
            "-I",
            "-c",
            _LOADER,
            "--pid",
            str(before["manager_pid"]),
            "--expected-starttime",
            str(before["manager_pid_starttime"]),
            "--expected-boot-id",
            str(before["boot_id"]),
            "--dbus-owner",
            str(before["dbus_unique_owner"]),
        ]
        if (
            invocation["argv"] != expected_argv
            or type(invocation["exit_code"]) is not int
            or invocation["exit_code"] != 0
            or invocation["stdin_sha256"] != attestation_tools["attestor"]["sha256"]
            or invocation["stdin_size_bytes"] != attestation_tools["attestor"]["size_bytes"]
            or type(invocation["stdout_base64"]) is not str
        ):
            raise AuthorityError(
                "MANAGER_TRANSCRIPT_INVALID",
                "attestor invocation does not join the selected request/toolchain",
            )
        try:
            stdout = base64.b64decode(
                invocation["stdout_base64"],
                validate=True,
            )
        except (ValueError, base64.binascii.Error) as exc:
            raise AuthorityError(
                "MANAGER_TRANSCRIPT_INVALID",
                "attestor stdout is not strict base64",
            ) from exc
        attestation = _exact_keys(
            round_record["privileged_attestation"],
            {"manager_executable", "request", "schema", "status"},
            f"manager epoch transcript round {expected_index} attestation",
        )
        if canonical_json(attestation) != stdout:
            raise AuthorityError(
                "MANAGER_TRANSCRIPT_INVALID",
                "attestor stdout bytes do not encode the joined attestation",
            )
        replayed_epochs.append(
            assemble_manager_epoch(
                unprivileged_before=before,
                attestation=attestation,
                unprivileged_after=after,
                observation_toolchain=observation,
                attestation_toolchain=attestation_tools,
                attestor_ast_audit=audit,
            )
        )
    if not same_manager_epoch(replayed_epochs[0], replayed_epochs[1]):
        raise AuthorityError(
            "MANAGER_EPOCH_DRIFT",
            "manager/boot epoch drifted across transcript rounds",
        )
    if expected_epoch is not None and not same_manager_epoch(
        replayed_epochs[1],
        expected_epoch,
    ):
        raise AuthorityError(
            "MANAGER_EPOCH_DRIFT",
            "manager transcript does not replay the expected epoch",
        )
    return transcript


def _read_pseudofile_same_fd(path: Path | str, *, label: str, limit: int) -> bytes:
    """Read one proc/sys pseudo-file without trusting its reported st_size."""

    absolute = _absolute(path)
    descriptor = os.open(
        absolute,
        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise AuthorityError("PSEUDOFILE_INVALID", f"{label} is not regular")
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, min(65536, limit - total + 1))
            if not block:
                break
            total += len(block)
            if total > limit:
                raise AuthorityError("PSEUDOFILE_INVALID", f"{label} exceeded the fixed cap")
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_uid", "st_gid")
    if any(getattr(before, field) != getattr(after, field) for field in fields):
        raise AuthorityError("PSEUDOFILE_RACE", f"{label} changed during same-FD read")
    return b"".join(chunks)


def _read_proc_starttime(pid: int) -> int:
    raw = _read_pseudofile_same_fd(
        f"/proc/{pid}/stat",
        label="manager proc stat",
        limit=1 << 20,
    )
    first_space = raw.find(b" ")
    right_parenthesis = raw.rfind(b")")
    if first_space <= 0 or right_parenthesis <= first_space:
        raise AuthorityError("PROC_STAT_INVALID", "manager proc stat framing is invalid")
    fields = raw[right_parenthesis + 2 :].split()
    if raw[:first_space] != str(pid).encode() or len(fields) < 20:
        raise AuthorityError("PROC_STAT_INVALID", "manager proc stat identity is invalid")
    try:
        starttime = int(fields[19])
    except ValueError as exc:
        raise AuthorityError("PROC_STAT_INVALID", "manager starttime is invalid") from exc
    if starttime <= 0:
        raise AuthorityError("PROC_STAT_INVALID", "manager starttime is not positive")
    return starttime


def _boot_id() -> str:
    raw = _read_pseudofile_same_fd(
        "/proc/sys/kernel/random/boot_id",
        label="kernel boot_id",
        limit=128,
    )
    if not raw.endswith(b"\n"):
        raise AuthorityError("BOOT_ID_INVALID", "boot_id is not newline terminated")
    try:
        value = raw[:-1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise AuthorityError("BOOT_ID_INVALID", "boot_id is not ASCII") from exc
    if BOOT_ID_RE.fullmatch(value) is None:
        raise AuthorityError("BOOT_ID_INVALID", "boot_id syntax is invalid")
    return value


def _busctl_json(busctl_path: str, *arguments: str) -> Mapping[str, object]:
    env = {
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin",
        "SYSTEMD_COLORS": "0",
        "SYSTEMD_PAGER": "cat",
        "SYSTEMD_PAGERSECURE": "1",
        "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
    }
    try:
        completed = subprocess.run(
            [busctl_path, "--user", "--json=short", *arguments],
            check=False,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AuthorityError("BUSCTL_FAILED", f"busctl failed: {exc}") from exc
    if completed.returncode != 0 or completed.stderr or not completed.stdout or len(completed.stdout) > 1 << 20:
        raise AuthorityError("BUSCTL_FAILED", "busctl did not return clean bounded output")
    value = strict_loads(completed.stdout, "busctl output")
    return _exact_keys(value, {"data", "type"}, "busctl envelope")


def _probe_manager(busctl_path: str) -> dict[str, object]:
    owner_reply = _busctl_json(
        busctl_path,
        "call",
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "GetNameOwner",
        "s",
        "org.freedesktop.systemd1",
    )
    if owner_reply["type"] != "s" or not isinstance(owner_reply["data"], list) or len(owner_reply["data"]) != 1:
        raise AuthorityError("DBUS_OWNER_INVALID", "GetNameOwner reply is invalid")
    owner = owner_reply["data"][0]
    if type(owner) is not str or DBUS_OWNER_RE.fullmatch(owner) is None:
        raise AuthorityError("DBUS_OWNER_INVALID", "systemd D-Bus owner is invalid")
    pid_reply = _busctl_json(
        busctl_path,
        "call",
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        "GetConnectionUnixProcessID",
        "s",
        owner,
    )
    if pid_reply["type"] != "u" or not isinstance(pid_reply["data"], list) or len(pid_reply["data"]) != 1:
        raise AuthorityError("DBUS_PID_INVALID", "manager PID reply is invalid")
    pid = pid_reply["data"][0]
    if type(pid) is not int or pid <= 0:
        raise AuthorityError("DBUS_PID_INVALID", "manager PID is invalid")

    def property_value(name: str) -> str:
        reply = _busctl_json(
            busctl_path,
            "get-property",
            owner,
            "/org/freedesktop/systemd1",
            "org.freedesktop.systemd1.Manager",
            name,
        )
        if reply["type"] != "s" or type(reply["data"]) is not str or not reply["data"]:
            raise AuthorityError("DBUS_PROPERTY_INVALID", f"manager property {name} is invalid")
        return reply["data"]

    return {
        "boot_id": _boot_id(),
        "dbus_unique_owner": owner,
        "manager_features": property_value("Features"),
        "manager_pid": pid,
        "manager_pid_starttime": _read_proc_starttime(pid),
        "manager_version": property_value("Version"),
    }


def _invoke_attestor(
    expected: Mapping[str, object],
    *,
    attestor_path: Path | str,
    python_path: Path | str,
    sudo_path: Path | str,
) -> tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]]:
    attestor_raw, attestor_tool = snapshot_tool(attestor_path, size_limit=1 << 20)
    audit = audit_attestor_source(attestor_raw)
    _, python_tool = snapshot_tool(python_path)
    _, sudo_tool = snapshot_tool(sudo_path)
    tools = {
        "attestor": attestor_tool,
        "python": python_tool,
        "sudo": sudo_tool,
    }
    argv = [
        str(sudo_tool["path"]),
        "-n",
        "--",
        str(python_tool["path"]),
        "-I",
        "-c",
        _LOADER,
        "--pid",
        str(expected["manager_pid"]),
        "--expected-starttime",
        str(expected["manager_pid_starttime"]),
        "--expected-boot-id",
        str(expected["boot_id"]),
        "--dbus-owner",
        str(expected["dbus_unique_owner"]),
    ]
    try:
        completed = subprocess.run(
            argv,
            check=False,
            env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin"},
            input=attestor_raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AuthorityError("ATTESTOR_FAILED", f"sudo attestor failed: {exc}") from exc
    if completed.returncode != 0 or completed.stderr or not completed.stdout or len(completed.stdout) > 1 << 20:
        raise AuthorityError("ATTESTOR_FAILED", "sudo attestor did not return clean bounded PASS output")
    after_attestor_raw, after_attestor = snapshot_tool(attestor_path, size_limit=1 << 20)
    _, after_python = snapshot_tool(python_path)
    _, after_sudo = snapshot_tool(sudo_path)
    if (
        after_attestor_raw != attestor_raw
        or after_attestor != attestor_tool
        or after_python != python_tool
        or after_sudo != sudo_tool
    ):
        raise AuthorityError("ATTESTOR_TOOL_DRIFT", "attestor toolchain drifted across sudo")
    response = strict_loads(completed.stdout, "privileged attestor output")
    if canonical_json(response) != completed.stdout:
        raise AuthorityError("ATTESTOR_OUTPUT_INVALID", "attestor output is not canonical JSON")
    evidence = {
        "argv": argv,
        "exit_code": completed.returncode,
        "stdin_sha256": sha256_bytes(attestor_raw),
        "stdin_size_bytes": len(attestor_raw),
        "stdout_base64": base64.b64encode(completed.stdout).decode("ascii"),
    }
    return (
        _exact_keys(
            response,
            {"manager_executable", "request", "schema", "status"},
            "attestor response",
        ),
        tools,
        {"audit": audit, "invocation": evidence},
    )


def capture_manager_epoch_with_transcript(
    *,
    attestor_path: Path | str,
    busctl_path: Path | str = "/usr/bin/busctl",
    python_path: Path | str = "/usr/bin/python3.14",
    sudo_path: Path | str = "/usr/bin/sudo",
    probe: Callable[[str], Mapping[str, object]] | None = None,
    invoke: Callable[
        [Mapping[str, object]],
        tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]],
    ]
    | None = None,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> dict[str, object]:
    """Double-capture one cuts-local manager/boot epoch and its raw transcript."""

    _, busctl_tool = snapshot_tool(busctl_path)
    effective_busctl = str(busctl_tool["path"])
    probe_fn = probe or _probe_manager

    def invoke_default(
        expected: Mapping[str, object],
    ) -> tuple[
        Mapping[str, object],
        Mapping[str, object],
        Mapping[str, object],
    ]:
        return _invoke_attestor(
            expected,
            attestor_path=attestor_path,
            python_path=python_path,
            sudo_path=sudo_path,
        )

    invoke_fn = invoke or invoke_default
    captures: list[dict[str, object]] = []
    rounds: list[dict[str, object]] = []
    for round_index in range(1, 3):
        observation_started_monotonic_ns = monotonic_ns()
        before = dict(probe_fn(effective_busctl))
        attestation, attestation_tools, attestation_evidence = invoke_fn(before)
        after = dict(probe_fn(effective_busctl))
        observation_finished_monotonic_ns = monotonic_ns()
        _, busctl_after = snapshot_tool(busctl_path)
        if busctl_after != busctl_tool:
            raise AuthorityError("MANAGER_EPOCH_DRIFT", "busctl identity drifted during capture")
        evidence = _exact_keys(
            attestation_evidence,
            {"audit", "invocation"},
            "attestation evidence",
        )
        audit = evidence["audit"]
        epoch = assemble_manager_epoch(
            unprivileged_before=before,
            attestation=attestation,
            unprivileged_after=after,
            observation_toolchain={"busctl": busctl_tool},
            attestation_toolchain=attestation_tools,
            attestor_ast_audit=audit,
        )
        captures.append(epoch)
        rounds.append(
            {
                "attestation_toolchain": dict(attestation_tools),
                "attestor_ast_audit": dict(audit),
                "attestor_invocation": dict(evidence["invocation"]),
                "observation_toolchain": {"busctl": busctl_tool},
                "observation_finished_monotonic_ns": observation_finished_monotonic_ns,
                "observation_started_monotonic_ns": observation_started_monotonic_ns,
                "privileged_attestation": dict(attestation),
                "round_index": round_index,
                "unprivileged_after": after,
                "unprivileged_before": before,
            }
        )
    if not same_manager_epoch(captures[0], captures[1]):
        raise AuthorityError("MANAGER_EPOCH_DRIFT", "manager/boot epoch drifted across double capture")
    transcript = {
        "capture_protocol": "two-round-before-read-only-attestor-after-transcript-v4",
        "rounds": rounds,
        "schema": MANAGER_EPOCH_TRANSCRIPT_SCHEMA,
    }
    validate_manager_epoch_capture_transcript(
        transcript,
        expected_epoch=captures[1],
    )
    return {
        "manager_epoch": captures[1],
        "transcript": transcript,
    }


def capture_manager_epoch(
    *,
    attestor_path: Path | str,
    busctl_path: Path | str = "/usr/bin/busctl",
    python_path: Path | str = "/usr/bin/python3.14",
    sudo_path: Path | str = "/usr/bin/sudo",
    probe: Callable[[str], Mapping[str, object]] | None = None,
    invoke: Callable[
        [Mapping[str, object]],
        tuple[Mapping[str, object], Mapping[str, object], Mapping[str, object]],
    ]
    | None = None,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> dict[str, object]:
    """Compatibility API returning only the stable manager-epoch record."""

    captured = capture_manager_epoch_with_transcript(
        attestor_path=attestor_path,
        busctl_path=busctl_path,
        python_path=python_path,
        sudo_path=sudo_path,
        probe=probe,
        invoke=invoke,
        monotonic_ns=monotonic_ns,
    )
    return dict(captured["manager_epoch"])


def _validate_role(role: str) -> None:
    if ROLE_RE.fullmatch(role) is None or role in {"SHA256SUMS", "package-manifest.json"} or "/" in role:
        raise AuthorityError("SOURCE_ROLE_INVALID", f"unsafe package role: {role!r}")


def build_package(
    package_dir: Path | str,
    sources: Sequence[SourceSpec],
    *,
    repository_head: str,
    run_nonce: str,
    manager_epoch: Mapping[str, object],
) -> dict[str, object]:
    """Create and seal a campaign package in one previously absent directory."""

    if GIT_SHA_RE.fullmatch(repository_head) is None:
        raise AuthorityError("HEAD_INVALID", "repository HEAD must be a lowercase 40-hex SHA")
    if not run_nonce or len(run_nonce) > 128:
        raise AuthorityError("RUN_NONCE_INVALID", "run nonce must contain 1..128 characters")
    validate_manager_epoch(manager_epoch)
    if not sources:
        raise AuthorityError("SOURCE_SET_INVALID", "package source set is empty")
    roles = [spec.role for spec in sources]
    for role in roles:
        _validate_role(role)
    if len(set(roles)) != len(roles):
        raise AuthorityError("SOURCE_SET_INVALID", "package source roles are not unique")

    output = mkdir_exclusive(package_dir)
    payload_dir = mkdir_exclusive(output / "payload")
    snapshots = {spec.role: snapshot_regular(spec.path) for spec in sources}
    records: list[dict[str, object]] = []
    members: list[dict[str, object]] = []
    for spec in sorted(sources, key=lambda item: item.role):
        snapshot = snapshots[spec.role]
        if spec.parse_json:
            strict_loads(snapshot.data, f"package source {spec.role}")
        package_path = payload_dir / spec.role
        identity = write_exclusive(package_path, snapshot.data)
        members.append(
            {
                "path": f"payload/{spec.role}",
                "sha256": identity["sha256"],
                "size_bytes": identity["size_bytes"],
            }
        )
        records.append(
            {
                "package_path": f"payload/{spec.role}",
                "parse_json": spec.parse_json,
                "role": spec.role,
                "source_identity": full_identity(snapshot),
            }
        )

    manifest = {
        "authorization_semantics": "byte qualification only; package PASS cannot launch any child",
        "external_sources": records,
        "manager_epoch": dict(manager_epoch),
        "package_members": members,
        "repository_head": repository_head,
        "run_nonce": run_nonce,
        "schema": PACKAGE_MANIFEST_SCHEMA,
        "seal_contract": {
            "package_id": "sha256(SHA256SUMS exact bytes)",
            "sha256sums_domain": "all regular files below package except SHA256SUMS",
            "writes_after_seal": "forbidden",
        },
    }
    manifest_identity = write_exclusive(output / "package-manifest.json", canonical_json(manifest))
    files = _scan_regular_tree(output)
    expected = {member["path"] for member in members} | {"package-manifest.json"}
    if set(files) != expected:
        raise AuthorityError("PACKAGE_MEMBER_DRIFT", "pre-seal package member set drifted")
    sha_raw = "".join(f"{files[name].sha256}  {name}\n" for name in sorted(files)).encode("ascii")
    seal_identity = write_exclusive(output / "SHA256SUMS", sha_raw)
    result = {
        "manifest_identity": manifest_identity,
        "package_dir": str(output),
        "package_id": seal_identity["sha256"],
        "schema": PACKAGE_SCHEMA,
        "seal_identity": seal_identity,
        "status": "SEALED",
    }
    verify_package(output, expected_manager_epoch=manager_epoch, replay_external=True)
    return result


def _scan_regular_tree(root: Path | str) -> dict[str, Snapshot]:
    absolute = _absolute(root)
    _reject_symlink_chain(absolute)
    if not absolute.is_dir():
        raise AuthorityError("TREE_INVALID", f"tree root is not a directory: {absolute}")
    result: dict[str, Snapshot] = {}
    for path in sorted(absolute.rglob("*")):
        mode = os.lstat(path).st_mode
        if stat.S_ISLNK(mode):
            raise AuthorityError("SYMLINK_REJECTED", f"symlink in tree: {path}")
        if stat.S_ISREG(mode):
            result[path.relative_to(absolute).as_posix()] = snapshot_regular(path)
        elif not stat.S_ISDIR(mode):
            raise AuthorityError("TREE_INVALID", f"non-regular object in tree: {path}")
    return result


def _safe_checksum_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or value == "SHA256SUMS"
        or path.is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise AuthorityError("SEAL_INVALID", f"unsafe checksum path: {value!r}")
    return path.as_posix()


def _parse_sha256sums(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise AuthorityError("SEAL_INVALID", "SHA256SUMS is not ASCII") from exc
    if not lines or not raw.endswith(b"\n"):
        raise AuthorityError("SEAL_INVALID", "SHA256SUMS must be nonempty and newline terminated")
    result: dict[str, str] = {}
    for line in lines:
        if len(line) < 67 or line[64:66] != "  ":
            raise AuthorityError("SEAL_INVALID", "malformed SHA256SUMS line")
        digest = line[:64]
        relative = _safe_checksum_path(line[66:])
        if SHA256_RE.fullmatch(digest) is None or relative in result:
            raise AuthorityError("SEAL_INVALID", "invalid or duplicate checksum entry")
        result[relative] = digest
    return result


def verify_package(
    package_dir: Path | str,
    *,
    expected_manager_epoch: Mapping[str, object],
    replay_external: bool,
) -> dict[str, object]:
    """Independently replay one sealed package."""

    validate_manager_epoch(expected_manager_epoch)
    files = _scan_regular_tree(package_dir)
    required = {"package-manifest.json", "SHA256SUMS"}
    if not required <= set(files):
        raise AuthorityError("PACKAGE_INCOMPLETE", "package lacks manifest or seal")
    entries = _parse_sha256sums(files["SHA256SUMS"].data)
    covered = set(files) - {"SHA256SUMS"}
    if set(entries) != covered or any(entries[name] != files[name].sha256 for name in covered):
        raise AuthorityError("PACKAGE_SEAL_DRIFT", "package seal member set or digest drifted")
    manifest_value = strict_loads(files["package-manifest.json"].data, "package manifest")
    manifest = _exact_keys(
        manifest_value,
        {
            "authorization_semantics",
            "external_sources",
            "manager_epoch",
            "package_members",
            "repository_head",
            "run_nonce",
            "schema",
            "seal_contract",
        },
        "package manifest",
    )
    if (
        manifest["schema"] != PACKAGE_MANIFEST_SCHEMA
        or manifest["authorization_semantics"] != "byte qualification only; package PASS cannot launch any child"
        or not same_manager_epoch(manifest["manager_epoch"], expected_manager_epoch)
    ):
        raise AuthorityError("PACKAGE_MANIFEST_DRIFT", "package manifest semantics drifted")
    member_records = manifest["package_members"]
    if not isinstance(member_records, list):
        raise AuthorityError("PACKAGE_MANIFEST_DRIFT", "package member records are invalid")
    expected_members: dict[str, tuple[object, object]] = {}
    for item in member_records:
        record = _exact_keys(item, {"path", "sha256", "size_bytes"}, "package member")
        path = _safe_checksum_path(record["path"])
        if path in expected_members:
            raise AuthorityError("PACKAGE_MANIFEST_DRIFT", "duplicate package member record")
        expected_members[path] = (record["sha256"], record["size_bytes"])
    payload_names = covered - {"package-manifest.json"}
    if set(expected_members) != payload_names:
        raise AuthorityError("PACKAGE_MANIFEST_DRIFT", "manifest payload member set drifted")
    for path, (digest, size) in expected_members.items():
        if files[path].sha256 != digest or files[path].size != size:
            raise AuthorityError("PACKAGE_MANIFEST_DRIFT", "manifest payload identity drifted")
    sources = manifest["external_sources"]
    if not isinstance(sources, list) or len(sources) != len(expected_members):
        raise AuthorityError("PACKAGE_MANIFEST_DRIFT", "external source set drifted")
    if replay_external:
        for item in sources:
            record = _exact_keys(
                item,
                {"package_path", "parse_json", "role", "source_identity"},
                "external source",
            )
            source_identity = _validate_full_tool_identity(record["source_identity"], "external source identity")
            current = snapshot_regular(source_identity["path"])
            if full_identity(current) != source_identity:
                raise AuthorityError("STALE_INPUT", f"external source drifted: {source_identity['path']}")
            if record["parse_json"] is True:
                strict_loads(current.data, f"external source {record['role']}")
            elif record["parse_json"] is not False:
                raise AuthorityError("PACKAGE_MANIFEST_DRIFT", "parse_json is not exact bool")
            package_path = record["package_path"]
            if package_path not in files or files[package_path].data != current.data:
                raise AuthorityError("PACKAGE_MANIFEST_DRIFT", "external source and payload differ")
    return {
        "manifest_identity": detached_identity(files["package-manifest.json"]),
        "package_id": files["SHA256SUMS"].sha256,
        "seal_identity": detached_identity(files["SHA256SUMS"]),
        "status": "PASS",
    }


def _future_ab16_slots(campaign_dir: Path, namespace: str) -> list[dict[str, object]]:
    slots: list[dict[str, object]] = []
    for configuration in AB16_CONFIGURATIONS:
        for order in AB16_ORDERS:
            for arm in AB16_ARMS:
                slot = f"{configuration}-{order}-{arm}"
                attempt = campaign_dir / "prospective-ab16" / "arms" / slot
                slots.append(
                    {
                        "arm": arm,
                        "attempt_dir": str(attempt),
                        "configuration": configuration,
                        "order": order,
                        "slot": slot,
                        "unit_name": f"{namespace}-ab16-{slot}.service",
                    }
                )
    return slots


def build_campaign_root(
    campaign_dir: Path | str,
    *,
    package: Mapping[str, object],
    repository_head: str,
    run_nonce: str,
    manager_epoch: Mapping[str, object],
    authority_tools: Mapping[str, object],
    strict_inputs: Mapping[str, object],
    created_at_utc: str,
) -> dict[str, object]:
    """Build the immutable root for Gate 1 and the reserved AB16 child."""

    directory = _absolute(campaign_dir)
    if not directory.is_dir():
        raise AuthorityError("CAMPAIGN_DIR_INVALID", "campaign directory must already exist")
    if GIT_SHA_RE.fullmatch(repository_head) is None or not run_nonce or len(run_nonce) > 128:
        raise AuthorityError("CAMPAIGN_IDENTITY_INVALID", "HEAD or run nonce is invalid")
    _utc(created_at_utc, "campaign created_at_utc")
    validate_manager_epoch(manager_epoch)
    tools = _identity_map(authority_tools, "campaign tools")
    inputs = _identity_map(strict_inputs, "campaign inputs")
    package_record = _exact_keys(
        package,
        {
            "manifest_identity",
            "package_dir",
            "package_id",
            "schema",
            "seal_identity",
            "status",
        },
        "campaign package",
    )
    if (
        package_record["schema"] != PACKAGE_SCHEMA
        or package_record["status"] != "SEALED"
        or type(package_record["package_id"]) is not str
        or SHA256_RE.fullmatch(package_record["package_id"]) is None
    ):
        raise AuthorityError("PACKAGE_BINDING_INVALID", "campaign package record is invalid")
    validate_detached_identity(package_record["manifest_identity"], "package manifest identity")
    validate_detached_identity(package_record["seal_identity"], "package seal identity")
    provisional = {
        "authority_ancestors": ["cuts-v4-package"],
        "authority_tools": dict(tools),
        "campaign_closed": False,
        "campaign_id": "",
        "created_at_utc": created_at_utc,
        "manager_epoch": dict(manager_epoch),
        "package": {
            "manifest_identity": dict(package_record["manifest_identity"]),
            "package_dir": package_record["package_dir"],
            "package_id": package_record["package_id"],
            "seal_identity": dict(package_record["seal_identity"]),
        },
        "purpose": CAMPAIGN_PURPOSE,
        "repository_head": repository_head,
        "run_nonce": run_nonce,
        "schema_version": CAMPAIGN_ROOT_SCHEMA,
        "strict_inputs": dict(inputs),
        "unit_namespace": "",
    }
    namespace = "cuts-g1v4-000000000000"
    gate1_dir = directory / "gate1-v4"
    positive_dir = gate1_dir / "positive-control-common"
    positive_common_dir = positive_dir / "common-prestate"
    positive_bindings_dir = positive_dir / "bindings"
    positive_arms_dir = positive_dir / "arms"
    positive_exports_dir = positive_dir / "builder-exports"
    gate_units: dict[str, dict[str, object]] = {}
    for slot in GATE1_SLOTS:
        attempt = gate1_dir / "units" / slot
        gate_units[slot] = {
            "attempt_dir": str(attempt),
            "contract_profile": "synthetic" if slot.startswith("q-") else "formal",
            "epoch_checkpoint_paths": {
                phase: str(attempt / "authority" / f"manager-epoch-{phase}.json")
                for phase in (
                    "prelaunch",
                    "preterminal",
                    "terminal",
                    "cleanup",
                    "detached-replay",
                )
            },
            "raw_dir": str(attempt / "raw"),
            "result_path": str(attempt / "result.json"),
            "slot": slot,
            "terminal_dir": str(attempt / "terminal"),
            "unit_name": f"{namespace}-{slot}.service",
        }
    topology = {
        "gate1_v4": {
            "continuation_path": str(gate1_dir / "continuation-authorization-a001.json"),
            "gate_admission_epoch_path": str(gate1_dir / "authority" / "manager-epoch-gate-admission.json"),
            "gate_admission_epoch_schema": GATE_ADMISSION_EPOCH_SCHEMA,
            "gate_path": str(gate1_dir / "gate-a001.json"),
            "order": 1,
            "positive_common_dir": str(positive_dir),
            "positive_control": {
                "arithmetic_receipt_path": str(positive_dir / "independent-arithmetic-receipt.json"),
                "arm_dirs": {
                    "control": str(positive_arms_dir / "control"),
                    "treatment": str(positive_arms_dir / "treatment"),
                },
                "binding_paths": {
                    "control": str(positive_bindings_dir / "control.json"),
                    "treatment": str(positive_bindings_dir / "treatment.json"),
                },
                "binding_seal_path": str(positive_bindings_dir / "bindings-seal.json"),
                "builder_export_dirs": {
                    arm: str(positive_exports_dir / arm) for arm in ("common", "control", "treatment")
                },
                "common_artifact_paths": {
                    "candidates": str(positive_common_dir / "candidates.json"),
                    "incumbent": str(positive_common_dir / "incumbent.json"),
                    "mandatory": str(positive_common_dir / "mandatory.json"),
                    "pre_model": str(positive_common_dir / "pre-injection-model.pb"),
                    "response": str(positive_common_dir / "pre-injection-response.pb"),
                    "selector_contract": str(positive_common_dir / "selector-contract.json"),
                    "solution": str(positive_common_dir / "solution.json"),
                },
                "common_manifest_path": str(positive_common_dir / "manifest.json"),
                "root_dir": str(positive_dir),
                "selection_path": str(positive_dir / "selection.json"),
            },
            "selection_path": str(gate1_dir / "selection-a001.json"),
            "suite": "gate1-v4",
            "units": gate_units,
        },
        "prospective_ab16": {
            "arm_selection_path": str(directory / "prospective-ab16" / "selection-a001.json"),
            "arms": _future_ab16_slots(directory, namespace),
            "manifest_path": str(directory / "prospective-ab16" / "manifest-a001.json"),
            "order": 2,
            "requires_continuation_schema": CONTINUATION_SCHEMA,
            "suite": "prospective-ab16",
            "terminal_classification_path": str(directory / "prospective-ab16" / "terminal-classification-a001.json"),
        },
    }
    root: dict[str, object] = {
        **provisional,
        "stage_topology": topology,
        "unit_namespace": namespace,
    }
    campaign_id = _campaign_digest(root)
    final_namespace = f"cuts-g1v4-{campaign_id[:12]}"
    root["unit_namespace"] = final_namespace
    for unit in root["stage_topology"]["gate1_v4"]["units"].values():
        unit["unit_name"] = str(unit["unit_name"]).replace(namespace, final_namespace)
    for arm in root["stage_topology"]["prospective_ab16"]["arms"]:
        arm["unit_name"] = str(arm["unit_name"]).replace(namespace, final_namespace)
    root["campaign_id"] = campaign_id
    validate_campaign_root(root, campaign_dir=directory)
    return root


def validate_campaign_root(
    value: object,
    *,
    campaign_dir: Path | str | None = None,
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "authority_ancestors",
            "authority_tools",
            "campaign_closed",
            "campaign_id",
            "created_at_utc",
            "manager_epoch",
            "package",
            "purpose",
            "repository_head",
            "run_nonce",
            "schema_version",
            "stage_topology",
            "strict_inputs",
            "unit_namespace",
        },
        "campaign root",
    )
    if (
        record["schema_version"] != CAMPAIGN_ROOT_SCHEMA
        or record["purpose"] != CAMPAIGN_PURPOSE
        or record["campaign_closed"] is not False
        or record["authority_ancestors"] != ["cuts-v4-package"]
        or type(record["campaign_id"]) is not str
        or SHA256_RE.fullmatch(record["campaign_id"]) is None
        or type(record["repository_head"]) is not str
        or GIT_SHA_RE.fullmatch(record["repository_head"]) is None
        or type(record["run_nonce"]) is not str
        or not record["run_nonce"]
        or type(record["unit_namespace"]) is not str
        or UNIT_NAMESPACE_RE.fullmatch(record["unit_namespace"]) is None
    ):
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "campaign root scalar semantics drifted")
    _utc(record["created_at_utc"], "campaign created_at_utc")
    validate_manager_epoch(record["manager_epoch"])
    _identity_map(record["authority_tools"], "campaign tools")
    _identity_map(record["strict_inputs"], "campaign inputs")
    package = _exact_keys(
        record["package"],
        {"manifest_identity", "package_dir", "package_id", "seal_identity"},
        "campaign package binding",
    )
    validate_detached_identity(package["manifest_identity"], "campaign package manifest")
    validate_detached_identity(package["seal_identity"], "campaign package seal")
    if (
        type(package["package_dir"]) is not str
        or not Path(package["package_dir"]).is_absolute()
        or type(package["package_id"]) is not str
        or SHA256_RE.fullmatch(package["package_id"]) is None
        or package["seal_identity"]["sha256"] != package["package_id"]
    ):
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "campaign package binding is invalid")
    if _campaign_digest(record) != record["campaign_id"]:
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "campaign_id digest mismatch")
    if record["unit_namespace"] != f"cuts-g1v4-{record['campaign_id'][:12]}":
        raise AuthorityError("CAMPAIGN_ROOT_INVALID", "unit namespace does not derive from campaign_id")
    topology = _exact_keys(
        record["stage_topology"],
        {"gate1_v4", "prospective_ab16"},
        "campaign topology",
    )
    gate = _exact_keys(
        topology["gate1_v4"],
        {
            "continuation_path",
            "gate_admission_epoch_path",
            "gate_admission_epoch_schema",
            "gate_path",
            "order",
            "positive_common_dir",
            "positive_control",
            "selection_path",
            "suite",
            "units",
        },
        "Gate 1 topology",
    )
    if gate["order"] != 1 or gate["suite"] != "gate1-v4":
        raise AuthorityError("TOPOLOGY_INVALID", "Gate 1 ordering drifted")
    gate_admission_path = Path(gate["gate_admission_epoch_path"])
    expected_gate_admission_path = (
        Path(gate["selection_path"]).parent / "authority" / "manager-epoch-gate-admission.json"
    )
    if (
        gate["gate_admission_epoch_schema"] != GATE_ADMISSION_EPOCH_SCHEMA
        or gate_admission_path != expected_gate_admission_path
        or not gate_admission_path.is_absolute()
    ):
        raise AuthorityError(
            "TOPOLOGY_INVALID",
            "Gate 1 admission manager-epoch topology drifted",
        )
    positive_root = Path(gate["positive_common_dir"])
    positive = _exact_keys(
        gate["positive_control"],
        {
            "arithmetic_receipt_path",
            "arm_dirs",
            "binding_paths",
            "binding_seal_path",
            "builder_export_dirs",
            "common_artifact_paths",
            "common_manifest_path",
            "root_dir",
            "selection_path",
        },
        "Gate 1 positive-control topology",
    )
    common_dir = positive_root / "common-prestate"
    bindings_dir = positive_root / "bindings"
    arms_dir = positive_root / "arms"
    exports_dir = positive_root / "builder-exports"
    artifact_names = {
        "candidates": "candidates.json",
        "incumbent": "incumbent.json",
        "mandatory": "mandatory.json",
        "pre_model": "pre-injection-model.pb",
        "response": "pre-injection-response.pb",
        "selector_contract": "selector-contract.json",
        "solution": "solution.json",
    }
    artifacts = _exact_keys(
        positive["common_artifact_paths"],
        set(artifact_names),
        "Gate 1 positive common artifacts",
    )
    binding_paths = _exact_keys(
        positive["binding_paths"],
        {"control", "treatment"},
        "Gate 1 positive binding paths",
    )
    arm_dirs = _exact_keys(
        positive["arm_dirs"],
        {"control", "treatment"},
        "Gate 1 positive arm directories",
    )
    builder_export_dirs = _exact_keys(
        positive["builder_export_dirs"],
        {"common", "control", "treatment"},
        "Gate 1 positive builder export directories",
    )
    if (
        not positive_root.is_absolute()
        or Path(positive["root_dir"]) != positive_root
        or Path(positive["selection_path"]) != positive_root / "selection.json"
        or Path(positive["common_manifest_path"]) != common_dir / "manifest.json"
        or Path(positive["binding_seal_path"]) != bindings_dir / "bindings-seal.json"
        or Path(positive["arithmetic_receipt_path"]) != positive_root / "independent-arithmetic-receipt.json"
        or any(Path(artifacts[role]) != common_dir / filename for role, filename in artifact_names.items())
        or any(Path(binding_paths[arm]) != bindings_dir / f"{arm}.json" for arm in ("control", "treatment"))
        or any(Path(arm_dirs[arm]) != arms_dir / arm for arm in ("control", "treatment"))
        or any(Path(builder_export_dirs[arm]) != exports_dir / arm for arm in ("common", "control", "treatment"))
    ):
        raise AuthorityError(
            "TOPOLOGY_INVALID",
            "Gate 1 positive-control preregistered paths drifted",
        )
    units = _exact_keys(gate["units"], set(GATE1_SLOTS), "Gate 1 units")
    namespace = record["unit_namespace"]
    paths: set[str] = set()
    unit_names: set[str] = set()
    for slot in GATE1_SLOTS:
        unit = _exact_keys(
            units[slot],
            {
                "attempt_dir",
                "contract_profile",
                "epoch_checkpoint_paths",
                "raw_dir",
                "result_path",
                "slot",
                "terminal_dir",
                "unit_name",
            },
            f"Gate 1 unit {slot}",
        )
        attempt = Path(unit["attempt_dir"])
        if (
            unit["slot"] != slot
            or unit["contract_profile"] != ("synthetic" if slot.startswith("q-") else "formal")
            or unit["unit_name"] != f"{namespace}-{slot}.service"
            or not attempt.is_absolute()
            or Path(unit["raw_dir"]) != attempt / "raw"
            or Path(unit["terminal_dir"]) != attempt / "terminal"
            or Path(unit["result_path"]) != attempt / "result.json"
        ):
            raise AuthorityError("TOPOLOGY_INVALID", f"Gate 1 unit {slot} drifted")
        checkpoints = _exact_keys(
            unit["epoch_checkpoint_paths"],
            {
                "cleanup",
                "detached-replay",
                "prelaunch",
                "preterminal",
                "terminal",
            },
            f"Gate 1 unit {slot} manager epoch checkpoints",
        )
        for phase, checkpoint_path in checkpoints.items():
            if Path(checkpoint_path) != (attempt / "authority" / f"manager-epoch-{phase}.json"):
                raise AuthorityError(
                    "TOPOLOGY_INVALID",
                    f"Gate 1 unit {slot} {phase} manager epoch path drifted",
                )
        paths.add(str(attempt))
        unit_names.add(unit["unit_name"])
    if len(paths) != 4 or len(unit_names) != 4:
        raise AuthorityError("TOPOLOGY_INVALID", "Gate 1 unit paths/names are not unique")
    prospective = _exact_keys(
        topology["prospective_ab16"],
        {
            "arm_selection_path",
            "arms",
            "manifest_path",
            "order",
            "requires_continuation_schema",
            "suite",
            "terminal_classification_path",
        },
        "AB16 topology",
    )
    if (
        prospective["order"] != 2
        or prospective["suite"] != "prospective-ab16"
        or prospective["requires_continuation_schema"] != CONTINUATION_SCHEMA
        or not isinstance(prospective["arms"], list)
        or len(prospective["arms"]) != 16
    ):
        raise AuthorityError("TOPOLOGY_INVALID", "prospective AB16 stage drifted")
    expected_triplets = {
        (configuration, order, arm)
        for configuration in AB16_CONFIGURATIONS
        for order in AB16_ORDERS
        for arm in AB16_ARMS
    }
    actual_triplets: set[tuple[object, object, object]] = set()
    future_names: set[str] = set()
    for item in prospective["arms"]:
        arm = _exact_keys(
            item,
            {"arm", "attempt_dir", "configuration", "order", "slot", "unit_name"},
            "AB16 arm",
        )
        triplet = (arm["configuration"], arm["order"], arm["arm"])
        actual_triplets.add(triplet)
        expected_slot = f"{arm['configuration']}-{arm['order']}-{arm['arm']}"
        if (
            arm["slot"] != expected_slot
            or arm["unit_name"] != f"{namespace}-ab16-{expected_slot}.service"
            or not Path(arm["attempt_dir"]).is_absolute()
        ):
            raise AuthorityError("TOPOLOGY_INVALID", "AB16 arm slot/name drifted")
        future_names.add(arm["unit_name"])
    if actual_triplets != expected_triplets or len(future_names) != 16:
        raise AuthorityError("TOPOLOGY_INVALID", "AB16 arm coverage or uniqueness drifted")
    if campaign_dir is not None:
        directory = _absolute(campaign_dir)
        for field in (
            "selection_path",
            "gate_path",
            "continuation_path",
            "gate_admission_epoch_path",
            "positive_common_dir",
        ):
            if not _absolute(gate[field]).is_relative_to(directory):
                raise AuthorityError("TOPOLOGY_INVALID", "Gate 1 path escaped campaign root")
        for field in ("manifest_path", "arm_selection_path", "terminal_classification_path"):
            if not _absolute(prospective[field]).is_relative_to(directory):
                raise AuthorityError("TOPOLOGY_INVALID", "AB16 path escaped campaign root")
        for item in prospective["arms"]:
            if not _absolute(item["attempt_dir"]).is_relative_to(directory):
                raise AuthorityError("TOPOLOGY_INVALID", "AB16 attempt escaped campaign root")
    return record


def write_campaign_root(
    campaign_dir: Path | str,
    root: Mapping[str, object],
) -> dict[str, object]:
    directory = _absolute(campaign_dir)
    validate_campaign_root(root, campaign_dir=directory)
    package_replay = verify_package(
        root["package"]["package_dir"],
        expected_manager_epoch=root["manager_epoch"],
        replay_external=True,
    )
    expected_package = {
        "manifest_identity": root["package"]["manifest_identity"],
        "package_id": root["package"]["package_id"],
        "seal_identity": root["package"]["seal_identity"],
        "status": "PASS",
    }
    if package_replay != expected_package:
        raise AuthorityError("PACKAGE_BINDING_INVALID", "campaign package replay does not join root")
    for group in ("authority_tools", "strict_inputs"):
        for role, identity in root[group].items():
            replay_detached_identity(identity, f"campaign {group}.{role}")
    root_path = directory / "campaign-root.json"
    reserved = reserved_child_paths(root)
    if root_path.exists() or root_path.is_symlink() or any(path.exists() or path.is_symlink() for path in reserved):
        raise AuthorityError("NO_OVERWRITE_COLLISION", "campaign root or a reserved child already exists")
    return write_exclusive(root_path, canonical_json(root))


def reserved_child_paths(root: Mapping[str, object]) -> list[Path]:
    validate_campaign_root(root)
    gate = root["stage_topology"]["gate1_v4"]
    prospective = root["stage_topology"]["prospective_ab16"]
    result = [
        _absolute(gate["selection_path"]),
        _absolute(gate["gate_path"]),
        _absolute(gate["continuation_path"]),
        _absolute(gate["gate_admission_epoch_path"]),
        _absolute(gate["positive_common_dir"]),
        _absolute(prospective["manifest_path"]),
        _absolute(prospective["arm_selection_path"]),
        _absolute(prospective["terminal_classification_path"]),
    ]
    result.extend(_absolute(unit["attempt_dir"]) for unit in gate["units"].values())
    result.extend(_absolute(arm["attempt_dir"]) for arm in prospective["arms"])
    return result


def load_campaign_root(
    path: Path | str,
    expected_identity: Mapping[str, object],
) -> tuple[Mapping[str, Any], dict[str, object]]:
    snapshot = snapshot_regular(path)
    identity = detached_identity(snapshot)
    if identity != validate_detached_identity(expected_identity, "campaign root expected identity"):
        raise AuthorityError("DETACHED_IDENTITY_DRIFT", "campaign root detached identity drifted")
    value = strict_loads(snapshot.data, "campaign root")
    if canonical_json(value) != snapshot.data:
        raise AuthorityError("JSON_NONCANONICAL", "campaign root bytes are not canonical JSON")
    return validate_campaign_root(value, campaign_dir=_absolute(path).parent), identity


def make_gate1_selection(
    root: Mapping[str, object],
    *,
    campaign_root_identity: Mapping[str, object],
    tools: Mapping[str, object],
    inputs: Mapping[str, object],
    created_at_utc: str,
) -> dict[str, object]:
    validate_campaign_root(root)
    validate_detached_identity(campaign_root_identity, "campaign root identity")
    _utc(created_at_utc, "Gate 1 selection created_at_utc")
    selected_units = root["stage_topology"]["gate1_v4"]["units"]
    selection: dict[str, object] = {
        "campaign_id": root["campaign_id"],
        "campaign_root_identity": dict(campaign_root_identity),
        "created_at_utc": created_at_utc,
        "inputs": dict(_identity_map(inputs, "Gate 1 selection inputs")),
        "manager_epoch": dict(root["manager_epoch"]),
        "package_id": root["package"]["package_id"],
        "purpose": GATE1_PURPOSE,
        "repository_head": root["repository_head"],
        "resource_contract": RESOURCE_CONTRACT,
        "run_nonce": root["run_nonce"],
        "schema_version": GATE1_SELECTION_SCHEMA,
        "selection_id": "",
        "tools": dict(_identity_map(tools, "Gate 1 selection tools")),
        "units": selected_units,
    }
    selection["selection_id"] = _digest_without(selection, "selection_id")
    validate_gate1_selection(selection, root=root)
    return selection


def validate_gate1_selection(
    value: object,
    *,
    root: Mapping[str, object] | None = None,
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "campaign_id",
            "campaign_root_identity",
            "created_at_utc",
            "inputs",
            "manager_epoch",
            "package_id",
            "purpose",
            "repository_head",
            "resource_contract",
            "run_nonce",
            "schema_version",
            "selection_id",
            "tools",
            "units",
        },
        "Gate 1 selection",
    )
    if (
        record["schema_version"] != GATE1_SELECTION_SCHEMA
        or record["purpose"] != GATE1_PURPOSE
        or record["resource_contract"] != RESOURCE_CONTRACT
        or type(record["campaign_id"]) is not str
        or SHA256_RE.fullmatch(record["campaign_id"]) is None
        or type(record["package_id"]) is not str
        or SHA256_RE.fullmatch(record["package_id"]) is None
        or type(record["repository_head"]) is not str
        or GIT_SHA_RE.fullmatch(record["repository_head"]) is None
        or type(record["selection_id"]) is not str
        or SHA256_RE.fullmatch(record["selection_id"]) is None
    ):
        raise AuthorityError("SELECTION_INVALID", "Gate 1 selection scalar semantics drifted")
    _utc(record["created_at_utc"], "Gate 1 selection created_at_utc")
    validate_detached_identity(record["campaign_root_identity"], "Gate 1 campaign root identity")
    validate_manager_epoch(record["manager_epoch"])
    tools = _identity_map(record["tools"], "Gate 1 selection tools")
    inputs = _identity_map(record["inputs"], "Gate 1 selection inputs")
    if not REQUIRED_GATE1_TOOL_ROLES <= set(tools):
        raise AuthorityError("SELECTION_INVALID", "Gate 1 selection lacks mandatory tool roles")
    if not REQUIRED_GATE1_INPUT_ROLES <= set(inputs):
        raise AuthorityError("SELECTION_INVALID", "Gate 1 selection lacks mandatory strict inputs")
    units = _exact_keys(record["units"], set(GATE1_SLOTS), "Gate 1 selection units")
    for slot in GATE1_SLOTS:
        _exact_keys(
            units[slot],
            {
                "attempt_dir",
                "contract_profile",
                "epoch_checkpoint_paths",
                "raw_dir",
                "result_path",
                "slot",
                "terminal_dir",
                "unit_name",
            },
            f"Gate 1 selection unit {slot}",
        )
    if _digest_without(record, "selection_id") != record["selection_id"]:
        raise AuthorityError("SELECTION_INVALID", "Gate 1 selection digest drifted")
    if root is not None:
        validate_campaign_root(root)
        expected = {
            "campaign_id": root["campaign_id"],
            "inputs": root["strict_inputs"],
            "manager_epoch": root["manager_epoch"],
            "package_id": root["package"]["package_id"],
            "repository_head": root["repository_head"],
            "run_nonce": root["run_nonce"],
            "tools": root["authority_tools"],
            "units": root["stage_topology"]["gate1_v4"]["units"],
        }
        if any(record[key] != value for key, value in expected.items()):
            raise AuthorityError("SELECTION_INVALID", "Gate 1 selection does not join campaign root")
    return record


def load_gate1_selection_bytes(
    raw: bytes,
    expected_identity: Mapping[str, object],
) -> Mapping[str, Any]:
    """Validate exact detached selection bytes without reopening their path."""

    verify_bytes_identity(raw, expected_identity)
    value = strict_loads(raw, "Gate 1 selection")
    if canonical_json(value) != raw:
        raise AuthorityError("JSON_NONCANONICAL", "Gate 1 selection is not canonical JSON")
    return validate_gate1_selection(value)


def write_gate1_selection(
    campaign_root_path: Path | str,
    campaign_root_identity: Mapping[str, object],
    selection: Mapping[str, object],
) -> dict[str, object]:
    root, _ = load_campaign_root(campaign_root_path, campaign_root_identity)
    validate_gate1_selection(selection, root=root)
    if not same_manager_epoch(selection["manager_epoch"], root["manager_epoch"]):
        raise AuthorityError("MANAGER_EPOCH_DRIFT", "Gate 1 selection epoch drifted")
    package_replay = verify_package(
        root["package"]["package_dir"],
        expected_manager_epoch=root["manager_epoch"],
        replay_external=True,
    )
    if package_replay["package_id"] != root["package"]["package_id"]:
        raise AuthorityError("PACKAGE_BINDING_INVALID", "Gate 1 package replay does not join campaign")
    replay_detached_identity(campaign_root_identity, "campaign root")
    for group in ("tools", "inputs"):
        for role, identity in selection[group].items():
            replay_detached_identity(identity, f"Gate 1 {group}.{role}")
    gate = root["stage_topology"]["gate1_v4"]
    prospective = root["stage_topology"]["prospective_ab16"]
    selection_path = _absolute(gate["selection_path"])
    absent = [
        _absolute(gate["gate_path"]),
        _absolute(gate["continuation_path"]),
        _absolute(gate["gate_admission_epoch_path"]),
        _absolute(gate["positive_common_dir"]),
        _absolute(prospective["manifest_path"]),
        _absolute(prospective["arm_selection_path"]),
        _absolute(prospective["terminal_classification_path"]),
        *(_absolute(unit["attempt_dir"]) for unit in gate["units"].values()),
        *(_absolute(arm["attempt_dir"]) for arm in prospective["arms"]),
    ]
    if any(path.exists() or path.is_symlink() for path in [selection_path, *absent]):
        raise AuthorityError("CHILD_ALREADY_EXISTS", "Gate 1 or prospective child path exists before selection")
    if not selection_path.parent.exists():
        mkdir_exclusive(selection_path.parent)
    return write_exclusive(selection_path, canonical_json(selection))


def replay_gate1_selection(
    campaign_root_path: Path | str,
    campaign_root_identity: Mapping[str, object],
    selection_identity: Mapping[str, object],
    *,
    current_manager_epoch: Mapping[str, object],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    root, _ = load_campaign_root(campaign_root_path, campaign_root_identity)
    if not same_manager_epoch(root["manager_epoch"], current_manager_epoch):
        raise AuthorityError("MANAGER_EPOCH_DRIFT", "current manager epoch does not join campaign")
    path = root["stage_topology"]["gate1_v4"]["selection_path"]
    snapshot = snapshot_regular(path)
    if detached_identity(snapshot) != validate_detached_identity(selection_identity, "Gate 1 selection identity"):
        raise AuthorityError("DETACHED_IDENTITY_DRIFT", "Gate 1 selection bytes drifted")
    selection = load_gate1_selection_bytes(snapshot.data, selection_identity)
    validate_gate1_selection(selection, root=root)
    return root, selection


def validate_gate_admission_epoch_checkpoint(
    value: object,
    *,
    root: Mapping[str, object],
    selection: Mapping[str, object],
) -> Mapping[str, Any]:
    """Validate the independently observed epoch immediately admitting Gate 1."""

    validate_campaign_root(root)
    validate_gate1_selection(selection, root=root)
    record = _exact_keys(
        value,
        {
            "campaign_id",
            "capture_transcript",
            "captured_at_utc",
            "captured_monotonic_ns",
            "manager_epoch",
            "manager_epoch_digest",
            "phase",
            "run_nonce",
            "schema_version",
            "selected_tool_identities",
            "selection_id",
            "transcript_binding_sha256",
            "unit_name",
            "unit_slot",
        },
        "Gate 1 admission manager epoch checkpoint",
    )
    selected_tools = _identity_map(
        record["selected_tool_identities"],
        "Gate 1 admission selected capture tools",
    )
    if set(selected_tools) != set(GATE_ADMISSION_CAPTURE_TOOL_ROLES):
        raise AuthorityError(
            "GATE_ADMISSION_EPOCH_INVALID",
            "Gate 1 admission selected capture tool set drifted",
        )
    expected_selected = {role: selection["tools"][role] for role in GATE_ADMISSION_CAPTURE_TOOL_ROLES}
    if dict(selected_tools) != expected_selected:
        raise AuthorityError(
            "GATE_ADMISSION_EPOCH_INVALID",
            "Gate 1 admission selected capture identities drifted",
        )
    transcript = validate_manager_epoch_capture_transcript(
        record["capture_transcript"],
        expected_epoch=root["manager_epoch"],
    )
    transcript_finished_ns = transcript["rounds"][-1]["observation_finished_monotonic_ns"]
    captured_monotonic_ns = record["captured_monotonic_ns"]
    if type(captured_monotonic_ns) is not int or captured_monotonic_ns <= transcript_finished_ns:
        raise AuthorityError(
            "GATE_ADMISSION_EPOCH_INVALID",
            "Gate 1 admission checkpoint timeline drifted",
        )
    _utc(record["captured_at_utc"], "Gate 1 admission captured_at_utc")
    expected_binding = sha256_bytes(
        canonical_json(
            {
                "campaign_id": root["campaign_id"],
                "capture_transcript": transcript,
                "phase": "gate-admission",
                "run_nonce": root["run_nonce"],
                "selected_tool_identities": dict(selected_tools),
                "selection_id": selection["selection_id"],
                "unit_slot": "gate-admission",
            }
        )
    )
    expected = {
        "campaign_id": root["campaign_id"],
        "manager_epoch_digest": sha256_bytes(canonical_json(root["manager_epoch"])),
        "phase": "gate-admission",
        "run_nonce": root["run_nonce"],
        "schema_version": root["stage_topology"]["gate1_v4"]["gate_admission_epoch_schema"],
        "selection_id": selection["selection_id"],
        "transcript_binding_sha256": expected_binding,
        "unit_name": f"{root['unit_namespace']}-gate-admission.authority",
        "unit_slot": "gate-admission",
    }
    if any(record[key] != expected_value for key, expected_value in expected.items()) or not same_manager_epoch(
        record["manager_epoch"], root["manager_epoch"]
    ):
        raise AuthorityError(
            "GATE_ADMISSION_EPOCH_INVALID",
            "Gate 1 admission checkpoint semantics drifted",
        )
    return record


def _validate_gate_continuation_eligibility(
    gate_result: Mapping[str, object],
    *,
    root: Mapping[str, object],
    gate_admission_epoch_identity: Mapping[str, object],
) -> None:
    expected = {
        "campaign_id": root["campaign_id"],
        "continuation_authorized": False,
        "continuation_eligible": True,
        "gate_admission_epoch_identity": dict(gate_admission_epoch_identity),
        "mechanism_credible": True,
        "organic_arm_launch_authorized": False,
        "status": "CUTS_GATE1_V4_AUTHORITY_COMPLETION_PASS",
    }
    if any(gate_result.get(key) != value for key, value in expected.items()) or not same_manager_epoch(
        gate_result.get("manager_epoch"),
        root["manager_epoch"],
    ):
        raise AuthorityError(
            "CONTINUATION_INVALID",
            "Gate 1 result does not authorize continuation",
        )


def make_continuation_authorization(
    root: Mapping[str, object],
    *,
    campaign_root_identity: Mapping[str, object],
    gate1_selection_identity: Mapping[str, object],
    gate_result: Mapping[str, object],
    gate_result_identity: Mapping[str, object],
    gate_admission_epoch_identity: Mapping[str, object],
    detached_replay_identities: Mapping[str, object],
    current_manager_epoch: Mapping[str, object],
    created_at_utc: str,
) -> dict[str, object]:
    """Build the only Gate 1 PASS continuation token."""

    validate_campaign_root(root)
    _utc(created_at_utc, "continuation created_at_utc")
    if not same_manager_epoch(root["manager_epoch"], current_manager_epoch):
        raise AuthorityError("MANAGER_EPOCH_DRIFT", "continuation epoch does not join campaign")
    validate_detached_identity(campaign_root_identity, "continuation campaign root identity")
    validate_detached_identity(gate1_selection_identity, "continuation selection identity")
    validate_detached_identity(gate_result_identity, "continuation gate result identity")
    validate_detached_identity(
        gate_admission_epoch_identity,
        "continuation Gate 1 admission epoch identity",
    )
    replay_ids = _identity_map(detached_replay_identities, "continuation detached replays")
    if set(replay_ids) != set(GATE1_SLOTS):
        raise AuthorityError("CONTINUATION_INVALID", "continuation requires exactly four unit replays")
    _validate_gate_continuation_eligibility(
        gate_result,
        root=root,
        gate_admission_epoch_identity=gate_admission_epoch_identity,
    )
    gate_topology = root["stage_topology"]["gate1_v4"]
    inferred_campaign_dir = _absolute(gate_topology["selection_path"]).parent.parent
    expected_paths = {
        "campaign root": inferred_campaign_dir / "campaign-root.json",
        "Gate 1 selection": _absolute(gate_topology["selection_path"]),
        "Gate 1 result": _absolute(gate_topology["gate_path"]),
        "Gate 1 admission epoch": _absolute(gate_topology["gate_admission_epoch_path"]),
    }
    actual_paths = {
        "campaign root": _absolute(campaign_root_identity["path"]),
        "Gate 1 selection": _absolute(gate1_selection_identity["path"]),
        "Gate 1 result": _absolute(gate_result_identity["path"]),
        "Gate 1 admission epoch": _absolute(gate_admission_epoch_identity["path"]),
    }
    if actual_paths != expected_paths:
        raise AuthorityError("CONTINUATION_INVALID", "continuation authority path binding drifted")
    replay_detached_identity(campaign_root_identity, "continuation campaign root")
    selection_snapshot = replay_detached_identity(
        gate1_selection_identity,
        "continuation Gate 1 selection",
    )
    selection = load_gate1_selection_bytes(
        selection_snapshot.data,
        gate1_selection_identity,
    )
    validate_gate1_selection(selection, root=root)
    checkpoint_snapshot = replay_detached_identity(
        gate_admission_epoch_identity,
        "continuation Gate 1 admission epoch",
    )
    checkpoint = strict_loads(
        checkpoint_snapshot.data,
        "Gate 1 admission epoch checkpoint",
    )
    if canonical_json(checkpoint) != checkpoint_snapshot.data:
        raise AuthorityError(
            "CONTINUATION_INVALID",
            "Gate 1 admission epoch checkpoint is not canonical",
        )
    validate_gate_admission_epoch_checkpoint(
        checkpoint,
        root=root,
        selection=selection,
    )
    gate_snapshot = replay_detached_identity(gate_result_identity, "continuation Gate 1 result")
    parsed_gate = strict_loads(gate_snapshot.data, "Gate 1 result")
    if parsed_gate != gate_result or canonical_json(parsed_gate) != gate_snapshot.data:
        raise AuthorityError("CONTINUATION_INVALID", "Gate 1 result bytes do not match the admitted result")
    for slot in GATE1_SLOTS:
        replay_identity = replay_ids[slot]
        replay_path = _absolute(replay_identity["path"])
        attempt_dir = _absolute(gate_topology["units"][slot]["attempt_dir"])
        if not replay_path.is_relative_to(attempt_dir):
            raise AuthorityError("CONTINUATION_INVALID", f"{slot} replay escaped its attempt directory")
        replay_detached_identity(replay_identity, f"continuation {slot} detached replay")
    result = {
        "campaign_closed": False,
        "campaign_id": root["campaign_id"],
        "campaign_root_identity": dict(campaign_root_identity),
        "continuation_authorized": True,
        "continuation_eligible": True,
        "created_at_utc": created_at_utc,
        "detached_replay_identities": dict(replay_ids),
        "future_child": {
            "arm_selection_path": root["stage_topology"]["prospective_ab16"]["arm_selection_path"],
            "manifest_path": root["stage_topology"]["prospective_ab16"]["manifest_path"],
            "slots_absent": True,
            "suite": "prospective-ab16",
        },
        "gate1_result_identity": dict(gate_result_identity),
        "gate1_selection_identity": dict(gate1_selection_identity),
        "gate_admission_epoch_identity": dict(gate_admission_epoch_identity),
        "manager_epoch": dict(current_manager_epoch),
        "organic_arm_launch_authorized": False,
        "run_nonce": root["run_nonce"],
        "schema_version": CONTINUATION_SCHEMA,
    }
    validate_continuation_authorization(result, root=root)
    return result


def validate_continuation_authorization(
    value: object,
    *,
    root: Mapping[str, object],
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "campaign_closed",
            "campaign_id",
            "campaign_root_identity",
            "continuation_authorized",
            "continuation_eligible",
            "created_at_utc",
            "detached_replay_identities",
            "future_child",
            "gate1_result_identity",
            "gate1_selection_identity",
            "gate_admission_epoch_identity",
            "manager_epoch",
            "organic_arm_launch_authorized",
            "run_nonce",
            "schema_version",
        },
        "continuation authorization",
    )
    if (
        record["schema_version"] != CONTINUATION_SCHEMA
        or record["campaign_closed"] is not False
        or record["continuation_authorized"] is not True
        or record["continuation_eligible"] is not True
        or record["organic_arm_launch_authorized"] is not False
        or record["campaign_id"] != root["campaign_id"]
        or record["run_nonce"] != root["run_nonce"]
        or not same_manager_epoch(record["manager_epoch"], root["manager_epoch"])
    ):
        raise AuthorityError("CONTINUATION_INVALID", "continuation semantics drifted")
    _utc(record["created_at_utc"], "continuation created_at_utc")
    for field in (
        "campaign_root_identity",
        "gate1_result_identity",
        "gate1_selection_identity",
        "gate_admission_epoch_identity",
    ):
        validate_detached_identity(record[field], f"continuation {field}")
    gate = root["stage_topology"]["gate1_v4"]
    inferred_campaign_dir = _absolute(gate["selection_path"]).parent.parent
    expected_paths = {
        "campaign_root_identity": inferred_campaign_dir / "campaign-root.json",
        "gate1_selection_identity": _absolute(gate["selection_path"]),
        "gate1_result_identity": _absolute(gate["gate_path"]),
        "gate_admission_epoch_identity": _absolute(gate["gate_admission_epoch_path"]),
    }
    if any(_absolute(record[field]["path"]) != expected for field, expected in expected_paths.items()):
        raise AuthorityError(
            "CONTINUATION_INVALID",
            "continuation detached authority path drifted",
        )
    replay = _identity_map(record["detached_replay_identities"], "continuation detached replays")
    if set(replay) != set(GATE1_SLOTS):
        raise AuthorityError("CONTINUATION_INVALID", "continuation replay set drifted")
    future = _exact_keys(
        record["future_child"],
        {"arm_selection_path", "manifest_path", "slots_absent", "suite"},
        "continuation future child",
    )
    prospective = root["stage_topology"]["prospective_ab16"]
    if (
        future["suite"] != "prospective-ab16"
        or future["slots_absent"] is not True
        or future["manifest_path"] != prospective["manifest_path"]
        or future["arm_selection_path"] != prospective["arm_selection_path"]
    ):
        raise AuthorityError("CONTINUATION_INVALID", "continuation future-child binding drifted")
    return record


def write_continuation_authorization(
    campaign_root_path: Path | str,
    campaign_root_identity: Mapping[str, object],
    continuation: Mapping[str, object],
) -> dict[str, object]:
    root, _ = load_campaign_root(campaign_root_path, campaign_root_identity)
    validate_continuation_authorization(continuation, root=root)
    replay_detached_identity(
        continuation["campaign_root_identity"],
        "continuation campaign root",
    )
    gate_snapshot = replay_detached_identity(
        continuation["gate1_result_identity"],
        "continuation Gate 1 result",
    )
    checkpoint_snapshot = replay_detached_identity(
        continuation["gate_admission_epoch_identity"],
        "continuation Gate 1 admission epoch",
    )
    selection_snapshot = replay_detached_identity(
        continuation["gate1_selection_identity"],
        "continuation Gate 1 selection",
    )
    selection = load_gate1_selection_bytes(
        selection_snapshot.data,
        continuation["gate1_selection_identity"],
    )
    checkpoint = strict_loads(
        checkpoint_snapshot.data,
        "Gate 1 admission epoch checkpoint",
    )
    if canonical_json(checkpoint) != checkpoint_snapshot.data:
        raise AuthorityError(
            "CONTINUATION_INVALID",
            "Gate 1 admission epoch checkpoint is not canonical",
        )
    validate_gate_admission_epoch_checkpoint(
        checkpoint,
        root=root,
        selection=selection,
    )
    gate_result = strict_loads(gate_snapshot.data, "Gate 1 result")
    if not isinstance(gate_result, Mapping) or canonical_json(gate_result) != gate_snapshot.data:
        raise AuthorityError(
            "CONTINUATION_INVALID",
            "Gate 1 result is not canonical",
        )
    _validate_gate_continuation_eligibility(
        gate_result,
        root=root,
        gate_admission_epoch_identity=continuation["gate_admission_epoch_identity"],
    )
    for slot, identity in continuation["detached_replay_identities"].items():
        replay_detached_identity(identity, f"continuation {slot} detached replay")
    prospective = root["stage_topology"]["prospective_ab16"]
    absent = [
        _absolute(prospective["manifest_path"]),
        _absolute(prospective["arm_selection_path"]),
        _absolute(prospective["terminal_classification_path"]),
        *(_absolute(arm["attempt_dir"]) for arm in prospective["arms"]),
    ]
    if any(path.exists() or path.is_symlink() for path in absent):
        raise AuthorityError("FUTURE_SLOT_CONSUMED", "prospective child exists before continuation")
    output = _absolute(root["stage_topology"]["gate1_v4"]["continuation_path"])
    if output.exists() or output.is_symlink():
        raise AuthorityError("NO_OVERWRITE_COLLISION", "continuation output already exists")
    return write_exclusive(output, canonical_json(continuation))


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit-attestor")
    audit.add_argument("--attestor", type=Path, required=True)
    verify = subparsers.add_parser("verify-package")
    verify.add_argument("--package-dir", type=Path, required=True)
    verify.add_argument("--manager-epoch", type=Path, required=True)
    capture = subparsers.add_parser("capture-manager-epoch")
    capture.add_argument("--attestor", type=Path, required=True)
    capture.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parse_args(argv)
    try:
        if arguments.command == "audit-attestor":
            result = audit_attestor_source(snapshot_regular(arguments.attestor, size_limit=1 << 20).data)
        elif arguments.command == "verify-package":
            epoch_snapshot = snapshot_regular(arguments.manager_epoch)
            epoch = strict_loads(epoch_snapshot.data, "manager epoch")
            result = verify_package(
                arguments.package_dir,
                expected_manager_epoch=validate_manager_epoch(epoch),
                replay_external=True,
            )
        else:
            result = capture_manager_epoch(attestor_path=arguments.attestor)
            write_exclusive(arguments.output, canonical_json(result))
    except AuthorityError as exc:
        print(
            json.dumps(
                {"error_code": exc.code, "message": str(exc), "status": "FAIL_CLOSED"},
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
