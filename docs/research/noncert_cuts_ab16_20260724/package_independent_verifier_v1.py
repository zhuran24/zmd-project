#!/usr/bin/env python3
"""Retained-FD, read-only verifier for one prospective AB16 package.

This file is a package-internal later role.  It is not a second ambient
pre-package executor: the bootstrap must first compare the actual package
member bytes with the externally pre-registered size and SHA-256, then execute
those bytes from the retained member descriptor.

The verifier has no project imports and accepts no output path.  It opens every
package descendant read-only through a retained package directory descriptor,
checks the verifier member against the external pin, installs a deny-all
Landlock filesystem ruleset, independently replays the package seal, manifest,
and complete descendant set, and returns one canonical result through a
pre-created pipe.
"""

from __future__ import annotations

import ctypes
import errno
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Mapping
from typing import Any


RESULT_SCHEMA = "noncert-cuts-ab16-campaign-package-independent-replay-v2"
PACKAGE_MANIFEST_SCHEMA = "noncert-cuts-campaign-authority-manifest-v5"
VERIFIER_PACKAGE_PATH = "payload/tool.package_independent_verifier_v1.py"
NATIVE_HELPER_PACKAGE_PATH = "payload/system.native_budget_helper.bin"
NATIVE_HELPER_WRAPPER_PACKAGE_PATH = "payload/tool.ab16_native_budget_helper_v1.py"
FINAL_RELEASE_ACTOR_PACKAGE_PATH = "payload/tool.ab16_final_release_actor_v1.py"
NATIVE_HELPER_SHA256 = (
    "65150434dc370596413e3e425e5cdcaa2d7960b8b181109f738588e8f40dca81"
)
NATIVE_HELPER_SIZE_BYTES = 16512
NATIVE_HELPER_SOURCE_MODE = 0o555
NATIVE_HELPER_BUILD_ID_SHA1 = "808dbb57b4fd260e704cb7399e76d76fef2e3146"
AUTHORITY_SCOPE = "AB16_RESEARCH_ONLY"

SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
ROLE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
MAX_JSON_BYTES = 128 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024

_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_STAT_FIELDS = (
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

# Linux assigns these Landlock calls in the architecture-independent new
# syscall range.  Unsupported kernels and non-Linux hosts fail closed.
_SYS_LANDLOCK_CREATE_RULESET = 444
_SYS_LANDLOCK_ADD_RULE = 445
_SYS_LANDLOCK_RESTRICT_SELF = 446
_LANDLOCK_CREATE_RULESET_VERSION = 1
_PR_SET_NO_NEW_PRIVS = 38


class PackageVerifierError(RuntimeError):
    """One package identity, closure, sandbox, or transport check failed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _LandlockRulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


def _fail(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise PackageVerifierError(code, message)


def _canonical_json(value: object) -> bytes:
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


def _strict_json(raw: bytes, label: str, *, require_canonical: bool = True) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise PackageVerifierError("JSON_DUPLICATE_KEY", f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject_float(value: str) -> object:
        raise PackageVerifierError("JSON_FLOAT_REJECTED", f"{label}: floating value {value!r}")

    def reject_constant(value: str) -> object:
        raise PackageVerifierError("JSON_CONSTANT_REJECTED", f"{label}: constant {value!r}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageVerifierError("JSON_INVALID", f"{label}: {exc}") from exc
    if require_canonical and _canonical_json(value) != raw:
        raise PackageVerifierError("JSON_NONCANONICAL", f"{label}: bytes are not canonical JSON")
    return value


def _exact_object(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise PackageVerifierError("SCHEMA_DRIFT", f"{label}: exact key set drifted")
    return dict(value)


def _record_fd(value: Mapping[str, object], label: str) -> int:
    descriptor = value.get("fd")
    if type(descriptor) is not int or descriptor < 0:
        raise PackageVerifierError("INTERNAL_VERIFIER_ERROR", f"{label}: retained descriptor is invalid")
    return descriptor


def _record_stat(value: Mapping[str, object], label: str) -> os.stat_result:
    metadata = value.get("stat")
    if not isinstance(metadata, os.stat_result):
        raise PackageVerifierError("INTERNAL_VERIFIER_ERROR", f"{label}: retained stat is invalid")
    return metadata


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
    return tuple(int(getattr(value, field)) for field in _STAT_FIELDS)


def _same_object(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _safe_relative(value: object, label: str) -> str:
    if type(value) is not str or not value or value.startswith("/") or "\\" in value:
        raise PackageVerifierError("PATH_INVALID", f"{label}: unsafe relative path")
    parts = value.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise PackageVerifierError("PATH_INVALID", f"{label}: unsafe relative path")
    normalized = "/".join(parts)
    if normalized != value:
        raise PackageVerifierError("PATH_INVALID", f"{label}: noncanonical relative path")
    return value


def _pread_all(descriptor: int, expected_size: int, label: str, *, limit: int | None = None) -> bytes:
    if limit is not None and expected_size > limit:
        raise PackageVerifierError("INPUT_SIZE_LIMIT", f"{label}: input exceeds fixed limit")
    chunks: list[bytes] = []
    offset = 0
    while offset < expected_size:
        block = os.pread(descriptor, min(READ_CHUNK_BYTES, expected_size - offset), offset)
        if not block:
            raise PackageVerifierError("INPUT_RACE", f"{label}: retained descriptor was truncated")
        chunks.append(block)
        offset += len(block)
    if os.pread(descriptor, 1, expected_size):
        raise PackageVerifierError("INPUT_RACE", f"{label}: retained descriptor grew")
    return b"".join(chunks)


def _hash_fd(descriptor: int, expected_size: int, label: str) -> str:
    digest = hashlib.sha256()
    offset = 0
    while offset < expected_size:
        block = os.pread(descriptor, min(READ_CHUNK_BYTES, expected_size - offset), offset)
        if not block:
            raise PackageVerifierError("INPUT_RACE", f"{label}: retained descriptor was truncated")
        digest.update(block)
        offset += len(block)
    if os.pread(descriptor, 1, expected_size):
        raise PackageVerifierError("INPUT_RACE", f"{label}: retained descriptor grew")
    return digest.hexdigest()


def _require_read_only(descriptor: int, label: str) -> None:
    try:
        flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
    except OSError as exc:
        raise PackageVerifierError("FD_INVALID", f"{label}: cannot inspect descriptor: {exc}") from exc
    if flags & os.O_ACCMODE != os.O_RDONLY:
        raise PackageVerifierError("WRITABLE_FD_REJECTED", f"{label}: descriptor is not read-only")


def _validate_result_pipe(descriptor: int) -> None:
    try:
        metadata = os.fstat(descriptor)
        flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
    except OSError as exc:
        raise PackageVerifierError("RESULT_TRANSPORT_INVALID", f"result descriptor is invalid: {exc}") from exc
    if not stat.S_ISFIFO(metadata.st_mode) or flags & os.O_ACCMODE not in {os.O_WRONLY, os.O_RDWR}:
        raise PackageVerifierError(
            "RESULT_TRANSPORT_INVALID",
            "result descriptor must be a pre-created writable pipe",
        )


def _open_fd_set() -> set[int]:
    try:
        names = os.listdir("/proc/self/fd")
    except OSError as exc:
        raise PackageVerifierError("PROC_FD_UNAVAILABLE", f"cannot enumerate /proc/self/fd: {exc}") from exc
    result: set[int] = set()
    for name in names:
        if not name.isdecimal():
            raise PackageVerifierError("PROC_FD_INVALID", "non-decimal /proc/self/fd member")
        descriptor = int(name)
        try:
            os.fstat(descriptor)
        except OSError as exc:
            if exc.errno == errno.EBADF:
                continue
            raise PackageVerifierError("PROC_FD_INVALID", f"cannot inspect descriptor {descriptor}: {exc}") from exc
        result.add(descriptor)
    return result


def _require_exact_fd_surface(allowed: set[int]) -> None:
    actual = _open_fd_set()
    extra = sorted(actual - allowed)
    missing = sorted(allowed - actual)
    if extra or missing:
        raise PackageVerifierError(
            "FD_SURFACE_DRIFT",
            f"descriptor surface drifted: extra={extra} missing={missing}",
        )
    for descriptor in (1, 2):
        metadata = os.fstat(descriptor)
        if stat.S_ISREG(metadata.st_mode):
            raise PackageVerifierError(
                "WRITABLE_PATH_FD_REJECTED",
                f"stdio descriptor {descriptor} is a regular output path",
            )


def _origin_candidates(module: object) -> list[str]:
    result: list[str] = []
    origin = getattr(module, "__file__", None)
    if isinstance(origin, str):
        result.append(origin)
    package_path = getattr(module, "__path__", None)
    if package_path is not None:
        try:
            entries = list(package_path)
        except TypeError as exc:
            raise PackageVerifierError("AMBIENT_MODULE_REJECTED", "module __path__ is malformed") from exc
        if any(not isinstance(entry, str) for entry in entries):
            raise PackageVerifierError("AMBIENT_MODULE_REJECTED", "module __path__ contains non-string entry")
        result.extend(entries)
    return result


def _reject_ambient_modules(verifier_fd: int) -> None:
    verifier_origins = {f"/proc/self/fd/{verifier_fd}", f"/dev/fd/{verifier_fd}"}
    main_module = sys.modules.get("__main__")
    if main_module is None or getattr(main_module, "__file__", None) not in verifier_origins:
        raise PackageVerifierError("EXECUTING_VERIFIER_DRIFT", "verified package verifier is not current __main__")

    stdlib_root = os.path.realpath(os.path.dirname(os.__file__))
    for name, module in tuple(sys.modules.items()):
        if module is None:
            continue
        for origin in _origin_candidates(module):
            if name == "__main__" and origin in verifier_origins:
                continue
            if origin in {"built-in", "frozen"}:
                continue
            if not os.path.isabs(origin):
                raise PackageVerifierError(
                    "AMBIENT_MODULE_REJECTED",
                    f"module {name!r} has non-absolute origin {origin!r}",
                )
            normalized = os.path.realpath(origin)
            if (
                os.path.commonpath((stdlib_root, normalized)) != stdlib_root
                or "/site-packages/" in f"/{normalized.lstrip('/')}"
                or "/dist-packages/" in f"/{normalized.lstrip('/')}"
            ):
                raise PackageVerifierError(
                    "AMBIENT_MODULE_REJECTED",
                    f"module {name!r} originated outside the standard library",
                )
    for entry in sys.path:
        if not isinstance(entry, str) or not entry or not os.path.isabs(entry):
            raise PackageVerifierError("AMBIENT_SEARCH_PATH_REJECTED", "sys.path contains a non-absolute entry")
        normalized = os.path.realpath(entry)
        # The stdlib zip path may not exist, but is still beneath the interpreter
        # library parent.
        allowed_parent = os.path.dirname(stdlib_root)
        if os.path.commonpath((allowed_parent, normalized)) != allowed_parent:
            raise PackageVerifierError(
                "AMBIENT_SEARCH_PATH_REJECTED",
                f"sys.path entry is outside the interpreter standard library: {entry}",
            )


def _entry_name(name: object) -> str:
    if type(name) is not str or not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise PackageVerifierError("PATH_INVALID", "package directory contains an unsafe entry name")
    return name


def _scan_open_tree(root_fd: int) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]], list[int]]:
    root_stat = os.fstat(root_fd)
    if not stat.S_ISDIR(root_stat.st_mode):
        raise PackageVerifierError("PACKAGE_ROOT_INVALID", "retained package root is not a directory")
    _require_read_only(root_fd, "package root")
    directories: dict[str, dict[str, object]] = {
        "": {
            "entries": (),
            "fd": root_fd,
            "owned": False,
            "stat": root_stat,
        }
    }
    files: dict[str, dict[str, object]] = {}
    owned: list[int] = []
    seen_file_objects: set[tuple[int, int]] = set()
    pending = [""]
    try:
        while pending:
            relative = pending.pop(0)
            directory = directories[relative]
            directory_fd = _record_fd(directory, relative or "package root")
            names = tuple(sorted(_entry_name(name) for name in os.listdir(directory_fd)))
            if len(set(names)) != len(names):
                raise PackageVerifierError("TREE_DRIFT", f"{relative or '.'}: duplicate directory entry")
            directory["entries"] = names
            for name in names:
                child_relative = f"{relative}/{name}" if relative else name
                named = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if stat.S_ISLNK(named.st_mode):
                    raise PackageVerifierError("SYMLINK_REJECTED", child_relative)
                if stat.S_ISDIR(named.st_mode):
                    descriptor = os.open(
                        name,
                        os.O_RDONLY | _O_CLOEXEC | _O_DIRECTORY | _O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                    owned.append(descriptor)
                    opened = os.fstat(descriptor)
                    if not _same_object(named, opened) or not stat.S_ISDIR(opened.st_mode):
                        raise PackageVerifierError("TREE_RACE", f"{child_relative}: directory identity drifted")
                    _require_read_only(descriptor, child_relative)
                    directories[child_relative] = {
                        "entries": (),
                        "fd": descriptor,
                        "owned": True,
                        "stat": opened,
                    }
                    pending.append(child_relative)
                elif stat.S_ISREG(named.st_mode):
                    if named.st_nlink != 1:
                        raise PackageVerifierError("HARDLINK_REJECTED", child_relative)
                    descriptor = os.open(
                        name,
                        os.O_RDONLY | _O_CLOEXEC | _O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                    owned.append(descriptor)
                    opened = os.fstat(descriptor)
                    if (
                        not _same_object(named, opened)
                        or not stat.S_ISREG(opened.st_mode)
                        or opened.st_nlink != 1
                    ):
                        raise PackageVerifierError("TREE_RACE", f"{child_relative}: file identity drifted")
                    _require_read_only(descriptor, child_relative)
                    object_id = (opened.st_dev, opened.st_ino)
                    if object_id in seen_file_objects:
                        raise PackageVerifierError("HARDLINK_REJECTED", child_relative)
                    seen_file_objects.add(object_id)
                    files[child_relative] = {
                        "fd": descriptor,
                        "parent": relative,
                        "name": name,
                        "stat": opened,
                    }
                else:
                    raise PackageVerifierError("SPECIAL_NODE_REJECTED", child_relative)
    except BaseException:
        for descriptor in reversed(owned):
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise
    return directories, files, owned


def _close_owned(descriptors: list[int]) -> None:
    first_error: OSError | None = None
    for descriptor in reversed(descriptors):
        try:
            os.close(descriptor)
        except OSError as exc:
            if first_error is None:
                first_error = exc
    if first_error is not None:
        raise PackageVerifierError("FD_CLOSE_FAILED", f"retained package descriptor close failed: {first_error}")


def _recheck_tree(
    directories: Mapping[str, Mapping[str, object]],
    files: Mapping[str, Mapping[str, object]],
) -> None:
    for relative, directory in directories.items():
        descriptor = _record_fd(directory, relative or "package root")
        before = _record_stat(directory, relative or "package root")
        after = os.fstat(descriptor)
        if _stat_signature(before) != _stat_signature(after):
            raise PackageVerifierError("TREE_RACE", f"{relative or '.'}: retained directory drifted")
        names = tuple(sorted(_entry_name(name) for name in os.listdir(descriptor)))
        if names != directory["entries"]:
            raise PackageVerifierError("TREE_RACE", f"{relative or '.'}: member set drifted")

    for relative, file_record in files.items():
        descriptor = _record_fd(file_record, relative)
        before = _record_stat(file_record, relative)
        after = os.fstat(descriptor)
        if _stat_signature(before) != _stat_signature(after):
            raise PackageVerifierError("TREE_RACE", f"{relative}: retained file drifted")
        parent = directories[str(file_record["parent"])]
        named = os.stat(
            str(file_record["name"]),
            dir_fd=_record_fd(parent, str(file_record["parent"]) or "package root"),
            follow_symlinks=False,
        )
        if _stat_signature(after) != _stat_signature(named):
            raise PackageVerifierError("TREE_RACE", f"{relative}: named file identity drifted")


def _landlock_abi() -> int:
    if sys.platform != "linux":
        raise PackageVerifierError("LANDLOCK_UNAVAILABLE", "Landlock requires Linux")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    result = libc.syscall(
        _SYS_LANDLOCK_CREATE_RULESET,
        ctypes.c_void_p(),
        ctypes.c_size_t(0),
        ctypes.c_uint(_LANDLOCK_CREATE_RULESET_VERSION),
    )
    if result < 0:
        error = ctypes.get_errno()
        raise PackageVerifierError(
            "LANDLOCK_UNAVAILABLE",
            f"Landlock ABI query failed: errno={error}",
        )
    return int(result)


def _handled_access_fs(abi: int) -> int:
    # ABI 1 rights, followed by REFER (ABI 2), TRUNCATE (ABI 3), and
    # IOCTL_DEV (ABI 5).  Network scopes are intentionally not requested.
    rights = (1 << 13) - 1
    if abi >= 2:
        rights |= 1 << 13
    if abi >= 3:
        rights |= 1 << 14
    if abi >= 5:
        rights |= 1 << 15
    return rights


def _install_landlock() -> dict[str, object]:
    abi = _landlock_abi()
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    libc.prctl.restype = ctypes.c_int
    handled = _handled_access_fs(abi)
    attributes = _LandlockRulesetAttr(handled_access_fs=handled)
    ruleset_fd = libc.syscall(
        _SYS_LANDLOCK_CREATE_RULESET,
        ctypes.byref(attributes),
        ctypes.sizeof(attributes),
        ctypes.c_uint(0),
    )
    if ruleset_fd < 0:
        error = ctypes.get_errno()
        raise PackageVerifierError("LANDLOCK_RULESET_FAILED", f"cannot create Landlock ruleset: errno={error}")
    try:
        if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            error = ctypes.get_errno()
            raise PackageVerifierError("LANDLOCK_NO_NEW_PRIVS_FAILED", f"prctl failed: errno={error}")
        if libc.syscall(_SYS_LANDLOCK_RESTRICT_SELF, ruleset_fd, ctypes.c_uint(0)) != 0:
            error = ctypes.get_errno()
            raise PackageVerifierError("LANDLOCK_RESTRICT_FAILED", f"restrict_self failed: errno={error}")
    finally:
        os.close(int(ruleset_fd))

    try:
        leaked = os.open("/", os.O_RDONLY | _O_CLOEXEC | _O_DIRECTORY)
    except OSError as exc:
        if exc.errno not in {errno.EACCES, errno.EPERM}:
            raise PackageVerifierError(
                "LANDLOCK_PROBE_FAILED",
                f"post-restriction path probe failed unexpectedly: errno={exc.errno}",
            ) from exc
    else:
        os.close(leaked)
        raise PackageVerifierError("LANDLOCK_INEFFECTIVE", "post-restriction path open unexpectedly succeeded")
    return {
        "abi_version": abi,
        "handled_access_fs": handled,
        "new_path_opens_denied": True,
        "policy": "deny-all-filesystem-after-retained-fd-open-v1",
    }


def _parse_sha256sums(raw: bytes) -> dict[str, str]:
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PackageVerifierError("SEAL_INVALID", "SHA256SUMS is not ASCII") from exc
    if not text or not text.endswith("\n"):
        raise PackageVerifierError("SEAL_INVALID", "SHA256SUMS is not nonempty newline-terminated ASCII")
    result: dict[str, str] = {}
    for line in text.splitlines():
        if len(line) < 67 or line[64:66] != "  ":
            raise PackageVerifierError("SEAL_INVALID", "SHA256SUMS line framing drifted")
        digest = line[:64]
        path = _safe_relative(line[66:], "SHA256SUMS path")
        if SHA256_RE.fullmatch(digest) is None or path == "SHA256SUMS" or path in result:
            raise PackageVerifierError("SEAL_INVALID", "SHA256SUMS entry is invalid or duplicated")
        result[path] = digest
    expected = "".join(f"{result[path]}  {path}\n" for path in sorted(result))
    if text != expected:
        raise PackageVerifierError("SEAL_INVALID", "SHA256SUMS ordering is not canonical")
    return result


def _external_source_identity(value: object, label: str) -> dict[str, object]:
    record = _exact_object(
        value,
        {"device", "inode", "mode", "mode_octal", "path", "sha256", "size_bytes"},
        label,
    )
    if (
        type(record["path"]) is not str
        or not os.path.isabs(record["path"])
        or os.path.normpath(record["path"]) != record["path"]
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
        or type(record["mode"]) is not int
        or type(record["mode_octal"]) is not str
        or record["mode_octal"] != f"{record['mode']:04o}"
        or type(record["device"]) is not int
        or type(record["inode"]) is not int
    ):
        raise PackageVerifierError("SOURCE_IDENTITY_INVALID", f"{label}: identity is malformed")
    return record


def _verify_manifest(
    raw: bytes,
    *,
    files: Mapping[str, Mapping[str, object]],
    file_hashes: Mapping[str, str],
    native_helper_expected: Mapping[str, object],
    verifier_expected: Mapping[str, object],
) -> dict[str, object]:
    manifest = _exact_object(
        _strict_json(raw, "package manifest"),
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
        or manifest["seal_contract"]
        != {
            "package_id": "sha256(SHA256SUMS exact bytes)",
            "sha256sums_domain": "all regular files below package except SHA256SUMS",
            "writes_after_seal": "forbidden",
        }
    ):
        raise PackageVerifierError("PACKAGE_MANIFEST_DRIFT", "package manifest semantics drifted")
    if type(manifest["repository_head"]) is not str or re.fullmatch(r"[0-9a-f]{40}", manifest["repository_head"]) is None:
        raise PackageVerifierError("PACKAGE_MANIFEST_DRIFT", "repository head is malformed")
    if type(manifest["run_nonce"]) is not str or not manifest["run_nonce"] or len(manifest["run_nonce"]) > 128:
        raise PackageVerifierError("PACKAGE_MANIFEST_DRIFT", "run nonce is malformed")
    if type(manifest["manager_epoch"]) is not dict:
        raise PackageVerifierError("PACKAGE_MANIFEST_DRIFT", "manager epoch is not an object")

    members_value = manifest["package_members"]
    if type(members_value) is not list:
        raise PackageVerifierError("PACKAGE_MANIFEST_DRIFT", "package members are not a list")
    members: dict[str, tuple[str, int]] = {}
    for index, value in enumerate(members_value):
        record = _exact_object(value, {"path", "sha256", "size_bytes"}, f"package member {index}")
        path = _safe_relative(record["path"], f"package member {index}.path")
        if (
            path in members
            or path in {"package-manifest.json", "SHA256SUMS"}
            or type(record["sha256"]) is not str
            or SHA256_RE.fullmatch(record["sha256"]) is None
            or type(record["size_bytes"]) is not int
            or record["size_bytes"] < 0
        ):
            raise PackageVerifierError("PACKAGE_MANIFEST_DRIFT", f"package member {index} is malformed")
        members[path] = (record["sha256"], record["size_bytes"])
    payload_paths = set(files) - {"package-manifest.json", "SHA256SUMS"}
    if set(members) != payload_paths:
        raise PackageVerifierError("PACKAGE_MANIFEST_DRIFT", "package manifest member set is not exact")
    verifier_path = str(verifier_expected["package_path"])
    verifier_digest, verifier_size = members[verifier_path]
    if verifier_digest != verifier_expected["sha256"] or verifier_size != verifier_expected["size_bytes"]:
        raise PackageVerifierError(
            "VERIFIER_MANIFEST_DRIFT",
            "manifest verifier identity disagrees with the externally verified actual bytes",
        )
    for path, (digest, size) in members.items():
        metadata = files[path]["stat"]
        if not isinstance(metadata, os.stat_result) or file_hashes[path] != digest or metadata.st_size != size:
            raise PackageVerifierError("PACKAGE_MANIFEST_DRIFT", f"{path}: package member identity drifted")

    sources_value = manifest["external_sources"]
    if type(sources_value) is not list or len(sources_value) != len(members):
        raise PackageVerifierError("PACKAGE_MANIFEST_DRIFT", "external source set is not exact")
    source_paths: set[str] = set()
    source_roles: set[str] = set()
    native_source_seen = False
    wrapper_source_seen = False
    final_release_actor_seen = False
    for index, value in enumerate(sources_value):
        record = _exact_object(
            value,
            {"package_path", "parse_json", "role", "source_identity"},
            f"external source {index}",
        )
        path = _safe_relative(record["package_path"], f"external source {index}.package_path")
        role = record["role"]
        if (
            path not in members
            or path in source_paths
            or type(role) is not str
            or ROLE_RE.fullmatch(role) is None
            or role in source_roles
            or type(record["parse_json"]) is not bool
        ):
            raise PackageVerifierError("PACKAGE_MANIFEST_DRIFT", f"external source {index} is malformed")
        source_paths.add(path)
        source_roles.add(role)
        source_identity = _external_source_identity(record["source_identity"], f"external source {index}.identity")
        digest, size = members[path]
        if source_identity["sha256"] != digest or source_identity["size_bytes"] != size:
            raise PackageVerifierError("PACKAGE_MANIFEST_DRIFT", f"external source {index} does not bind payload")
        if record["parse_json"]:
            metadata = _record_stat(files[path], path)
            _strict_json(
                _pread_all(_record_fd(files[path], path), metadata.st_size, path, limit=MAX_JSON_BYTES),
                path,
            )
        if role == "system.native_budget_helper.bin":
            native_source_seen = True
            if (
                path != NATIVE_HELPER_PACKAGE_PATH
                or source_identity["mode"] != NATIVE_HELPER_SOURCE_MODE
                or source_identity["sha256"] != native_helper_expected["sha256"]
                or source_identity["size_bytes"]
                != native_helper_expected["size_bytes"]
            ):
                raise PackageVerifierError(
                    "NATIVE_HELPER_SOURCE_DRIFT",
                    "native helper manifest source identity drifted",
                )
        elif role == "tool.ab16_native_budget_helper_v1.py":
            wrapper_source_seen = True
            if path != NATIVE_HELPER_WRAPPER_PACKAGE_PATH:
                raise PackageVerifierError(
                    "NATIVE_HELPER_ROLE_SUBSTITUTION",
                    "native helper wrapper package role drifted",
                )
        elif role == "tool.ab16_final_release_actor_v1.py":
            final_release_actor_seen = True
            if path != FINAL_RELEASE_ACTOR_PACKAGE_PATH:
                raise PackageVerifierError(
                    "FINAL_RELEASE_ACTOR_ROLE_SUBSTITUTION",
                    "final-release actor package role drifted",
                )
    if source_paths != set(members):
        raise PackageVerifierError("PACKAGE_MANIFEST_DRIFT", "external sources do not cover payload exactly")
    if not native_source_seen or not wrapper_source_seen:
        raise PackageVerifierError(
            "NATIVE_HELPER_ROLE_MISSING",
            "native helper binary or wrapper package role is absent",
        )
    if not final_release_actor_seen:
        raise PackageVerifierError(
            "FINAL_RELEASE_ACTOR_ROLE_MISSING",
            "final-release actor package role is absent",
        )
    return manifest


def _validate_expected_verifier(value: object) -> dict[str, object]:
    record = _exact_object(value, {"package_path", "sha256", "size_bytes"}, "expected verifier identity")
    path = _safe_relative(record["package_path"], "expected verifier package path")
    if (
        path != VERIFIER_PACKAGE_PATH
        or type(record["sha256"]) is not str
        or SHA256_RE.fullmatch(record["sha256"]) is None
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] <= 0
    ):
        raise PackageVerifierError("VERIFIER_IDENTITY_INVALID", "expected verifier identity is malformed")
    return record


def _validate_expected_native_helper(value: object) -> dict[str, object]:
    expected = {
        "binary_format": "ELF64",
        "build_id_sha1": NATIVE_HELPER_BUILD_ID_SHA1,
        "byte_order": "little",
        "elf_abi": "SYSV",
        "elf_machine": 62,
        "elf_type": 3,
        "elf_version": 1,
        "host_machine": "x86_64",
        "host_platform": "linux",
        "mode": NATIVE_HELPER_SOURCE_MODE,
        "package_path": NATIVE_HELPER_PACKAGE_PATH,
        "sha256": NATIVE_HELPER_SHA256,
        "size_bytes": NATIVE_HELPER_SIZE_BYTES,
        "wrapper_package_path": NATIVE_HELPER_WRAPPER_PACKAGE_PATH,
    }
    record = _exact_object(value, set(expected), "expected native helper identity")
    if record != expected:
        raise PackageVerifierError(
            "NATIVE_HELPER_IDENTITY_INVALID",
            "expected native helper identity differs from the fixed cohort",
        )
    return record


def _verify_native_helper_bytes(
    raw: bytes,
    expected: Mapping[str, object],
) -> None:
    if sys.platform != "linux" or os.uname().machine != "x86_64":
        raise PackageVerifierError(
            "NATIVE_HELPER_HOST_UNSUPPORTED",
            "native helper requires the registered Linux x86_64 host",
        )
    if (
        len(raw) != expected["size_bytes"]
        or hashlib.sha256(raw).hexdigest() != expected["sha256"]
        or len(raw) < 64
        or raw[:4] != b"\x7fELF"
        or raw[4:8] != b"\x02\x01\x01\x00"
        or int.from_bytes(raw[16:18], "little") != expected["elf_type"]
        or int.from_bytes(raw[18:20], "little") != expected["elf_machine"]
        or int.from_bytes(raw[20:24], "little") != expected["elf_version"]
    ):
        raise PackageVerifierError(
            "NATIVE_HELPER_ELF_DRIFT",
            "native helper bytes or ELF header drifted",
        )
    program_offset = int.from_bytes(raw[32:40], "little")
    program_entry_size = int.from_bytes(raw[54:56], "little")
    program_count = int.from_bytes(raw[56:58], "little")
    if program_entry_size != 56 or program_count <= 0:
        raise PackageVerifierError(
            "NATIVE_HELPER_ELF_DRIFT",
            "native helper ELF program table drifted",
        )
    build_ids: list[str] = []
    for index in range(program_count):
        start = program_offset + index * program_entry_size
        end = start + program_entry_size
        if end > len(raw):
            raise PackageVerifierError(
                "NATIVE_HELPER_ELF_DRIFT",
                "native helper ELF program table is truncated",
            )
        if int.from_bytes(raw[start : start + 4], "little") != 4:
            continue
        note_offset = int.from_bytes(raw[start + 8 : start + 16], "little")
        note_size = int.from_bytes(raw[start + 32 : start + 40], "little")
        note_end = note_offset + note_size
        if note_end > len(raw):
            raise PackageVerifierError(
                "NATIVE_HELPER_ELF_DRIFT",
                "native helper ELF note table is truncated",
            )
        cursor = note_offset
        while cursor < note_end:
            if cursor + 12 > note_end:
                raise PackageVerifierError(
                    "NATIVE_HELPER_ELF_DRIFT",
                    "native helper ELF note header is truncated",
                )
            name_size = int.from_bytes(raw[cursor : cursor + 4], "little")
            desc_size = int.from_bytes(raw[cursor + 4 : cursor + 8], "little")
            note_type = int.from_bytes(raw[cursor + 8 : cursor + 12], "little")
            cursor += 12
            name_end = cursor + name_size
            desc_start = (name_end + 3) & ~3
            desc_end = desc_start + desc_size
            next_note = (desc_end + 3) & ~3
            if name_end > note_end or desc_end > note_end or next_note > note_end:
                raise PackageVerifierError(
                    "NATIVE_HELPER_ELF_DRIFT",
                    "native helper ELF note payload is truncated",
                )
            if note_type == 3 and raw[cursor:name_end].rstrip(b"\0") == b"GNU":
                build_ids.append(raw[desc_start:desc_end].hex())
            cursor = next_note
    if build_ids != [expected["build_id_sha1"]]:
        raise PackageVerifierError(
            "NATIVE_HELPER_ELF_DRIFT",
            "native helper GNU BuildID drifted",
        )


def _write_result(descriptor: int, value: Mapping[str, object]) -> None:
    raw = _canonical_json(dict(value))
    offset = 0
    while offset < len(raw):
        try:
            written = os.write(descriptor, raw[offset:])
        except OSError as exc:
            raise PackageVerifierError("RESULT_WRITE_FAILED", f"result pipe write failed: {exc}") from exc
        if written <= 0:
            raise PackageVerifierError("RESULT_WRITE_FAILED", "result pipe made no progress")
        offset += written


def verify_package_from_fds(
    *,
    package_fd: int,
    verifier_fd: int,
    result_fd: int,
    expected_verifier: Mapping[str, object],
    expected_native_helper: Mapping[str, object],
    install_landlock: bool = True,
    enforce_ambient: bool = True,
    enforce_fd_surface: bool = True,
) -> dict[str, object]:
    """Verify one package and publish its canonical replay to ``result_fd``."""

    expected = _validate_expected_verifier(expected_verifier)
    native_expected = _validate_expected_native_helper(expected_native_helper)
    _validate_result_pipe(result_fd)
    _require_read_only(package_fd, "package root")
    _require_read_only(verifier_fd, "package verifier")
    if len({package_fd, verifier_fd, result_fd}) != 3:
        raise PackageVerifierError("FD_ALIAS_REJECTED", "package, verifier, and result descriptors must be distinct")
    if enforce_ambient:
        _reject_ambient_modules(verifier_fd)
    base_fds = {0, 1, 2, package_fd, verifier_fd, result_fd}
    if enforce_fd_surface:
        _require_exact_fd_surface(base_fds)

    directories: dict[str, dict[str, object]] = {}
    files: dict[str, dict[str, object]] = {}
    owned: list[int] = []
    primary_error: BaseException | None = None
    try:
        directories, files, owned = _scan_open_tree(package_fd)
        if enforce_fd_surface:
            _require_exact_fd_surface(base_fds | set(owned))
        verifier_record = files.get(str(expected["package_path"]))
        if verifier_record is None:
            raise PackageVerifierError("VERIFIER_MEMBER_MISSING", "package verifier member is absent")
        verifier_stat = os.fstat(verifier_fd)
        member_stat = verifier_record["stat"]
        if (
            not isinstance(member_stat, os.stat_result)
            or not _same_object(verifier_stat, member_stat)
            or _stat_signature(verifier_stat) != _stat_signature(member_stat)
        ):
            raise PackageVerifierError(
                "EXECUTING_VERIFIER_DRIFT",
                "executing verifier descriptor is not the package verifier member",
            )
        verifier_digest = _hash_fd(verifier_fd, verifier_stat.st_size, "package verifier")
        if verifier_stat.st_size != expected["size_bytes"] or verifier_digest != expected["sha256"]:
            raise PackageVerifierError(
                "VERIFIER_EXTERNAL_PIN_DRIFT",
                "actual package verifier bytes disagree with the external pre-registration",
            )

        sandbox = _install_landlock() if install_landlock else {
            "abi_version": 0,
            "handled_access_fs": 0,
            "new_path_opens_denied": False,
            "policy": "test-only-landlock-disabled",
        }
        file_hashes: dict[str, str] = {}
        for relative, record in sorted(files.items()):
            metadata = _record_stat(record, relative)
            file_hashes[relative] = _hash_fd(_record_fd(record, relative), metadata.st_size, relative)
        required = {
            "package-manifest.json",
            "SHA256SUMS",
            str(expected["package_path"]),
            str(native_expected["package_path"]),
            str(native_expected["wrapper_package_path"]),
        }
        if not required <= set(files):
            raise PackageVerifierError("PACKAGE_INCOMPLETE", "package lacks manifest, seal, or verifier member")
        expected_directories: set[str] = set()
        for relative in files:
            parts = relative.split("/")[:-1]
            for index in range(1, len(parts) + 1):
                expected_directories.add("/".join(parts[:index]))
        actual_directories = set(directories) - {""}
        if actual_directories != expected_directories:
            raise PackageVerifierError(
                "PACKAGE_CLOSURE_DRIFT",
                "package directory set is not exactly induced by its regular members",
            )
        seal_record = files["SHA256SUMS"]
        seal_stat = _record_stat(seal_record, "SHA256SUMS")
        manifest_record = files["package-manifest.json"]
        manifest_stat = _record_stat(manifest_record, "package-manifest.json")
        seal_raw = _pread_all(
            _record_fd(seal_record, "SHA256SUMS"),
            seal_stat.st_size,
            "SHA256SUMS",
            limit=MAX_JSON_BYTES,
        )
        seal = _parse_sha256sums(seal_raw)
        covered = set(files) - {"SHA256SUMS"}
        if set(seal) != covered or any(seal[path] != file_hashes[path] for path in covered):
            raise PackageVerifierError("PACKAGE_SEAL_DRIFT", "SHA256SUMS member set or digest drifted")
        manifest_raw = _pread_all(
            _record_fd(manifest_record, "package-manifest.json"),
            manifest_stat.st_size,
            "package-manifest.json",
            limit=MAX_JSON_BYTES,
        )
        manifest = _verify_manifest(
            manifest_raw,
            files=files,
            file_hashes=file_hashes,
            native_helper_expected=native_expected,
            verifier_expected=expected,
        )
        native_record = files[str(native_expected["package_path"])]
        native_stat = _record_stat(
            native_record,
            str(native_expected["package_path"]),
        )
        native_raw = _pread_all(
            _record_fd(native_record, str(native_expected["package_path"])),
            native_stat.st_size,
            str(native_expected["package_path"]),
            limit=NATIVE_HELPER_SIZE_BYTES,
        )
        _verify_native_helper_bytes(native_raw, native_expected)
        _recheck_tree(directories, files)

        artifact_manifest: list[dict[str, object]] = [
            {"path": relative, "type": "directory"} for relative in sorted(directories) if relative
        ]
        for relative in sorted(files):
            artifact_manifest.append(
                {
                "path": relative,
                "sha256": file_hashes[relative],
                "size_bytes": _record_stat(files[relative], relative).st_size,
                "type": "regular",
                }
            )
        result = {
            "arm_launch_authorized": False,
            "artifact_manifest": artifact_manifest,
            "artifact_manifest_sha256": hashlib.sha256(_canonical_json(artifact_manifest)).hexdigest(),
            "authority_scope": AUTHORITY_SCOPE,
            "classification_authorized": False,
            "landlock": sandbox,
            "manifest_identity": {
                "path": "package-manifest.json",
                "sha256": file_hashes["package-manifest.json"],
                "size_bytes": manifest_stat.st_size,
            },
            "manager_epoch": manifest["manager_epoch"],
            "native_helper_identity": native_expected,
            "package_id": hashlib.sha256(seal_raw).hexdigest(),
            "repository_head": manifest["repository_head"],
            "run_nonce": manifest["run_nonce"],
            "schema": RESULT_SCHEMA,
            "seal_identity": {
                "path": "SHA256SUMS",
                "sha256": file_hashes["SHA256SUMS"],
                "size_bytes": seal_stat.st_size,
            },
            "status": "PASS",
            "verifier_identity": expected,
            "whole_campaign_authorized": False,
        }
        # A PASS is not observable until every package descendant descriptor
        # owned by this verifier has closed successfully.
        closing = owned
        owned = []
        _close_owned(closing)
        _write_result(result_fd, result)
        return result
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        try:
            _close_owned(owned)
        except BaseException:
            if primary_error is None:
                raise


def _parse_cli(
    argv: list[str],
) -> tuple[int, int, int, dict[str, object], dict[str, object]]:
    if len(argv) != 10 or argv[0:1] != ["--package-fd"] or argv[2:3] != ["--verifier-fd"]:
        raise PackageVerifierError("ARGV_INVALID", "fixed verifier argv prefix drifted")
    if (
        argv[4:5] != ["--result-fd"]
        or argv[6:7] != ["--expected-verifier-json"]
        or argv[8:9] != ["--expected-native-helper-json"]
    ):
        raise PackageVerifierError("ARGV_INVALID", "fixed verifier argv suffix drifted")
    try:
        package_fd = int(argv[1])
        verifier_fd = int(argv[3])
        result_fd = int(argv[5])
    except ValueError as exc:
        raise PackageVerifierError("ARGV_INVALID", "descriptor arguments are not decimal integers") from exc
    if any(value < 3 for value in (package_fd, verifier_fd, result_fd)):
        raise PackageVerifierError("ARGV_INVALID", "authority descriptors must be above stdio")
    expected = _strict_json(argv[7].encode("utf-8"), "expected verifier", require_canonical=False)
    native_expected = _strict_json(
        argv[9].encode("utf-8"),
        "expected native helper",
        require_canonical=False,
    )
    return (
        package_fd,
        verifier_fd,
        result_fd,
        _validate_expected_verifier(expected),
        _validate_expected_native_helper(native_expected),
    )


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    result_fd: int | None = None
    try:
        package_fd, verifier_fd, result_fd, expected, native_expected = _parse_cli(
            arguments
        )
        verify_package_from_fds(
            package_fd=package_fd,
            verifier_fd=verifier_fd,
            result_fd=result_fd,
            expected_verifier=expected,
            expected_native_helper=native_expected,
        )
    except PackageVerifierError as exc:
        if result_fd is not None:
            try:
                _validate_result_pipe(result_fd)
                _write_result(
                    result_fd,
                    {
                        "arm_launch_authorized": False,
                        "authority_scope": AUTHORITY_SCOPE,
                        "classification_authorized": False,
                        "error_code": exc.code,
                        "message": str(exc),
                        "schema": RESULT_SCHEMA,
                        "status": "FAIL_CLOSED",
                        "whole_campaign_authorized": False,
                    },
                )
            except PackageVerifierError:
                pass
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
