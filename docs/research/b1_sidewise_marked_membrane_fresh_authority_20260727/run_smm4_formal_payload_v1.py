#!/usr/bin/env python3
"""Run the one-shot SMM4 formal-a004 payload without granting terminal authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
from types import ModuleType
from typing import Any


AUTHORITY_SCHEMA = "b1_sidewise_smm4_pre_run_authority_v1"
SELECTION_SCHEMA = "b1_sidewise_smm4_attempt_selection_v1"
RECEIPT_SCHEMA = "b1_sidewise_smm4_internal_formal_receipt_v1"
ATTEMPT = "smm4-formal-a004"
FORMULA_SIZE = 283
FORMULA_SHA256 = "d4b79cd76c80d23e509ad09b1d2e7fa02fa337049f40459ab803f0fc55a4d865"
PROOF_LIMIT = 5_000_000_000
LOW_WATER = 10 * 1024**3
REQUIRED_FREE = LOW_WATER + PROOF_LIMIT
ROUNDINGSAT_SECONDS = 3600
ROUNDINGSAT_MONITOR_SECONDS = 3900
VERIPB_SECONDS = 3600
TRANSLATION_SECONDS = 300
RUNTIME_MAX_SECONDS = 9000
PAYLOAD_WAIT_SECONDS = 8000
KEEPER_TIMEOUT_SECONDS = 8700
JSON_LIMIT = 64 * 1024 * 1024
TEXT_LIMIT = 64 * 1024 * 1024
BUILD_MEMBERS = (
    "formula.opb",
    "variable_map.json",
    "encoder.meta.json",
    "build_record.json",
    "estimate.json",
    "SHA256SUMS",
)
ROUNDINGSAT_STATUS = re.compile(r"^s (UNSATISFIABLE|SATISFIABLE|UNKNOWN)\s*$")
VERIPB_SUCCESS = re.compile(r"^s VERIFIED UNSATISFIABLE\s*$")
VERIPB_ERROR_MARKERS = (
    "Error:",
    "Checking error",
    "panic",
    "failed",
    "unsupported",
)
STABLE_STAT_FIELDS = (
    "st_dev",
    "st_ino",
    "st_mode",
    "st_nlink",
    "st_uid",
    "st_gid",
    "st_size",
    "st_mtime_ns",
    "st_ctime_ns",
)
FULL_IDENTITY_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
    "mode_octal",
    "device",
    "inode",
    "link_count",
)
RETAINED_REGULAR_FIELDS = (
    "fd",
    "before",
    "identity",
    "logical_path",
    "fd_path",
    "access",
)
PINNED_EXECUTABLE_FIELDS = (
    "fd",
    "before",
    "identity",
    "logical_path",
    "fd_path",
)
RETAINED_ANCHOR_FIELDS = (
    "st_dev",
    "st_ino",
    "st_mode",
    "st_nlink",
    "st_uid",
    "st_gid",
)
RETAINED_FD_PROVENANCE_SCHEMA = "b1_sidewise_smm4_retained_fd_provenance_v1"
TRANSLATION_FD_BOOTSTRAP = r"""
import fcntl
import hashlib
import json
import os
import posixpath
import re
import stat
import sys

FIELDS = ("path", "size_bytes", "sha256", "mode_octal", "device", "inode", "link_count")
STABLE = (
    "st_dev", "st_ino", "st_mode", "st_nlink", "st_uid", "st_gid",
    "st_size", "st_mtime_ns", "st_ctime_ns",
)

def fail(message):
    raise SystemExit("translation retained FD bootstrap: " + message)

try:
    descriptor = int(sys.argv[1])
    expected = json.loads(sys.argv[2])
except Exception as exc:
    fail("malformed retained descriptor arguments: " + str(exc))
arguments = sys.argv[3:]
if type(expected) is not dict or set(expected) != set(FIELDS):
    fail("exact full7 identity key set mismatch")
if (
    type(expected["path"]) is not str
    or not posixpath.isabs(expected["path"])
    or expected["path"].startswith("//")
    or posixpath.normpath(expected["path"]) != expected["path"]
):
    fail("identity path is not canonical")
if type(expected["size_bytes"]) is not int or expected["size_bytes"] < 0:
    fail("identity size is invalid")
if type(expected["sha256"]) is not str or re.fullmatch(r"[0-9a-f]{64}", expected["sha256"]) is None:
    fail("identity SHA-256 is invalid")
if type(expected["mode_octal"]) is not str or re.fullmatch(r"[0-7]{4}", expected["mode_octal"]) is None:
    fail("identity mode is invalid")
for name, minimum in (("device", 0), ("inode", 1)):
    if type(expected[name]) is not int or expected[name] < minimum:
        fail("identity " + name + " is invalid")
if type(expected["link_count"]) is not int or expected["link_count"] != 1:
    fail("identity link_count must equal one")
if fcntl.fcntl(descriptor, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDONLY:
    fail("retained tool FD is not read-only")
before = os.fstat(descriptor)
if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
    fail("retained tool FD is not a single-link regular file")
parts = []
offset = 0
while offset < before.st_size:
    block = os.pread(descriptor, min(1 << 20, before.st_size - offset), offset)
    if not block:
        fail("short retained-FD read")
    parts.append(block)
    offset += len(block)
if os.pread(descriptor, 1, offset):
    fail("retained tool FD extended during read")
after = os.fstat(descriptor)
if any(getattr(before, name) != getattr(after, name) for name in STABLE):
    fail("retained tool FD changed during read")
raw = b"".join(parts)
actual = {
    "path": expected["path"],
    "size_bytes": len(raw),
    "sha256": hashlib.sha256(raw).hexdigest(),
    "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
    "device": before.st_dev,
    "inode": before.st_ino,
    "link_count": before.st_nlink,
}
if actual != expected:
    fail("retained tool full7 identity drifted")
real_os_open = os.open

def retained_self_open(path, flags, mode=0o777, *, dir_fd=None):
    if os.fspath(path) == expected["path"]:
        forbidden = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_TRUNC | os.O_APPEND
        if dir_fd is not None or flags & forbidden or flags & os.O_ACCMODE != os.O_RDONLY:
            fail("translation tool requested invalid self-open flags")
        os.lseek(descriptor, 0, os.SEEK_SET)
        return os.dup(descriptor)
    return real_os_open(path, flags, mode, dir_fd=dir_fd)

os.open = retained_self_open
sys.argv = [expected["path"], *arguments]
namespace = {
    "__name__": "__main__",
    "__file__": expected["path"],
    "__package__": None,
    "__cached__": None,
}
exec(compile(raw, expected["path"], "exec", dont_inherit=True), namespace)
"""
RESEARCH = Path(__file__).resolve().parent
IDENTITY_CONTRACT = RESEARCH / "identity_contract_v1.py"
AUTHORITY_PACKAGE = RESEARCH / "authority_package_v1.py"

_ACTIVE_IDENTITY_CONTRACT: ModuleType | None = None


class PayloadError(RuntimeError):
    """Raised when the SMM4 payload must fail closed."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise PayloadError(message)


def path_exists(path: Path) -> bool:
    return os.path.lexists(path)


def require_absent(path: Path, label: str) -> None:
    require(not path_exists(path), f"{label}: output already exists")


def stable(before: os.stat_result, after: os.stat_result) -> bool:
    return all(getattr(before, field) == getattr(after, field) for field in STABLE_STAT_FIELDS)


def snapshot_regular(
    path: Path,
    label: str,
    *,
    collect: bool = True,
    max_bytes: int | None = None,
) -> tuple[bytes | None, dict[str, Any]]:
    require(path.is_absolute(), f"{label}: path is not absolute")
    try:
        absolute = path.resolve(strict=True)
    except OSError as exc:
        raise PayloadError(f"{label}: cannot resolve: {exc}") from exc
    require(path == absolute, f"{label}: path is not canonical or traverses a symlink")
    descriptor = os.open(
        absolute,
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode), f"{label}: not a regular file")
        if max_bytes is not None:
            require(
                before.st_size <= max_bytes,
                f"{label}: exceeds {max_bytes} byte read limit",
            )
        digest = hashlib.sha256()
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, 1 << 20)
            if not block:
                break
            total += len(block)
            if max_bytes is not None:
                require(
                    total <= max_bytes,
                    f"{label}: grew beyond {max_bytes} byte read limit",
                )
            digest.update(block)
            if collect:
                chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require(stable(before, after), f"{label}: changed during same-fd read")
    require(total == before.st_size, f"{label}: short or extended read")
    return (
        b"".join(chunks) if collect else None,
        {
            "path": str(absolute),
            "size_bytes": total,
            "sha256": digest.hexdigest(),
            "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
            "device": before.st_dev,
            "inode": before.st_ino,
            "link_count": before.st_nlink,
        },
    )


def strict_json(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PayloadError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise PayloadError(f"{label}: non-integer JSON number {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PayloadError(f"{label}: malformed strict JSON: {exc}") from exc


def load_json(
    path: Path,
    label: str,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    raw, identity = snapshot_regular(
        path,
        label,
        max_bytes=JSON_LIMIT,
    )
    require(raw is not None, f"{label}: internal snapshot failure")
    payload = strict_json(raw, label)
    require(isinstance(payload, dict), f"{label}: root is not an object")
    return payload, identity, raw


def identity_path(value: Any, label: str) -> Path:
    require(isinstance(value, dict), f"{label}: identity is not an object")
    path = value.get("path")
    require(
        isinstance(path, str) and path.startswith("/"),
        f"{label}: absolute path missing",
    )
    return Path(path)


def match_identity(
    actual: dict[str, Any],
    expected: Any,
    label: str,
) -> None:
    contract = _ACTIVE_IDENTITY_CONTRACT
    require(contract is not None, f"{label}: shared identity contract is not active")
    try:
        expected_full = contract.validate_full_identity(
            expected,
            f"{label} expected identity",
        )
        projection = contract.canonical_content_projection(
            expected_full,
            f"{label} expected identity",
        )
        contract.assert_identity_join(
            expected_full,
            projection,
            actual,
            label,
        )
    except Exception as exc:
        raise PayloadError(f"{label}: exact identity mismatch: {exc}") from exc


def _bootstrap_full_identity(value: Any, label: str) -> dict[str, Any]:
    require(
        type(value) is dict and set(value) == set(FULL_IDENTITY_FIELDS),
        f"{label}: exact full7 identity key set mismatch",
    )
    result = {field: value[field] for field in FULL_IDENTITY_FIELDS}
    path = result["path"]
    require(
        type(path) is str
        and os.path.isabs(path)
        and not path.startswith("//")
        and os.path.normpath(path) == path,
        f"{label}: noncanonical absolute identity path",
    )
    require(
        type(result["size_bytes"]) is int and result["size_bytes"] >= 0,
        f"{label}: invalid identity size",
    )
    require(
        type(result["sha256"]) is str
        and re.fullmatch(r"[0-9a-f]{64}", result["sha256"]) is not None,
        f"{label}: invalid identity SHA-256",
    )
    require(
        type(result["mode_octal"]) is str
        and re.fullmatch(r"[0-7]{4}", result["mode_octal"]) is not None,
        f"{label}: invalid identity mode",
    )
    for field, minimum in (("device", 0), ("inode", 1)):
        require(
            type(result[field]) is int and result[field] >= minimum,
            f"{label}: invalid identity {field}",
        )
    require(
        type(result["link_count"]) is int and result["link_count"] == 1,
        f"{label}: identity link_count must equal one",
    )
    return result


def _activate_identity_contract(module: ModuleType) -> ModuleType:
    required = (
        "IdentityContractError",
        "validate_full_identity",
        "validate_projection",
        "canonical_content_projection",
        "assert_identity_join",
    )
    require(
        all(hasattr(module, name) for name in required),
        "canonical content identity contract API missing",
    )
    global _ACTIVE_IDENTITY_CONTRACT
    _ACTIVE_IDENTITY_CONTRACT = module
    return module


def load_sealed_authority(
    path: Path,
    package_id: str,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    bytes,
    dict[str, Any],
]:
    identity_raw, identity_observed = snapshot_regular(
        IDENTITY_CONTRACT,
        "canonical content identity contract",
        max_bytes=JSON_LIMIT,
    )
    require(identity_raw is not None, "identity contract source bytes missing")
    identity_module = ModuleType("_smm4_payload_bootstrap_identity")
    identity_module.__file__ = str(IDENTITY_CONTRACT)
    identity_module.__package__ = None
    exec(
        compile(identity_raw, str(IDENTITY_CONTRACT), "exec", dont_inherit=True),
        identity_module.__dict__,
    )
    _activate_identity_contract(identity_module)

    package_raw, package_observed = snapshot_regular(
        AUTHORITY_PACKAGE,
        "sealed authority package verifier",
        max_bytes=JSON_LIMIT,
    )
    require(package_raw is not None, "authority package verifier source bytes missing")
    package_module = ModuleType("_smm4_payload_bootstrap_authority_package")
    package_module.__file__ = str(AUTHORITY_PACKAGE)
    package_module.__package__ = None
    previous = sys.modules.get("identity_contract_v1")
    sys.modules["identity_contract_v1"] = identity_module
    try:
        exec(
            compile(package_raw, str(AUTHORITY_PACKAGE), "exec", dont_inherit=True),
            package_module.__dict__,
        )
    finally:
        if previous is None:
            sys.modules.pop("identity_contract_v1", None)
        else:
            sys.modules["identity_contract_v1"] = previous
    try:
        package = package_module.verify_authority_package(
            path.parent,
            package_id,
        )
    except Exception as exc:
        raise PayloadError(f"SMM4 authority package verification failed: {exc}") from exc
    require(
        isinstance(package, dict)
        and set(package)
        == {"authority_raw", "authority", "seal", "package_id"}
        and isinstance(package.get("authority_raw"), bytes)
        and isinstance(package.get("authority"), dict)
        and isinstance(package.get("seal"), dict)
        and package.get("authority", {}).get("path") == str(path)
        and package.get("package_id") == package_id,
        "SMM4 authority package verifier returned malformed output",
    )
    authority_raw = package["authority_raw"]
    authority = strict_json(authority_raw, "SMM4 sealed authority")
    require(isinstance(authority, dict), "SMM4 sealed authority root is not an object")
    tools = authority.get("tools")
    require(isinstance(tools, dict), "SMM4 sealed authority tools missing")
    match_identity(
        identity_observed,
        tools.get("identity_contract"),
        "canonical content identity contract",
    )
    match_identity(
        package_observed,
        tools.get("authority_package"),
        "sealed authority package verifier",
    )
    return authority, package["authority"], authority_raw, package["seal"]


def snapshot_pinned(
    expected: Any,
    label: str,
    *,
    collect: bool = True,
    max_bytes: int | None = None,
) -> tuple[bytes | None, dict[str, Any]]:
    path = identity_path(expected, label)
    raw, actual = snapshot_regular(
        path,
        label,
        collect=collect,
        max_bytes=max_bytes,
    )
    match_identity(actual, expected, label)
    return raw, actual


def load_pinned_module(expected: Any, label: str) -> ModuleType:
    raw, identity = snapshot_pinned(expected, label, max_bytes=JSON_LIMIT)
    require(raw is not None, f"{label}: source bytes missing")
    module = ModuleType(f"_smm4_{Path(identity['path']).stem}_{identity['sha256'][:12]}")
    module.__file__ = identity["path"]
    module.__package__ = None
    try:
        exec(
            compile(raw, identity["path"], "exec", dont_inherit=True),
            module.__dict__,
        )
    except Exception as exc:
        raise PayloadError(f"{label}: pinned execution failed: {exc}") from exc
    return module


def load_identity_contract(expected: Any, label: str) -> ModuleType:
    expected_full = _bootstrap_full_identity(expected, f"{label} expected identity")
    raw, actual = snapshot_regular(
        Path(expected_full["path"]),
        label,
        max_bytes=JSON_LIMIT,
    )
    require(raw is not None, f"{label}: source bytes missing")
    actual_full = _bootstrap_full_identity(actual, f"{label} actual identity")
    require(actual_full == expected_full, f"{label}: exact full7 identity drifted")
    module = ModuleType(
        f"_smm4_{Path(actual_full['path']).stem}_{actual_full['sha256'][:12]}"
    )
    module.__file__ = actual_full["path"]
    module.__package__ = None
    try:
        exec(
            compile(raw, actual_full["path"], "exec", dont_inherit=True),
            module.__dict__,
        )
    except Exception as exc:
        raise PayloadError(f"{label}: pinned execution failed: {exc}") from exc
    return _activate_identity_contract(module)


def validate_selection_authority_join(
    identity_module: ModuleType,
    selection: dict[str, Any],
    authority_identity: dict[str, Any],
) -> dict[str, Any]:
    try:
        return identity_module.assert_identity_join(
            selection.get("authority"),
            selection.get("authority_content_identity"),
            authority_identity,
            "formal payload authority",
        )
    except Exception as exc:
        raise PayloadError(f"formal payload authority identity join failed: {exc}") from exc


def mode_from_identity(identity: dict[str, Any], label: str) -> int:
    value = identity.get("mode_octal")
    require(
        isinstance(value, str) and re.fullmatch(r"0[0-7]{3}", value) is not None,
        f"{label}: invalid mode",
    )
    return int(value, 8)


def write_once(path: Path, raw: bytes, *, mode: int = 0o644) -> dict[str, Any]:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(descriptor, raw[offset:])
            require(count > 0, f"{path}: short output write")
            offset += count
        os.fsync(descriptor)
        record = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require(stat.S_ISREG(record.st_mode), f"{path}: output is not regular")
    require(record.st_size == len(raw), f"{path}: output size mismatch")
    require(record.st_nlink == 1, f"{path}: output link_count must equal one")
    identity = _bootstrap_full_identity(
        {
            "path": str(path.absolute()),
            "size_bytes": len(raw),
            "sha256": sha256(raw),
            "mode_octal": f"{stat.S_IMODE(record.st_mode):04o}",
            "device": record.st_dev,
            "inode": record.st_ino,
            "link_count": record.st_nlink,
        },
        f"output {path.name}",
    )
    contract = _ACTIVE_IDENTITY_CONTRACT
    if contract is not None:
        try:
            return contract.validate_full_identity(identity, f"output {path.name}")
        except Exception as exc:
            raise PayloadError(f"{path}: output identity contract failed: {exc}") from exc
    return identity


def make_directory(path: Path, label: str) -> None:
    require_absent(path, label)
    os.mkdir(path, 0o755)
    record = os.lstat(path)
    require(stat.S_ISDIR(record.st_mode), f"{label}: mkdir did not make directory")
    require(not stat.S_ISLNK(record.st_mode), f"{label}: directory is symlink")


def free_bytes(path: Path) -> int:
    result = os.statvfs(path)
    return result.f_bavail * result.f_frsize


def read_proc_bounded(path: Path, label: str, limit: int = 64 * 1024) -> bytes:
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(descriptor)
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, 4096)
            if not block:
                break
            total += len(block)
            require(total <= limit, f"{label}: proc payload exceeds limit")
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    for field in ("st_dev", "st_ino", "st_mode"):
        require(
            getattr(before, field) == getattr(after, field),
            f"{label}: proc identity changed during read",
        )
    return b"".join(chunks)


def verify_current_cgroup(expected_unit: str) -> dict[str, Any]:
    raw = read_proc_bounded(Path("/proc/self/cgroup"), "payload cgroup")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise PayloadError("payload cgroup: non-ASCII bytes") from exc
    unified = [line.split("::", 1)[1] for line in lines if "::" in line]
    require(len(unified) == 1, "payload cgroup: unified path is ambiguous")
    relative = unified[0]
    require(
        expected_unit in relative,
        "payload is outside selected systemd unit",
    )
    return {
        "proc_path": "/proc/self/cgroup",
        "sha256": sha256(raw),
        "size_bytes": len(raw),
        "unified_path": relative,
        "expected_unit_present": True,
    }


def executable_record(
    value: Any,
    label: str,
) -> tuple[Path, dict[str, Any], str]:
    require(isinstance(value, dict), f"{label}: binary identity missing")
    if "target" in value:
        logical = value.get("path")
        resolved = value.get("resolved_path")
        target = value.get("target")
        require(
            isinstance(logical, str) and logical.startswith("/"),
            f"{label}: logical path missing",
        )
        require(
            isinstance(resolved, str) and resolved.startswith("/"),
            f"{label}: resolved path missing",
        )
        try:
            current_resolved = Path(logical).resolve(strict=True)
        except OSError as exc:
            raise PayloadError(f"{label}: cannot resolve logical path: {exc}") from exc
        require(
            str(current_resolved) == resolved,
            f"{label}: logical path resolution drifted",
        )
        return Path(resolved), target, logical
    path = identity_path(value, label)
    return path, value, str(path)


def pin_executable(value: Any, label: str) -> dict[str, Any]:
    path, expected, logical_path = executable_record(value, label)
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode), f"{label}: not a regular file")
        digest = hashlib.sha256()
        total = 0
        while True:
            block = os.read(descriptor, 1 << 20)
            if not block:
                break
            total += len(block)
            digest.update(block)
        after = os.fstat(descriptor)
        require(stable(before, after), f"{label}: changed while pinning")
        require(total == before.st_size, f"{label}: short read while pinning")
        actual = {
            "path": str(path.absolute()),
            "size_bytes": total,
            "sha256": digest.hexdigest(),
            "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
            "device": before.st_dev,
            "inode": before.st_ino,
            "link_count": before.st_nlink,
        }
        match_identity(actual, expected, label)
        require(
            stat.S_IMODE(before.st_mode) & 0o111 != 0,
            f"{label}: executable bit missing",
        )
        return {
            "fd": descriptor,
            "before": before,
            "identity": actual,
            "logical_path": logical_path,
            "fd_path": f"/proc/self/fd/{descriptor}",
        }
    except BaseException:
        os.close(descriptor)
        raise


def verify_pinned_executable(record: dict[str, Any], label: str) -> None:
    pinned = _validate_pinned_executable_record(record, label)
    after = os.fstat(pinned["fd"])
    require(
        stable(pinned["before"], after),
        f"{label}: pinned executable changed during use",
    )


def close_pinned_executable(record: dict[str, Any] | None) -> None:
    if record is not None:
        os.close(record["fd"])


def _validate_pinned_executable_record(value: Any, label: str) -> dict[str, Any]:
    require(
        type(value) is dict and set(value) == set(PINNED_EXECUTABLE_FIELDS),
        f"{label}: exact pinned executable record key set mismatch",
    )
    descriptor = value["fd"]
    require(type(descriptor) is int and descriptor >= 0, f"{label}: invalid pinned executable FD")
    require(isinstance(value["before"], os.stat_result), f"{label}: pinned executable anchor missing")
    _bootstrap_full_identity(value["identity"], f"{label} pinned executable identity")
    require(
        type(value["logical_path"]) is str and value["logical_path"].startswith("/"),
        f"{label}: pinned executable logical path missing",
    )
    require(
        value["fd_path"] == f"/proc/self/fd/{descriptor}",
        f"{label}: pinned executable FD path mismatch",
    )
    return value


def _identity_from_stat(path: str, record: os.stat_result, digest: str) -> dict[str, Any]:
    return _bootstrap_full_identity(
        {
            "path": path,
            "size_bytes": record.st_size,
            "sha256": digest,
            "mode_octal": f"{stat.S_IMODE(record.st_mode):04o}",
            "device": record.st_dev,
            "inode": record.st_ino,
            "link_count": record.st_nlink,
        },
        f"retained regular file {path}",
    )


def _validate_retained_record(value: Any, label: str) -> dict[str, Any]:
    require(
        type(value) is dict and set(value) == set(RETAINED_REGULAR_FIELDS),
        f"{label}: exact retained-FD record key set mismatch",
    )
    descriptor = value["fd"]
    require(type(descriptor) is int and descriptor >= 0, f"{label}: invalid retained FD")
    require(isinstance(value["before"], os.stat_result), f"{label}: retained anchor missing")
    identity = _bootstrap_full_identity(value["identity"], f"{label} retained identity")
    require(
        type(value["logical_path"]) is str
        and value["logical_path"] == identity["path"],
        f"{label}: retained logical path mismatch",
    )
    require(
        value["fd_path"] == f"/proc/self/fd/{descriptor}",
        f"{label}: retained FD path mismatch",
    )
    require(
        value["access"] in {"read_only", "read_write_output"},
        f"{label}: retained access mode invalid",
    )
    return value


def _same_retained_anchor(before: os.stat_result, after: os.stat_result) -> bool:
    return all(
        getattr(before, field) == getattr(after, field)
        for field in RETAINED_ANCHOR_FIELDS
    )


def _verify_retained_path_binding(record: dict[str, Any], label: str) -> None:
    retained = _validate_retained_record(record, label)
    try:
        current = os.stat(retained["logical_path"], follow_symlinks=False)
    except OSError as exc:
        raise PayloadError(f"{label}: retained path binding unavailable: {exc}") from exc
    require(stat.S_ISREG(current.st_mode), f"{label}: retained path stopped being regular")
    require(
        _same_retained_anchor(retained["before"], current),
        f"{label}: retained path binding drifted",
    )


def snapshot_retained_regular(
    record: dict[str, Any],
    label: str,
    *,
    collect: bool = True,
    max_bytes: int | None = None,
) -> tuple[bytes | None, dict[str, Any]]:
    retained = _validate_retained_record(record, label)
    _verify_retained_path_binding(retained, label)
    descriptor = retained["fd"]
    before = os.fstat(descriptor)
    require(stat.S_ISREG(before.st_mode), f"{label}: retained FD is not regular")
    require(
        _same_retained_anchor(retained["before"], before),
        f"{label}: retained FD anchor drifted",
    )
    require(before.st_nlink == 1, f"{label}: retained file link_count must equal one")
    if max_bytes is not None:
        require(before.st_size <= max_bytes, f"{label}: exceeds {max_bytes} byte read limit")
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    while total < before.st_size:
        block = os.pread(descriptor, min(1 << 20, before.st_size - total), total)
        require(bool(block), f"{label}: short retained-FD read")
        total += len(block)
        if max_bytes is not None:
            require(total <= max_bytes, f"{label}: grew beyond {max_bytes} byte read limit")
        digest.update(block)
        if collect:
            chunks.append(block)
    require(
        os.pread(descriptor, 1, total) == b"",
        f"{label}: retained file extended during read",
    )
    after = os.fstat(descriptor)
    require(stable(before, after), f"{label}: changed during retained-FD read")
    require(total == before.st_size, f"{label}: short or extended retained-FD read")
    identity = _identity_from_stat(retained["logical_path"], before, digest.hexdigest())
    return b"".join(chunks) if collect else None, identity


def pin_retained_regular(
    expected: Any,
    label: str,
    *,
    collect: bool = True,
    max_bytes: int | None = None,
) -> tuple[bytes | None, dict[str, Any]]:
    contract = _ACTIVE_IDENTITY_CONTRACT
    require(contract is not None, f"{label}: shared identity contract is not active")
    try:
        expected_full = contract.validate_full_identity(expected, f"{label} expected identity")
    except Exception as exc:
        raise PayloadError(f"{label}: malformed expected identity: {exc}") from exc
    path = Path(expected_full["path"])
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as exc:
        raise PayloadError(f"{label}: cannot open expected retained file: {exc}") from exc
    record: dict[str, Any] | None = None
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode), f"{label}: not a regular file")
        require(before.st_nlink == 1, f"{label}: link_count must equal one")
        record = {
            "fd": descriptor,
            "before": before,
            "identity": expected_full,
            "logical_path": expected_full["path"],
            "fd_path": f"/proc/self/fd/{descriptor}",
            "access": "read_only",
        }
        raw, actual = snapshot_retained_regular(
            record,
            label,
            collect=collect,
            max_bytes=max_bytes,
        )
        match_identity(actual, expected_full, label)
        record["identity"] = actual
        return raw, record
    except BaseException:
        os.close(descriptor)
        raise


def create_retained_output(path: Path, label: str) -> dict[str, Any]:
    require(path.is_absolute(), f"{label}: output path is not absolute")
    try:
        descriptor = os.open(
            path,
            os.O_RDWR
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o644,
        )
    except OSError as exc:
        raise PayloadError(f"{label}: exclusive retained output create failed: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode), f"{label}: output is not regular")
        require(before.st_size == 0, f"{label}: exclusive output is not empty")
        require(before.st_nlink == 1, f"{label}: output link_count must equal one")
        identity = _identity_from_stat(
            str(path),
            before,
            hashlib.sha256(b"").hexdigest(),
        )
        record = {
            "fd": descriptor,
            "before": before,
            "identity": identity,
            "logical_path": str(path),
            "fd_path": f"/proc/self/fd/{descriptor}",
            "access": "read_write_output",
        }
        _validate_retained_record(record, label)
        _verify_retained_path_binding(record, label)
        return record
    except BaseException:
        os.close(descriptor)
        raise


def verify_retained_unchanged(
    record: dict[str, Any],
    expected: Any,
    label: str,
    *,
    max_bytes: int | None = None,
) -> dict[str, Any]:
    _, actual = snapshot_retained_regular(
        record,
        label,
        collect=False,
        max_bytes=max_bytes,
    )
    match_identity(actual, expected, label)
    return actual


def close_retained_regular(record: dict[str, Any] | None) -> None:
    if record is not None:
        os.close(record["fd"])


def translation_fd_invocation(
    python_record: dict[str, Any],
    tool_record: dict[str, Any],
    arguments: list[str],
) -> tuple[list[str], tuple[int, ...]]:
    python_pin = _validate_pinned_executable_record(
        python_record,
        "translation fixed Python",
    )
    tool_pin = _validate_retained_record(tool_record, "translation gate tool")
    require(
        tool_pin["access"] == "read_only",
        "translation gate tool: retained FD must be read-only",
    )
    verify_pinned_executable(python_pin, "translation fixed Python")
    verify_retained_unchanged(
        tool_pin,
        tool_pin["identity"],
        "translation gate tool before execution",
        max_bytes=JSON_LIMIT,
    )
    return (
        [
            python_pin["fd_path"],
            "-I",
            "-c",
            TRANSLATION_FD_BOOTSTRAP,
            str(tool_pin["fd"]),
            json.dumps(tool_pin["identity"], sort_keys=True, separators=(",", ":")),
            *arguments,
        ],
        (python_pin["fd"], tool_pin["fd"]),
    )


def roundingsat_fd_invocation(
    executable_record: dict[str, Any],
    formula_record: dict[str, Any],
    proof_record: dict[str, Any],
) -> tuple[list[str], tuple[int, ...]]:
    executable = _validate_pinned_executable_record(
        executable_record,
        "RoundingSat",
    )
    formula = _validate_retained_record(formula_record, "formal formula")
    proof = _validate_retained_record(proof_record, "RoundingSat proof")
    require(formula["access"] == "read_only", "formal formula: retained FD must be read-only")
    require(
        proof["access"] == "read_write_output",
        "RoundingSat proof: retained FD must be a writable output",
    )
    verify_pinned_executable(executable, "RoundingSat")
    verify_retained_unchanged(
        formula,
        formula["identity"],
        "formal formula before RoundingSat",
        max_bytes=FORMULA_SIZE,
    )
    verify_retained_unchanged(
        proof,
        proof["identity"],
        "RoundingSat exclusive proof seed",
        max_bytes=0,
    )
    return (
        [
            executable["fd_path"],
            f"--proof-log={proof['fd_path']}",
            f"--time-limit={ROUNDINGSAT_SECONDS}",
            formula["fd_path"],
        ],
        (executable["fd"], formula["fd"], proof["fd"]),
    )


def veripb_fd_invocation(
    executable_record: dict[str, Any],
    formula_record: dict[str, Any],
    proof_record: dict[str, Any],
    proof_expected: Any,
) -> tuple[list[str], tuple[int, ...]]:
    executable = _validate_pinned_executable_record(executable_record, "VeriPB")
    formula = _validate_retained_record(formula_record, "formal formula")
    proof = _validate_retained_record(proof_record, "RoundingSat proof")
    require(formula["access"] == "read_only", "formal formula: retained FD must be read-only")
    require(
        proof["access"] == "read_write_output",
        "RoundingSat proof: retained FD must be a writable output",
    )
    verify_pinned_executable(executable, "VeriPB")
    verify_retained_unchanged(
        formula,
        formula["identity"],
        "formal formula before VeriPB",
        max_bytes=FORMULA_SIZE,
    )
    verify_retained_unchanged(
        proof,
        proof_expected,
        "formal proof before VeriPB",
        max_bytes=PROOF_LIMIT,
    )
    return (
        [
            executable["fd_path"],
            "--opb",
            "--stats",
            formula["fd_path"],
            proof["fd_path"],
        ],
        (executable["fd"], formula["fd"], proof["fd"]),
    )


def retained_fd_provenance(
    *,
    formula_write_identity: Any,
    formula_final_identity: Any,
    proof_seed_identity: Any,
    proof_final_identity: Any,
    translation_tool_identity: Any,
    translation_tool_final_identity: Any,
) -> dict[str, Any]:
    contract = _ACTIVE_IDENTITY_CONTRACT
    require(contract is not None, "retained FD provenance: shared identity contract is not active")
    try:
        formula_write = contract.validate_full_identity(
            formula_write_identity,
            "retained FD provenance formula write",
        )
        formula_final = contract.validate_full_identity(
            formula_final_identity,
            "retained FD provenance formula final",
        )
        proof_seed = contract.validate_full_identity(
            proof_seed_identity,
            "retained FD provenance proof seed",
        )
        proof_final = contract.validate_full_identity(
            proof_final_identity,
            "retained FD provenance proof final",
        )
        translation_tool = contract.validate_full_identity(
            translation_tool_identity,
            "retained FD provenance translation tool",
        )
        translation_tool_final = contract.validate_full_identity(
            translation_tool_final_identity,
            "retained FD provenance translation tool final",
        )
    except Exception as exc:
        raise PayloadError(f"retained FD provenance identity failed: {exc}") from exc
    require(formula_final == formula_write, "retained FD provenance: formula identity drifted")
    require(
        translation_tool_final == translation_tool,
        "retained FD provenance: translation tool identity drifted",
    )
    require(
        proof_seed["size_bytes"] == 0
        and proof_seed["sha256"] == hashlib.sha256(b"").hexdigest(),
        "retained FD provenance: proof seed is not the exclusive empty file",
    )
    for field in ("path", "mode_octal", "device", "inode", "link_count"):
        require(
            proof_final[field] == proof_seed[field],
            f"retained FD provenance: proof {field} drifted",
        )
    require(
        0 < proof_final["size_bytes"] <= PROOF_LIMIT,
        "retained FD provenance: proof final size invalid",
    )
    return {
        "schema_version": RETAINED_FD_PROVENANCE_SCHEMA,
        "formula": {
            "write_once_identity": formula_write,
            "retained_open_access": "read_only",
            "validated_after_write_from_retained_fd": True,
            "roundingsat_input_transport": "proc_self_fd",
            "veripb_input_transport": "proc_self_fd",
            "same_parent_fd_retained_through_both_processes": True,
            "final_same_fd_identity": formula_final,
        },
        "proof": {
            "exclusive_create_identity": proof_seed,
            "retained_open_access": "read_write_output",
            "created_with_o_excl": True,
            "roundingsat_proof_log_transport": "proc_self_fd",
            "size_monitor_source": "same_retained_fd_fstat",
            "post_solver_read_source": "same_retained_fd_pread",
            "veripb_input_transport": "same_retained_fd_proc_self_fd",
            "same_parent_fd_retained_through_both_processes": True,
            "final_same_fd_identity": proof_final,
        },
        "translation_tool": {
            "source_identity": translation_tool,
            "retained_open_access": "read_only",
            "python_script_transport": "same_retained_fd_bootstrap",
            "child_full7_revalidation": True,
            "self_identity_read_redirected_to_same_retained_fd": True,
            "executed_from_validated_source_fd": True,
            "final_same_fd_identity": translation_tool_final,
        },
        "content_reopened_by_path_after_retained_validation": False,
    }


def open_exclusive_output(path: Path) -> int:
    return os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )


def terminate_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=30)


def run_timed(
    argv: list[str],
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
    *,
    pass_fds: tuple[int, ...],
) -> tuple[int, int]:
    stdout_fd = open_exclusive_output(stdout_path)
    try:
        stderr_fd = open_exclusive_output(stderr_path)
    except BaseException:
        os.close(stdout_fd)
        raise
    started = time.monotonic()
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            argv,
            stdout=stdout_fd,
            stderr=stderr_fd,
            start_new_session=True,
            pass_fds=pass_fds,
        )
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            terminate_group(process)
            raise PayloadError(f"subprocess exceeded {timeout_seconds} seconds") from exc
    finally:
        if process is not None and process.poll() is None:
            terminate_group(process)
        os.close(stdout_fd)
        os.close(stderr_fd)
    return exit_code, round((time.monotonic() - started) * 1000)


def proof_size(record: dict[str, Any]) -> int:
    retained = _validate_retained_record(record, "proof target")
    require(
        retained["access"] == "read_write_output",
        "proof target: retained FD is not a writable output",
    )
    _verify_retained_path_binding(retained, "proof target")
    current = os.fstat(retained["fd"])
    require(stat.S_ISREG(current.st_mode), "proof target stopped being regular")
    require(
        _same_retained_anchor(retained["before"], current),
        "proof target retained FD anchor changed",
    )
    return current.st_size


def run_roundingsat(
    argv: list[str],
    stdout_path: Path,
    stderr_path: Path,
    proof_record: dict[str, Any],
    *,
    pass_fds: tuple[int, ...],
) -> tuple[int, int, str | None]:
    stdout_fd = open_exclusive_output(stdout_path)
    try:
        stderr_fd = open_exclusive_output(stderr_path)
    except BaseException:
        os.close(stdout_fd)
        raise
    proof_size(proof_record)
    started = time.monotonic()
    process: subprocess.Popen[bytes] | None = None
    stop_reason: str | None = None
    try:
        process = subprocess.Popen(
            argv,
            stdout=stdout_fd,
            stderr=stderr_fd,
            start_new_session=True,
            pass_fds=pass_fds,
        )
        while process.poll() is None:
            elapsed = time.monotonic() - started
            if elapsed > ROUNDINGSAT_MONITOR_SECONDS:
                stop_reason = "roundingsat_monitor_timeout"
            else:
                try:
                    if proof_size(proof_record) > PROOF_LIMIT:
                        stop_reason = "proof_size_limit_exceeded"
                except (OSError, PayloadError):
                    stop_reason = "proof_target_identity_failed"
            if stop_reason is not None:
                terminate_group(process)
                break
            time.sleep(0.05)
        exit_code = process.wait(timeout=30)
    finally:
        if process is not None and process.poll() is None:
            terminate_group(process)
        os.close(stdout_fd)
        os.close(stderr_fd)
    return (
        exit_code,
        round((time.monotonic() - started) * 1000),
        stop_reason,
    )


def add_member(
    members: dict[str, dict[str, Any]],
    output_dir: Path,
    identity: dict[str, Any],
) -> None:
    path = Path(identity["path"])
    try:
        relative = path.relative_to(output_dir)
    except ValueError as exc:
        raise PayloadError("manifest member escaped output directory") from exc
    name = relative.as_posix()
    require(name not in members, f"duplicate manifest member {name}")
    members[name] = identity


def validate_historical_semantics(
    pb_authority: dict[str, Any],
    geometry: dict[str, Any],
    translation: dict[str, Any],
    strict_instance: dict[str, Any],
) -> None:
    require(
        pb_authority.get("schema_version") == "b1_sidewise_pb_pre_run_authority_v1"
        and pb_authority.get("status") == "PB_PRE_RUN_AUTHORITY_PASS",
        "historical PB authority semantics failed",
    )
    require(
        geometry.get("schema_version") == "b1_sidewise_geometry_admission_v1"
        and geometry.get("status") == "PASS"
        and geometry.get("decision") == "ADMITTED_FOR_PB_ENCODER",
        "historical geometry admission semantics failed",
    )
    require(
        translation.get("schema_version") == "b1_sidewise_ceiling_translation_gate_v1"
        and translation.get("status") == "PASS"
        and translation.get("decision") == "FORMAL_RUN_AUTHORIZED"
        and translation.get("formal_run_authorized") is True
        and translation.get("corpus_errors") == []
        and all(translation.get("checks", {}).values()),
        "historical translation gate semantics failed",
    )
    require(bool(strict_instance), "strict instance is empty")


def formal_timing_contract() -> dict[str, int]:
    return {
        "runtime_max_seconds": RUNTIME_MAX_SECONDS,
        "payload_wait_seconds": PAYLOAD_WAIT_SECONDS,
        "keeper_timeout_seconds": KEEPER_TIMEOUT_SECONDS,
        "roundingsat_time_limit_seconds": ROUNDINGSAT_SECONDS,
        "roundingsat_monitor_limit_seconds": ROUNDINGSAT_MONITOR_SECONDS,
        "veripb_time_limit_seconds": VERIPB_SECONDS,
    }


def validate_resource_contract(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict), "SMM4 authority resource contract missing")
    expected = {
        "memory_high_bytes": 35 * 1024**3,
        "memory_max_bytes": 39 * 1024**3,
        "memory_swap_max_bytes": 16 * 1024**3,
        "oom_policy": "continue",
        "kill_mode": "control-group",
        "send_sigkill": "yes",
        "single_worker": True,
        "proof_limit_bytes": PROOF_LIMIT,
        "artifact_low_water_bytes": LOW_WATER,
        "required_free_before_formal_bytes": REQUIRED_FREE,
        "formal_attempt_limit": 1,
        "formal_runtime_max_seconds": RUNTIME_MAX_SECONDS,
        "formal_payload_wait_seconds": PAYLOAD_WAIT_SECONDS,
        "formal_keeper_timeout_seconds": KEEPER_TIMEOUT_SECONDS,
        "formal_roundingsat_time_limit_seconds": ROUNDINGSAT_SECONDS,
        "formal_roundingsat_monitor_limit_seconds": ROUNDINGSAT_MONITOR_SECONDS,
        "formal_veripb_time_limit_seconds": VERIPB_SECONDS,
    }
    for name, expected_value in expected.items():
        require(value.get(name) == expected_value, f"resource contract drifted: {name}")
    return dict(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--authority-package-id", required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-systemd-unit", required=True)
    args = parser.parse_args()
    args.output_dir = args.output_dir.absolute()

    output_created = False
    python_pin: dict[str, Any] | None = None
    roundingsat_pin: dict[str, Any] | None = None
    veripb_pin: dict[str, Any] | None = None
    translation_tool_pin: dict[str, Any] | None = None
    formula_pin: dict[str, Any] | None = None
    proof_pin: dict[str, Any] | None = None
    try:
        (
            authority,
            authority_identity,
            authority_raw,
            authority_seal_identity,
        ) = load_sealed_authority(
            args.authority,
            args.authority_package_id,
        )
        require(
            authority.get("schema_version") == AUTHORITY_SCHEMA,
            "SMM4 authority schema mismatch",
        )
        run_nonce = authority.get("run_nonce")
        require(
            isinstance(run_nonce, str) and bool(run_nonce),
            "SMM4 authority run nonce missing",
        )
        resource_contract = validate_resource_contract(authority.get("resource_contract"))
        timing_contract = formal_timing_contract()
        tools = authority.get("tools")
        require(isinstance(tools, dict), "authority tools missing")
        identity_module = load_identity_contract(
            tools.get("identity_contract"),
            "canonical content identity contract",
        )
        selection, selection_identity, selection_raw = load_json(
            args.selection,
            "SMM4 selection",
        )
        require(
            selection.get("schema_version") == SELECTION_SCHEMA
            and selection.get("status") == "SELECTED_CONSUMED"
            and selection.get("attempt") == ATTEMPT
            and selection.get("purpose") == "formal"
            and selection.get("run_nonce") == run_nonce
            and selection.get("authority_package_id")
            == args.authority_package_id
            and selection.get("unit") == args.expected_systemd_unit
            and selection.get("worker_argv") == sys.argv,
            "SMM4 selection semantics or argv mismatch",
        )
        validate_selection_authority_join(
            identity_module,
            selection,
            authority_identity,
        )
        require(
            isinstance(selection.get("formal_admission"), dict),
            "SMM4 formal selection lacks admission identity",
        )
        require(
            selection.get("resource_contract") == resource_contract
            and selection.get("timing_contract") == timing_contract,
            "SMM4 selection budget contract mismatch",
        )
        formal_admission_raw, formal_admission_identity = snapshot_pinned(
            selection.get("formal_admission"),
            "formal admission",
            max_bytes=JSON_LIMIT,
        )
        require(
            formal_admission_raw is not None,
            "formal admission source bytes missing",
        )
        formal_admission = strict_json(
            formal_admission_raw,
            "formal admission",
        )
        require(
            isinstance(formal_admission, dict)
            and formal_admission.get("schema_version")
            == "b1_sidewise_smm4_formal_admission_v1"
            and formal_admission.get("status") == "FORMAL_ADMISSION_PASS"
            and formal_admission.get("formal_attempt") == ATTEMPT
            and formal_admission.get("authority_package_id")
            == args.authority_package_id
            and formal_admission.get("formal_attempt_selected") is False
            and formal_admission.get("upper_bound_update_authorized") is False,
            "formal admission semantics failed",
        )
        inputs = authority.get("inputs")
        binaries = authority.get("binaries")
        require(isinstance(inputs, dict), "authority inputs missing")
        require(isinstance(binaries, dict), "authority binaries missing")
        orchestrator = load_pinned_module(
            tools.get("orchestrator"),
            "SMM4 authority orchestrator",
        )
        try:
            old_upper_replay = orchestrator.replay_old_upper(authority)
            composition_replay = orchestrator.replay_composition(authority)
        except Exception as exc:
            raise PayloadError(f"formal authority composition replay failed: {exc}") from exc
        require(
            formal_admission.get("old_upper_replay") == old_upper_replay
            and formal_admission.get("composition_replay") == composition_replay,
            "formal admission composition closure drifted",
        )

        _, self_identity = snapshot_regular(
            Path(__file__).resolve(strict=True),
            "formal payload",
            max_bytes=JSON_LIMIT,
        )
        match_identity(
            self_identity,
            tools.get("formal_payload"),
            "formal payload",
        )

        pb_raw, pb_identity = snapshot_pinned(
            inputs.get("pb_authority"),
            "historical PB authority",
            max_bytes=JSON_LIMIT,
        )
        geometry_raw, geometry_identity = snapshot_pinned(
            inputs.get("geometry_admission"),
            "historical geometry admission",
            max_bytes=JSON_LIMIT,
        )
        strict_raw, strict_identity = snapshot_pinned(
            inputs.get("strict_instance"),
            "strict instance",
            max_bytes=JSON_LIMIT,
        )
        translation_raw, translation_identity = snapshot_pinned(
            inputs.get("translation_gate"),
            "historical translation gate",
            max_bytes=JSON_LIMIT,
        )
        require(
            all(
                raw is not None
                for raw in (
                    pb_raw,
                    geometry_raw,
                    strict_raw,
                    translation_raw,
                )
            ),
            "historical input snapshot failed",
        )
        pb_payload = strict_json(pb_raw, "historical PB authority")
        geometry_payload = strict_json(
            geometry_raw,
            "historical geometry admission",
        )
        strict_payload = strict_json(strict_raw, "strict instance")
        translation_payload = strict_json(
            translation_raw,
            "historical translation gate",
        )
        require(
            all(
                isinstance(value, dict)
                for value in (
                    pb_payload,
                    geometry_payload,
                    strict_payload,
                    translation_payload,
                )
            ),
            "historical JSON root type failed",
        )
        validate_historical_semantics(
            pb_payload,
            geometry_payload,
            translation_payload,
            strict_payload,
        )

        build_expected = inputs.get("build_files")
        require(
            isinstance(build_expected, dict) and set(build_expected) == set(BUILD_MEMBERS),
            "authority build file set mismatch",
        )
        build_raw: dict[str, bytes] = {}
        build_identities: dict[str, dict[str, Any]] = {}
        build_parents: set[Path] = set()
        for name in BUILD_MEMBERS:
            raw, identity = snapshot_pinned(
                build_expected[name],
                f"historical build {name}",
                max_bytes=JSON_LIMIT,
            )
            require(raw is not None, f"historical build {name}: snapshot failed")
            build_raw[name] = raw
            build_identities[name] = identity
            build_parents.add(Path(identity["path"]).parent)
        require(len(build_parents) == 1, "historical build files are split")
        require(
            len(build_raw["formula.opb"]) == FORMULA_SIZE and sha256(build_raw["formula.opb"]) == FORMULA_SHA256,
            "historical formula identity mismatch",
        )

        translation_tool_raw, translation_tool_pin = pin_retained_regular(
            tools.get("translation_gate"),
            "translation gate tool",
            max_bytes=JSON_LIMIT,
        )
        require(
            translation_tool_raw is not None,
            "translation gate tool snapshot failed",
        )
        translation_tool_identity = translation_tool_pin["identity"]
        python_pin = pin_executable(
            binaries.get("fixed_python"),
            "fixed Python",
        )
        roundingsat_pin = pin_executable(
            binaries.get("roundingsat"),
            "RoundingSat",
        )
        veripb_pin = pin_executable(
            binaries.get("veripb"),
            "VeriPB",
        )

        require(
            args.output_dir.parent.is_dir() and not args.output_dir.parent.is_symlink(),
            "formal output parent is not a real directory",
        )
        make_directory(args.output_dir, "formal output directory")
        output_created = True
        snapshot_dir = args.output_dir / "inputs.snapshot"
        build_snapshot_dir = snapshot_dir / "build"
        make_directory(snapshot_dir, "input snapshot directory")
        make_directory(build_snapshot_dir, "build snapshot directory")
        members: dict[str, dict[str, Any]] = {}

        snapshot_identities: dict[str, Any] = {}
        for name, raw, identity in (
            ("pb_authority.json", pb_raw, pb_identity),
            ("geometry_admission.json", geometry_raw, geometry_identity),
            ("strict_instance.json", strict_raw, strict_identity),
            (
                "translation_gate.previous.json",
                translation_raw,
                translation_identity,
            ),
            (
                "translation_gate.py",
                translation_tool_raw,
                translation_tool_identity,
            ),
        ):
            output_identity = write_once(
                snapshot_dir / name,
                raw,
                mode=mode_from_identity(identity, name),
            )
            snapshot_identities[name] = output_identity
            add_member(members, args.output_dir, output_identity)
        snapshot_identities["build"] = {}
        for name in BUILD_MEMBERS:
            output_identity = write_once(
                build_snapshot_dir / name,
                build_raw[name],
                mode=mode_from_identity(build_identities[name], name),
            )
            snapshot_identities["build"][name] = output_identity
            add_member(members, args.output_dir, output_identity)

        authority_snapshot_identity = write_once(
            snapshot_dir / "smm4_authority.json",
            authority_raw,
        )
        selection_snapshot_identity = write_once(
            snapshot_dir / "smm4-formal-a004-selection.json",
            selection_raw,
        )
        add_member(members, args.output_dir, authority_snapshot_identity)
        add_member(members, args.output_dir, selection_snapshot_identity)

        formula_path = args.output_dir / "formula.opb"
        formula_identity = write_once(
            formula_path,
            build_raw["formula.opb"],
        )
        _, formula_pin = pin_retained_regular(
            formula_identity,
            "formal formula retained FD",
            collect=False,
            max_bytes=FORMULA_SIZE,
        )
        add_member(members, args.output_dir, formula_identity)

        cgroup_receipt = verify_current_cgroup(args.expected_systemd_unit)

        translation_output = args.output_dir / "translation_gate.recheck.json"
        translation_stdout = args.output_dir / "translation_recheck.stdout.txt"
        translation_stderr = args.output_dir / "translation_recheck.stderr.txt"
        translation_arguments = [
            "--pb-authority",
            str(snapshot_dir / "pb_authority.json"),
            "--geometry-admission",
            str(snapshot_dir / "geometry_admission.json"),
            "--instance",
            str(snapshot_dir / "strict_instance.json"),
            "--build-dir",
            str(build_snapshot_dir),
            "--output",
            str(translation_output),
        ]
        translation_argv, translation_pass_fds = translation_fd_invocation(
            python_pin,
            translation_tool_pin,
            translation_arguments,
        )
        translation_exit, translation_elapsed = run_timed(
            translation_argv,
            translation_stdout,
            translation_stderr,
            TRANSLATION_SECONDS,
            pass_fds=translation_pass_fds,
        )
        require(translation_exit == 0, "translation replay exited nonzero")
        translation_recheck, translation_recheck_identity, _ = load_json(
            translation_output,
            "translation replay",
        )
        require(
            translation_recheck.get("schema_version") == "b1_sidewise_ceiling_translation_gate_v1"
            and translation_recheck.get("status") == "PASS"
            and translation_recheck.get("decision") == "FORMAL_RUN_AUTHORIZED"
            and translation_recheck.get("formal_run_authorized") is True
            and translation_recheck.get("corpus_errors") == []
            and all(translation_recheck.get("checks", {}).values()),
            "translation replay semantics failed",
        )
        add_member(members, args.output_dir, translation_recheck_identity)
        for path, label in (
            (translation_stdout, "translation stdout"),
            (translation_stderr, "translation stderr"),
        ):
            _, identity = snapshot_regular(
                path,
                label,
                collect=False,
            )
            add_member(members, args.output_dir, identity)
        verify_pinned_executable(python_pin, "fixed Python")
        translation_tool_final_identity = verify_retained_unchanged(
            translation_tool_pin,
            translation_tool_identity,
            "translation gate tool final replay",
            max_bytes=JSON_LIMIT,
        )

        available_before_solver = free_bytes(args.output_dir)
        require(
            available_before_solver >= REQUIRED_FREE,
            "disk gate failed before RoundingSat",
        )
        proof_path = args.output_dir / "roundingsat.proof.pbp"
        proof_pin = create_retained_output(
            proof_path,
            "RoundingSat proof retained output",
        )
        proof_seed_identity = proof_pin["identity"]
        solver_stdout = args.output_dir / "roundingsat.stdout.txt"
        solver_stderr = args.output_dir / "roundingsat.stderr.txt"
        solver_logical_argv = [
            roundingsat_pin["logical_path"],
            f"--proof-log={proof_path}",
            f"--time-limit={ROUNDINGSAT_SECONDS}",
            str(formula_path),
        ]
        solver_argv, solver_pass_fds = roundingsat_fd_invocation(
            roundingsat_pin,
            formula_pin,
            proof_pin,
        )
        solver_exit, solver_elapsed, solver_stop = run_roundingsat(
            solver_argv,
            solver_stdout,
            solver_stderr,
            proof_pin,
            pass_fds=solver_pass_fds,
        )
        require(solver_stop is None, f"RoundingSat stopped: {solver_stop}")
        require(solver_exit == 0, "RoundingSat exited nonzero")
        solver_stdout_raw, solver_stdout_identity = snapshot_regular(
            solver_stdout,
            "RoundingSat stdout",
            max_bytes=TEXT_LIMIT,
        )
        _, solver_stderr_identity = snapshot_regular(
            solver_stderr,
            "RoundingSat stderr",
            collect=False,
        )
        require(
            solver_stdout_raw is not None,
            "RoundingSat stdout snapshot failed",
        )
        solver_statuses = [
            match.group(1)
            for line in solver_stdout_raw.decode(
                "utf-8",
                errors="replace",
            ).splitlines()
            if (match := ROUNDINGSAT_STATUS.fullmatch(line)) is not None
        ]
        require(
            solver_statuses == ["UNSATISFIABLE"],
            "RoundingSat status protocol failed",
        )
        _, proof_identity = snapshot_retained_regular(
            proof_pin,
            "RoundingSat proof",
            collect=False,
            max_bytes=PROOF_LIMIT,
        )
        require(
            0 < proof_identity["size_bytes"] <= PROOF_LIMIT,
            "RoundingSat proof is empty or over cap",
        )
        add_member(members, args.output_dir, solver_stdout_identity)
        add_member(members, args.output_dir, solver_stderr_identity)
        add_member(members, args.output_dir, proof_identity)
        verify_pinned_executable(roundingsat_pin, "RoundingSat")
        verify_retained_unchanged(
            formula_pin,
            formula_identity,
            "formal formula after RoundingSat",
            max_bytes=FORMULA_SIZE,
        )
        require(
            free_bytes(args.output_dir) >= LOW_WATER,
            "artifact low-water crossed after RoundingSat",
        )

        verifier_stdout = args.output_dir / "veripb.stdout.txt"
        verifier_stderr = args.output_dir / "veripb.stderr.txt"
        verifier_logical_argv = [
            veripb_pin["logical_path"],
            "--opb",
            "--stats",
            str(formula_path),
            str(proof_path),
        ]
        verifier_argv, verifier_pass_fds = veripb_fd_invocation(
            veripb_pin,
            formula_pin,
            proof_pin,
            proof_identity,
        )
        verifier_exit, verifier_elapsed = run_timed(
            verifier_argv,
            verifier_stdout,
            verifier_stderr,
            VERIPB_SECONDS,
            pass_fds=verifier_pass_fds,
        )
        verifier_stdout_raw, verifier_stdout_identity = snapshot_regular(
            verifier_stdout,
            "VeriPB stdout",
            max_bytes=TEXT_LIMIT,
        )
        verifier_stderr_raw, verifier_stderr_identity = snapshot_regular(
            verifier_stderr,
            "VeriPB stderr",
            max_bytes=TEXT_LIMIT,
        )
        require(
            verifier_stdout_raw is not None and verifier_stderr_raw is not None,
            "VeriPB output snapshot failed",
        )
        verifier_text = verifier_stdout_raw.decode(
            "utf-8",
            errors="replace",
        )
        verifier_lines = [line for line in verifier_text.splitlines() if line.startswith("s ")]
        require(verifier_exit == 0, "VeriPB exited nonzero")
        require(
            len(verifier_lines) == 1 and VERIPB_SUCCESS.fullmatch(verifier_lines[0]) is not None,
            "VeriPB did not uniquely verify UNSAT",
        )
        combined_verifier = verifier_text + "\n" + verifier_stderr_raw.decode("utf-8", errors="replace")
        require(
            not any(marker in combined_verifier for marker in VERIPB_ERROR_MARKERS),
            "VeriPB output contains an error marker",
        )
        add_member(members, args.output_dir, verifier_stdout_identity)
        add_member(members, args.output_dir, verifier_stderr_identity)
        verify_pinned_executable(veripb_pin, "VeriPB")
        formula_final_identity = verify_retained_unchanged(
            formula_pin,
            formula_identity,
            "formal formula after VeriPB",
            max_bytes=FORMULA_SIZE,
        )
        proof_final_identity = verify_retained_unchanged(
            proof_pin,
            proof_identity,
            "formal proof after VeriPB",
            max_bytes=PROOF_LIMIT,
        )
        require(
            free_bytes(args.output_dir) >= LOW_WATER,
            "artifact low-water crossed after VeriPB",
        )

        (
            _,
            current_authority_identity,
            _,
            current_authority_seal_identity,
        ) = load_sealed_authority(
            args.authority,
            args.authority_package_id,
        )
        _, current_selection_identity = snapshot_regular(
            args.selection,
            "SMM4 selection final replay",
            collect=False,
        )
        require(
            current_authority_identity == authority_identity,
            "SMM4 authority drifted during payload",
        )
        require(
            current_authority_seal_identity == authority_seal_identity,
            "SMM4 authority seal drifted during payload",
        )
        require(
            current_selection_identity == selection_identity,
            "SMM4 selection drifted during payload",
        )
        _, current_formal_admission_identity = snapshot_pinned(
            selection.get("formal_admission"),
            "formal admission final replay",
            collect=False,
        )
        require(
            current_formal_admission_identity == formal_admission_identity,
            "formal admission drifted during payload",
        )
        for name in BUILD_MEMBERS:
            _, current = snapshot_pinned(
                build_expected[name],
                f"historical build {name} final replay",
                collect=False,
            )
            require(
                current == build_identities[name],
                f"historical build {name} drifted during payload",
            )

        receipt = {
            "schema_version": RECEIPT_SCHEMA,
            "status": "VERIFIED",
            "attempt": ATTEMPT,
            "purpose": "formal",
            "run_nonce": run_nonce,
            "proof_status": "VERIFIED UNSATISFIABLE",
            "claim": ("machine_verified_two_oriented_ceiling_selectors_unsat_given_admitted_smm209"),
            "expected_systemd_unit": args.expected_systemd_unit,
            "completed_monotonic_ns": time.monotonic_ns(),
            "resource_contract": resource_contract,
            "timing_contract": timing_contract,
            "cgroup_membership": cgroup_receipt,
            "inputs": {
                "authority": authority_identity,
                "authority_seal": authority_seal_identity,
                "authority_package_id": args.authority_package_id,
                "selection": selection_identity,
                "formal_admission": formal_admission_identity,
                "historical_pb_authority": pb_identity,
                "historical_geometry_admission": geometry_identity,
                "strict_instance": strict_identity,
                "historical_translation_gate": translation_identity,
                "historical_build_files": build_identities,
                "execution_snapshots": snapshot_identities,
                "translation_recheck": translation_recheck_identity,
            },
            "tools": {
                "formal_payload": self_identity,
                "translation_gate": translation_tool_identity,
                "fixed_python": {
                    "logical_path": python_pin["logical_path"],
                    "target": python_pin["identity"],
                    "execution": "pinned_fd",
                },
                "roundingsat": {
                    "logical_path": roundingsat_pin["logical_path"],
                    "target": roundingsat_pin["identity"],
                    "execution": "pinned_fd",
                },
                "veripb": {
                    "logical_path": veripb_pin["logical_path"],
                    "target": veripb_pin["identity"],
                    "execution": "pinned_fd",
                },
            },
            "formula": formula_identity,
            "proof": proof_identity,
            "retained_fd_provenance": retained_fd_provenance(
                formula_write_identity=formula_identity,
                formula_final_identity=formula_final_identity,
                proof_seed_identity=proof_seed_identity,
                proof_final_identity=proof_final_identity,
                translation_tool_identity=translation_tool_identity,
                translation_tool_final_identity=translation_tool_final_identity,
            ),
            "translation_replay": {
                "logical_argv": [
                    python_pin["logical_path"],
                    "-I",
                    translation_tool_pin["logical_path"],
                    *translation_arguments,
                ],
                "executed_from_pinned_fd": True,
                "tool_source_transport": "same_retained_fd_bootstrap",
                "child_full7_revalidation": True,
                "exit_code": translation_exit,
                "elapsed_milliseconds": translation_elapsed,
                "status": "PASS",
            },
            "old_upper_replay": old_upper_replay,
            "composition_replay": composition_replay,
            "solver": {
                "logical_argv": solver_logical_argv,
                "executed_from_pinned_fd": True,
                "formula_transport": "retained_fd_procfs",
                "proof_log_transport": "retained_fd_procfs",
                "proof_size_monitor": "same_retained_fd_fstat",
                "exit_code": solver_exit,
                "elapsed_milliseconds": solver_elapsed,
                "status_lines": solver_statuses,
                "time_limit_seconds": ROUNDINGSAT_SECONDS,
                "monitor_limit_seconds": ROUNDINGSAT_MONITOR_SECONDS,
            },
            "verifier": {
                "logical_argv": verifier_logical_argv,
                "executed_from_pinned_fd": True,
                "formula_transport": "same_retained_fd_procfs",
                "proof_transport": "same_retained_fd_procfs",
                "exit_code": verifier_exit,
                "elapsed_milliseconds": verifier_elapsed,
                "status_lines": verifier_lines,
                "time_limit_seconds": VERIPB_SECONDS,
            },
            "artifact_contract": {
                "proof_limit_bytes": PROOF_LIMIT,
                "low_water_bytes": LOW_WATER,
                "required_free_before_formal_bytes": REQUIRED_FREE,
                "free_before_solver_bytes": available_before_solver,
                "free_after_verifier_bytes": free_bytes(args.output_dir),
            },
            "ledger_candidate": {
                "old_upper": [1188, 22],
                "new_upper": [1188, 18],
                "lower": "absent",
            },
            "upper_bound_update_authorized": False,
            "awaiting_terminal_envelope": True,
            "production_certified": False,
        }
        receipt_raw = json_bytes(receipt)
        receipt_identity = write_once(
            args.output_dir / "internal_formal_receipt.json",
            receipt_raw,
        )
        add_member(members, args.output_dir, receipt_identity)
        manifest_raw = "".join(f"{members[name]['sha256']}  {name}\n" for name in sorted(members)).encode("ascii")
        write_once(args.output_dir / "SHA256SUMS", manifest_raw)
        result = {
            "status": "VERIFIED",
            "attempt": ATTEMPT,
            "proof_status": receipt["proof_status"],
            "internal_receipt": receipt_identity,
            "upper_bound_update_authorized": False,
            "awaiting_terminal_envelope": True,
        }
    except Exception as exc:
        failure = {
            "schema_version": "b1_sidewise_smm4_internal_formal_failure_v1",
            "status": "FAIL_CLOSED",
            "attempt": ATTEMPT,
            "error": str(exc),
            "upper_bound_update_authorized": False,
            "awaiting_terminal_envelope": False,
            "ledger": {"upper": [1188, 22], "lower": "absent"},
            "production_certified": False,
        }
        if output_created:
            failure_path = args.output_dir / "formal_failure.json"
            if not path_exists(failure_path):
                try:
                    write_once(failure_path, json_bytes(failure))
                except Exception:
                    pass
        print(json.dumps(failure, sort_keys=True))
        return 2
    finally:
        close_retained_regular(proof_pin)
        close_retained_regular(formula_pin)
        close_retained_regular(translation_tool_pin)
        close_pinned_executable(veripb_pin)
        close_pinned_executable(roundingsat_pin)
        close_pinned_executable(python_pin)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
