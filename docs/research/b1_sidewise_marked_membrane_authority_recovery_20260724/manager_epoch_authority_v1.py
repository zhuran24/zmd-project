#!/usr/bin/env python3
"""Capture a fail-closed systemd user-manager and boot epoch.

The unprivileged side binds the systemd well-known name to one D-Bus unique
owner, freezes and audits a narrowly scoped privileged attestor, and executes
those exact attestor bytes through a fixed ``sudo -n`` and isolated Python
loader.  No command-line executable-path fallback is permitted.
"""

from __future__ import annotations

import argparse
import ast
import base64
from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any


SCHEMA = "systemd-user-manager-boot-epoch-v1"
ATTESTOR_SCHEMA = "privileged-systemd-manager-exe-attestation-v1"
AST_POLICY = "privileged-manager-exe-attestor-ast-v1"

BUSCTL = "/usr/bin/busctl"
DEFAULT_SUDO_PATH = "/usr/bin/sudo"
DEFAULT_PYTHON_PATH = "/usr/bin/python3.14"
DEFAULT_ATTESTOR_PATH = str(Path(__file__).absolute().with_name("privileged_manager_exe_attestor_v1.py"))

DBUS_DAEMON = "org.freedesktop.DBus"
DBUS_PATH = "/org/freedesktop/DBus"
DBUS_INTERFACE = "org.freedesktop.DBus"
MANAGER_NAME = "org.freedesktop.systemd1"
MANAGER_PATH = "/org/freedesktop/systemd1"
MANAGER_INTERFACE = "org.freedesktop.systemd1.Manager"

BUSCTL_TIMEOUT_SECONDS = 10
ATTESTOR_TIMEOUT_SECONDS = 30
MAX_BUSCTL_OUTPUT_BYTES = 1 << 20
MAX_ATTESTOR_OUTPUT_BYTES = 1 << 20
MAX_PROC_STAT_BYTES = 1 << 20
MAX_BOOT_ID_BYTES = 128
MAX_ATTESTOR_SOURCE_BYTES = 1 << 20
MAX_TOOL_BYTES = 64 << 20

_UNIQUE_OWNER_RE = re.compile(r":[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\Z")
_BOOT_ID_RE = re.compile(
    rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    rb"[0-9a-f]{4}-[0-9a-f]{12}\n\Z"
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

_LOADER = (
    "import sys;"
    "_source=sys.stdin.buffer.read();"
    "_namespace={'__name__':'__main__',"
    "'__file__':'<privileged-manager-exe-attestor-stdin>',"
    "'__package__':None};"
    "exec(compile(_source,'<privileged-manager-exe-attestor-stdin>',"
    "'exec',dont_inherit=True),_namespace,_namespace)"
)

_ALLOWED_ATTESTOR_IMPORTS = {
    "hashlib",
    "json",
    "os",
    "re",
    "stat",
    "sys",
}
_ALLOWED_DIRECT_CALLS = {
    "AttestorError",
    "SystemExit",
    "int",
    "isinstance",
    "len",
    "min",
    "str",
    "tuple",
}
_ALLOWED_METHOD_CALLS = {
    "append",
    "decode",
    "encode",
    "endswith",
    "find",
    "fullmatch",
    "hexdigest",
    "isalpha",
    "join",
    "rfind",
    "split",
    "update",
    "write",
}
_ALLOWED_MODULE_ATTRIBUTES = {
    "hashlib.sha256",
    "json.dumps",
    "os.O_CLOEXEC",
    "os.O_NOFOLLOW",
    "os.O_RDONLY",
    "os.SEEK_SET",
    "os.close",
    "os.fstat",
    "os.fsencode",
    "os.lseek",
    "os.open",
    "os.path",
    "os.path.isabs",
    "os.read",
    "os.readlink",
    "os.stat",
    "os.stat_result",
    "re.compile",
    "stat.S_IMODE",
    "stat.S_ISREG",
    "sys.argv",
    "sys.stdout",
    "sys.stdout.write",
}
_BANNED_NAMES = {
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "eval",
    "exec",
    "getattr",
    "globals",
    "input",
    "locals",
    "open",
    "setattr",
    "vars",
}
_BANNED_AST_NODES = (
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


class ManagerEpochError(RuntimeError):
    """Raised when the manager epoch cannot be captured unambiguously."""


def _strict_json(raw: bytes, label: str) -> Any:
    def reject_constant(value: str) -> Any:
        raise ManagerEpochError(f"{label}: non-finite JSON number {value!r}")

    def reject_float(value: str) -> Any:
        raise ManagerEpochError(f"{label}: floating-point JSON number {value!r}")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ManagerEpochError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManagerEpochError(f"{label}: invalid strict JSON: {exc}") from exc


def _busctl_json(
    *arguments: str,
    busctl_path: str = BUSCTL,
) -> dict[str, Any]:
    argv = [busctl_path, "--user", "--json=short", *arguments]
    environment = os.environ.copy()
    environment.update(
        {
            "LC_ALL": "C",
            "SYSTEMD_COLORS": "0",
            "SYSTEMD_PAGER": "cat",
            "SYSTEMD_PAGERSECURE": "1",
        }
    )
    try:
        completed = subprocess.run(
            argv,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=BUSCTL_TIMEOUT_SECONDS,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ManagerEpochError(f"busctl invocation failed for {arguments[0]!r}: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "backslashreplace").strip()
        raise ManagerEpochError(f"busctl {arguments[0]!r} exited {completed.returncode}: {detail or '<empty stderr>'}")
    if completed.stderr:
        detail = completed.stderr.decode("utf-8", "backslashreplace").strip()
        raise ManagerEpochError(f"busctl {arguments[0]!r} emitted stderr: {detail or '<non-empty binary stderr>'}")
    if not completed.stdout:
        raise ManagerEpochError(f"busctl {arguments[0]!r} returned empty stdout")
    if len(completed.stdout) > MAX_BUSCTL_OUTPUT_BYTES:
        raise ManagerEpochError(f"busctl {arguments[0]!r} output exceeded the fixed cap")
    parsed = _strict_json(completed.stdout, f"busctl {arguments[0]}")
    if not isinstance(parsed, dict) or set(parsed) != {"type", "data"}:
        raise ManagerEpochError(f"busctl {arguments[0]!r} returned an unexpected JSON envelope")
    return parsed


def _call_single(
    method: str,
    signature: str,
    argument: str,
    expected_type: str,
    *,
    busctl_path: str = BUSCTL,
) -> Any:
    payload = _busctl_json(
        "call",
        DBUS_DAEMON,
        DBUS_PATH,
        DBUS_INTERFACE,
        method,
        signature,
        argument,
        busctl_path=busctl_path,
    )
    if payload["type"] != expected_type:
        raise ManagerEpochError(f"{method}: expected type {expected_type!r}, got {payload['type']!r}")
    data = payload["data"]
    if not isinstance(data, list) or len(data) != 1:
        raise ManagerEpochError(f"{method}: expected exactly one return value")
    return data[0]


def _manager_owner(busctl_path: str = BUSCTL) -> str:
    owner = _call_single(
        "GetNameOwner",
        "s",
        MANAGER_NAME,
        "s",
        busctl_path=busctl_path,
    )
    if not isinstance(owner, str) or _UNIQUE_OWNER_RE.fullmatch(owner) is None:
        raise ManagerEpochError(f"GetNameOwner returned an invalid unique name: {owner!r}")
    return owner


def _manager_pid(owner: str, busctl_path: str = BUSCTL) -> int:
    pid = _call_single(
        "GetConnectionUnixProcessID",
        "s",
        owner,
        "u",
        busctl_path=busctl_path,
    )
    if type(pid) is not int or pid <= 0:
        raise ManagerEpochError(f"GetConnectionUnixProcessID returned an invalid PID: {pid!r}")
    return pid


def _manager_property(
    owner: str,
    name: str,
    busctl_path: str = BUSCTL,
) -> str:
    payload = _busctl_json(
        "get-property",
        owner,
        MANAGER_PATH,
        MANAGER_INTERFACE,
        name,
        busctl_path=busctl_path,
    )
    if payload["type"] != "s" or not isinstance(payload["data"], str):
        raise ManagerEpochError(f"manager property {name!r} is not a string")
    value = payload["data"]
    if not value or any(mark in value for mark in ("\x00", "\n", "\r")):
        raise ManagerEpochError(f"manager property {name!r} is malformed")
    return value


def _stable_pseudo_identity(
    metadata: os.stat_result,
) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_uid,
        metadata.st_gid,
    )


def _stable_regular_identity(
    metadata: os.stat_result,
) -> tuple[int, ...]:
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


def _read_pseudofile_same_fd(
    path: str,
    *,
    label: str,
    limit: int,
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ManagerEpochError(f"{label}: cannot open: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ManagerEpochError(f"{label}: not a regular procfs file")
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, min(65536, limit - total + 1))
            if not block:
                break
            total += len(block)
            if total > limit:
                raise ManagerEpochError(f"{label}: exceeded the fixed read cap")
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if _stable_pseudo_identity(before) != _stable_pseudo_identity(after):
        raise ManagerEpochError(f"{label}: changed during same-FD read")
    return b"".join(chunks)


def _pid_starttime(pid: int) -> int:
    raw = _read_pseudofile_same_fd(
        f"/proc/{pid}/stat",
        label=f"manager /proc/{pid}/stat",
        limit=MAX_PROC_STAT_BYTES,
    )
    first_space = raw.find(b" ")
    right_parenthesis = raw.rfind(b")")
    if (
        first_space <= 0
        or raw[first_space + 1 : first_space + 2] != b"("
        or right_parenthesis <= first_space + 1
        or raw[right_parenthesis + 1 : right_parenthesis + 2] != b" "
    ):
        raise ManagerEpochError("manager proc stat framing is invalid")
    if raw[:first_space] != str(pid).encode("ascii"):
        raise ManagerEpochError("manager proc stat PID differs from D-Bus")
    fields = raw[right_parenthesis + 2 :].split()
    if len(fields) < 20:
        raise ManagerEpochError("manager proc stat lacks starttime")
    try:
        starttime = int(fields[19], 10)
    except ValueError as exc:
        raise ManagerEpochError("manager proc stat starttime is invalid") from exc
    if starttime <= 0:
        raise ManagerEpochError("manager proc stat starttime is not positive")
    return starttime


def _boot_id() -> str:
    raw = _read_pseudofile_same_fd(
        "/proc/sys/kernel/random/boot_id",
        label="kernel boot_id",
        limit=MAX_BOOT_ID_BYTES,
    )
    if _BOOT_ID_RE.fullmatch(raw) is None:
        raise ManagerEpochError("kernel boot_id byte form is invalid")
    return raw[:-1].decode("ascii")


def _user_manager_state(
    busctl_path: str = BUSCTL,
) -> dict[str, Any]:
    owner = _manager_owner(busctl_path)
    pid = _manager_pid(owner, busctl_path)
    starttime = _pid_starttime(pid)
    version = _manager_property(owner, "Version", busctl_path)
    features = _manager_property(owner, "Features", busctl_path)
    boot_id = _boot_id()
    if _manager_owner(busctl_path) != owner:
        raise ManagerEpochError("manager owner changed during unprivileged capture")
    if _manager_pid(owner, busctl_path) != pid:
        raise ManagerEpochError("manager PID changed during unprivileged capture")
    if _pid_starttime(pid) != starttime:
        raise ManagerEpochError("manager starttime changed during unprivileged capture")
    if _manager_property(owner, "Version", busctl_path) != version:
        raise ManagerEpochError("manager Version changed during unprivileged capture")
    if _manager_property(owner, "Features", busctl_path) != features:
        raise ManagerEpochError("manager Features changed during unprivileged capture")
    if _boot_id() != boot_id:
        raise ManagerEpochError("boot_id changed during unprivileged capture")
    return {
        "boot_id": boot_id,
        "dbus_unique_owner": owner,
        "manager_pid": pid,
        "manager_pid_starttime": starttime,
        "manager_version": version,
        "manager_features": features,
    }


def _snapshot_path(
    requested_path: str | os.PathLike[str],
    *,
    label: str,
    limit: int,
    preserve_bytes: bool,
    resolve_symlinks: bool,
) -> tuple[bytes | None, dict[str, Any]]:
    requested = os.path.abspath(os.fspath(requested_path))
    if resolve_symlinks:
        path = os.path.realpath(requested)
    else:
        path = requested
    if not os.path.isabs(path):
        raise ManagerEpochError(f"{label}: path is not absolute")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ManagerEpochError(f"{label}: cannot open: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ManagerEpochError(f"{label}: not a regular file")
        if before.st_size <= 0 or before.st_size > limit:
            raise ManagerEpochError(f"{label}: size is outside fixed bounds")
        digest = hashlib.sha256()
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, 1 << 20)
            if not block:
                break
            total += len(block)
            if total > limit:
                raise ManagerEpochError(f"{label}: exceeded the fixed read cap")
            digest.update(block)
            if preserve_bytes:
                chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if _stable_regular_identity(before) != _stable_regular_identity(after):
        raise ManagerEpochError(f"{label}: changed during same-FD read")
    if total != before.st_size:
        raise ManagerEpochError(f"{label}: short or extended read")
    if resolve_symlinks and os.path.realpath(requested) != path:
        raise ManagerEpochError(f"{label}: requested symlink chain changed during snapshot")
    record = {
        "requested_path": requested,
        "path": path,
        "size_bytes": total,
        "mode": stat.S_IMODE(after.st_mode),
        "mode_octal": f"{stat.S_IMODE(after.st_mode):04o}",
        "sha256": digest.hexdigest(),
        "device": after.st_dev,
        "inode": after.st_ino,
    }
    return (b"".join(chunks) if preserve_bytes else None), record


def _qualified_name(node: ast.AST) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def _approved_attestor_pseudofile_path(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return node.value == "/proc/sys/kernel/random/boot_id" and type(node.value) is str
    if not isinstance(node, ast.JoinedStr) or len(node.values) != 3:
        return False
    prefix, interpolation, suffix = node.values
    return (
        isinstance(prefix, ast.Constant)
        and prefix.value == "/proc/"
        and isinstance(interpolation, ast.FormattedValue)
        and isinstance(interpolation.value, ast.Name)
        and interpolation.value.id == "pid"
        and interpolation.conversion == -1
        and interpolation.format_spec is None
        and isinstance(suffix, ast.Constant)
        and suffix.value == "/stat"
    )


def _audit_attestor_ast(raw: bytes) -> dict[str, Any]:
    try:
        source = raw.decode("utf-8", "strict")
        tree = ast.parse(
            source,
            filename="<privileged-manager-exe-attestor>",
            mode="exec",
        )
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ManagerEpochError(f"privileged attestor AST parse failed: {exc}") from exc
    defined_calls = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    open_flag_assignments: dict[str, list[ast.Assign]] = {}
    open_flag_store_counts: dict[str, int] = {}
    argument_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            open_flag_assignments.setdefault(node.targets[0].id, []).append(node)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            open_flag_store_counts[node.id] = open_flag_store_counts.get(node.id, 0) + 1
        if isinstance(node, ast.arg):
            argument_names.add(node.arg)

    def read_only_open_flags(
        node: ast.AST,
        *,
        call_line: int,
        seen: frozenset[str] = frozenset(),
    ) -> frozenset[str] | None:
        qualified = _qualified_name(node)
        if qualified in {"os.O_RDONLY", "os.O_CLOEXEC", "os.O_NOFOLLOW"}:
            return frozenset({qualified})
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left = read_only_open_flags(
                node.left,
                call_line=call_line,
                seen=seen,
            )
            right = read_only_open_flags(
                node.right,
                call_line=call_line,
                seen=seen,
            )
            if left is None or right is None:
                return None
            return left | right
        if (
            isinstance(node, ast.Name)
            and node.id not in seen
            and node.id not in argument_names
            and open_flag_store_counts.get(node.id) == 1
        ):
            assignments = open_flag_assignments.get(node.id, [])
            if len(assignments) != 1 or assignments[0].lineno >= call_line:
                return None
            return read_only_open_flags(
                assignments[0].value,
                call_line=call_line,
                seen=seen | {node.id},
            )
        return None

    node_count = 0
    for node in ast.walk(tree):
        node_count += 1
        if isinstance(node, _BANNED_AST_NODES):
            raise ManagerEpochError(f"privileged attestor AST contains banned node {type(node).__name__}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in _ALLOWED_ATTESTOR_IMPORTS or alias.asname is not None:
                    raise ManagerEpochError("privileged attestor imports a non-whitelisted module")
        if isinstance(node, ast.ImportFrom):
            if (
                node.module != "__future__"
                or len(node.names) != 1
                or node.names[0].name != "annotations"
                or node.names[0].asname is not None
            ):
                raise ManagerEpochError("privileged attestor has a non-whitelisted from-import")
        if isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            raise ManagerEpochError(f"privileged attestor uses banned name {node.id!r}")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                raise ManagerEpochError("privileged attestor uses a dunder attribute")
            qualified = _qualified_name(node)
            if (
                qualified is not None
                and qualified.split(".", 1)[0] in _ALLOWED_ATTESTOR_IMPORTS
                and qualified not in _ALLOWED_MODULE_ATTRIBUTES
            ):
                raise ManagerEpochError(f"privileged attestor uses non-whitelisted module attribute {qualified!r}")
            if not isinstance(node.ctx, ast.Load):
                raise ManagerEpochError("privileged attestor mutates an attribute")
        if isinstance(node, ast.Call):
            qualified = _qualified_name(node.func)
            if isinstance(node.func, ast.Name):
                allowed = node.func.id in defined_calls or node.func.id in _ALLOWED_DIRECT_CALLS
            elif isinstance(node.func, ast.Attribute):
                allowed = qualified in _ALLOWED_MODULE_ATTRIBUTES or node.func.attr in _ALLOWED_METHOD_CALLS
            else:
                allowed = False
            if not allowed:
                raise ManagerEpochError(f"privileged attestor calls a non-whitelisted target {qualified!r}")
            if qualified == "_read_pseudofile_same_fd" and (
                len(node.args) != 3 or node.keywords or not _approved_attestor_pseudofile_path(node.args[0])
            ):
                raise ManagerEpochError(
                    "privileged attestor pseudofile helper path is outside the fixed procfs allowlist"
                )
            if qualified == "os.open":
                proven_flags = (
                    read_only_open_flags(
                        node.args[1],
                        call_line=node.lineno,
                    )
                    if len(node.args) == 2
                    else None
                )
                if (
                    len(node.args) != 2
                    or node.keywords
                    or not isinstance(node.args[0], ast.Name)
                    or node.args[0].id not in {"path", "proc_exe", "target_raw"}
                    or proven_flags is None
                    or "os.O_RDONLY" not in proven_flags
                ):
                    raise ManagerEpochError("privileged attestor os.open is not a fixed read-only approved-path call")
    return {
        "policy": AST_POLICY,
        "status": "PASS",
        "ast_node_count": node_count,
        "source_size_bytes": len(raw),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
    }


def _tool_snapshots(
    sudo_path: str | os.PathLike[str],
    python_path: str | os.PathLike[str],
    attestor_path: str | os.PathLike[str],
) -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    attestor_raw, attestor = _snapshot_path(
        attestor_path,
        label="privileged attestor",
        limit=MAX_ATTESTOR_SOURCE_BYTES,
        preserve_bytes=True,
        resolve_symlinks=False,
    )
    if attestor_raw is None:
        raise ManagerEpochError("privileged attestor bytes were not retained")
    ast_receipt = _audit_attestor_ast(attestor_raw)
    _, sudo = _snapshot_path(
        sudo_path,
        label="fixed sudo",
        limit=MAX_TOOL_BYTES,
        preserve_bytes=False,
        resolve_symlinks=True,
    )
    _, python = _snapshot_path(
        python_path,
        label="fixed Python",
        limit=MAX_TOOL_BYTES,
        preserve_bytes=False,
        resolve_symlinks=True,
    )
    return (
        attestor_raw,
        {
            "attestor": attestor,
            "sudo": sudo,
            "python": python,
        },
        ast_receipt,
    )


def _attestor_payload(
    raw: bytes,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    parsed = _strict_json(raw, "privileged attestor stdout")
    if not isinstance(parsed, dict):
        raise ManagerEpochError("privileged attestor stdout root is not an object")
    canonical = (
        json.dumps(
            parsed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")
    if canonical != raw:
        raise ManagerEpochError("privileged attestor stdout is not canonical strict JSON")
    if set(parsed) != {
        "schema",
        "status",
        "request",
        "manager_executable",
    }:
        raise ManagerEpochError("privileged attestor PASS envelope has unexpected fields")
    if parsed["schema"] != ATTESTOR_SCHEMA or parsed["status"] != "PASS":
        raise ManagerEpochError("privileged attestor did not return PASS")
    request = parsed["request"]
    expected_request = {
        "manager_pid": expected["manager_pid"],
        "manager_pid_starttime": expected["manager_pid_starttime"],
        "boot_id": expected["boot_id"],
        "dbus_unique_owner": expected["dbus_unique_owner"],
    }
    if request != expected_request:
        raise ManagerEpochError("privileged attestor request echo does not join")
    executable = parsed["manager_executable"]
    if not isinstance(executable, dict) or set(executable) != {
        "path",
        "size_bytes",
        "mode",
        "mode_octal",
        "sha256",
        "device",
        "inode",
    }:
        raise ManagerEpochError("privileged attestor executable record is malformed")
    path = executable["path"]
    size_bytes = executable["size_bytes"]
    mode = executable["mode"]
    mode_octal = executable["mode_octal"]
    sha256 = executable["sha256"]
    device = executable["device"]
    inode = executable["inode"]
    if not isinstance(path, str) or not os.path.isabs(path):
        raise ManagerEpochError("privileged attestor executable path is invalid")
    if type(size_bytes) is not int or size_bytes <= 0:
        raise ManagerEpochError("privileged attestor executable size is invalid")
    if type(mode) is not int or not 0 <= mode <= 0o7777:
        raise ManagerEpochError("privileged attestor executable mode is invalid")
    if mode_octal != f"{mode:04o}":
        raise ManagerEpochError("privileged attestor executable mode forms disagree")
    if not isinstance(sha256, str) or _SHA256_RE.fullmatch(sha256) is None:
        raise ManagerEpochError("privileged attestor executable SHA-256 is invalid")
    if type(device) is not int or device < 0:
        raise ManagerEpochError("privileged attestor executable device is invalid")
    if type(inode) is not int or inode <= 0:
        raise ManagerEpochError("privileged attestor executable inode is invalid")
    return parsed


def _invoke_privileged_attestor(
    expected: Mapping[str, Any],
    *,
    sudo_path: str | os.PathLike[str],
    python_path: str | os.PathLike[str],
    attestor_path: str | os.PathLike[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    attestor_raw, tools_before, ast_receipt = _tool_snapshots(
        sudo_path,
        python_path,
        attestor_path,
    )
    argv = [
        tools_before["sudo"]["path"],
        "-n",
        "--",
        tools_before["python"]["path"],
        "-I",
        "-c",
        _LOADER,
        "--pid",
        str(expected["manager_pid"]),
        "--expected-starttime",
        str(expected["manager_pid_starttime"]),
        "--expected-boot-id",
        expected["boot_id"],
        "--dbus-owner",
        expected["dbus_unique_owner"],
    ]
    environment = {
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin",
    }
    try:
        completed = subprocess.run(
            argv,
            check=False,
            input=attestor_raw,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=ATTESTOR_TIMEOUT_SECONDS,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ManagerEpochError(f"privileged attestor invocation failed: {exc}") from exc
    _, tools_after, ast_after = _tool_snapshots(
        sudo_path,
        python_path,
        attestor_path,
    )
    if tools_after != tools_before or ast_after != ast_receipt:
        raise ManagerEpochError("privileged attestor toolchain changed across invocation")
    invocation = {
        "argv": argv,
        "stdin": {
            "size_bytes": len(attestor_raw),
            "sha256": hashlib.sha256(attestor_raw).hexdigest(),
        },
        "stdout_base64": base64.b64encode(completed.stdout).decode("ascii"),
        "stderr_base64": base64.b64encode(completed.stderr).decode("ascii"),
        "exit_code": completed.returncode,
    }
    if len(completed.stdout) > MAX_ATTESTOR_OUTPUT_BYTES:
        raise ManagerEpochError("privileged attestor stdout exceeded the fixed cap")
    if len(completed.stderr) > MAX_ATTESTOR_OUTPUT_BYTES:
        raise ManagerEpochError("privileged attestor stderr exceeded the fixed cap")
    if completed.returncode != 0:
        raise ManagerEpochError(f"privileged attestor exited {completed.returncode}")
    if completed.stderr:
        raise ManagerEpochError("privileged attestor emitted stderr")
    parsed = _attestor_payload(completed.stdout, expected)
    evidence = {
        "toolchain": tools_before,
        "ast_audit": ast_receipt,
        "invocation": invocation,
        "response": parsed,
        "post_invocation_tool_recheck": "PASS",
    }
    return parsed["manager_executable"], evidence


def _same_user_state(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    keys = (
        "boot_id",
        "dbus_unique_owner",
        "manager_pid",
        "manager_pid_starttime",
        "manager_version",
        "manager_features",
    )
    return all(left.get(key) == right.get(key) for key in keys)


def _capture_once(
    *,
    sudo_path: str | os.PathLike[str],
    python_path: str | os.PathLike[str],
    attestor_path: str | os.PathLike[str],
    busctl_path: str | os.PathLike[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _, busctl_before = _snapshot_path(
        busctl_path,
        label="observation busctl",
        limit=MAX_TOOL_BYTES,
        preserve_bytes=False,
        resolve_symlinks=True,
    )
    effective_busctl = busctl_before["path"]
    before = _user_manager_state(effective_busctl)
    executable, privileged = _invoke_privileged_attestor(
        before,
        sudo_path=sudo_path,
        python_path=python_path,
        attestor_path=attestor_path,
    )
    after = _user_manager_state(effective_busctl)
    _, busctl_after = _snapshot_path(
        busctl_path,
        label="observation busctl",
        limit=MAX_TOOL_BYTES,
        preserve_bytes=False,
        resolve_symlinks=True,
    )
    if busctl_after != busctl_before:
        raise ManagerEpochError("observation busctl changed across manager epoch capture")
    if not _same_user_state(before, after):
        raise ManagerEpochError("manager/boot epoch changed across privileged attestation")
    epoch = {
        "schema": SCHEMA,
        **after,
        "manager_executable": executable,
        "observation_toolchain": {
            "busctl": busctl_before,
        },
        "attestation_toolchain": privileged["toolchain"],
        "attestor_ast_audit": privileged["ast_audit"],
    }
    evidence = {
        "observation_toolchain_before": {
            "busctl": busctl_before,
        },
        "unprivileged_before": before,
        "privileged": privileged,
        "unprivileged_after": after,
        "observation_toolchain_after": {
            "busctl": busctl_after,
        },
        "observation_toolchain_replay": "PASS",
        "epoch_join": "PASS",
    }
    return epoch, evidence


def _identity_tuple(record: Mapping[str, Any]) -> tuple[Any, ...]:
    if record.get("schema") != SCHEMA:
        raise ManagerEpochError("manager epoch record has the wrong schema")
    executable = record.get("manager_executable")
    if not isinstance(executable, Mapping):
        raise ManagerEpochError("manager epoch record lacks an executable mapping")
    observation_toolchain = record.get("observation_toolchain")
    if not isinstance(observation_toolchain, Mapping):
        raise ManagerEpochError("manager epoch lacks observation toolchain")
    observation_busctl = observation_toolchain.get("busctl")
    if not isinstance(observation_busctl, Mapping):
        raise ManagerEpochError("manager epoch lacks observation busctl identity")
    observation_path = observation_busctl.get("path")
    observation_size = observation_busctl.get("size_bytes")
    observation_mode = observation_busctl.get("mode_octal")
    observation_digest = observation_busctl.get("sha256")
    observation_device = observation_busctl.get("device")
    observation_inode = observation_busctl.get("inode")
    if not isinstance(observation_path, str) or not os.path.isabs(observation_path):
        raise ManagerEpochError("manager epoch observation busctl path is invalid")
    if type(observation_size) is not int or observation_size <= 0:
        raise ManagerEpochError("manager epoch observation busctl size is invalid")
    if not isinstance(observation_mode, str) or re.fullmatch(r"[0-7]{4}", observation_mode) is None:
        raise ManagerEpochError("manager epoch observation busctl mode is invalid")
    if not isinstance(observation_digest, str) or _SHA256_RE.fullmatch(observation_digest) is None:
        raise ManagerEpochError("manager epoch observation busctl SHA-256 is invalid")
    if (
        type(observation_device) is not int
        or observation_device < 0
        or type(observation_inode) is not int
        or observation_inode <= 0
    ):
        raise ManagerEpochError("manager epoch observation busctl device/inode is invalid")
    toolchain = record.get("attestation_toolchain")
    if not isinstance(toolchain, Mapping):
        raise ManagerEpochError("manager epoch lacks attestation toolchain")
    tool_values: list[Any] = []
    for label in ("attestor", "sudo", "python"):
        tool = toolchain.get(label)
        if not isinstance(tool, Mapping):
            raise ManagerEpochError(f"manager epoch lacks {label} tool identity")
        path_value = tool.get("path")
        size_value = tool.get("size_bytes")
        mode_value = tool.get("mode_octal")
        digest_value = tool.get("sha256")
        device_value = tool.get("device")
        inode_value = tool.get("inode")
        if not isinstance(path_value, str) or not os.path.isabs(path_value):
            raise ManagerEpochError(f"manager epoch {label} path is invalid")
        if type(size_value) is not int or size_value <= 0:
            raise ManagerEpochError(f"manager epoch {label} size is invalid")
        if not isinstance(mode_value, str) or re.fullmatch(r"[0-7]{4}", mode_value) is None:
            raise ManagerEpochError(f"manager epoch {label} mode is invalid")
        if not isinstance(digest_value, str) or _SHA256_RE.fullmatch(digest_value) is None:
            raise ManagerEpochError(f"manager epoch {label} SHA-256 is invalid")
        if type(device_value) is not int or type(inode_value) is not int:
            raise ManagerEpochError(f"manager epoch {label} device/inode is invalid")
        tool_values.extend(
            (
                path_value,
                size_value,
                mode_value,
                digest_value,
                device_value,
                inode_value,
            )
        )
    values = (
        record.get("boot_id"),
        record.get("dbus_unique_owner"),
        record.get("manager_pid"),
        record.get("manager_pid_starttime"),
        executable.get("path"),
        executable.get("size_bytes"),
        executable.get("mode"),
        executable.get("sha256"),
        executable.get("device"),
        executable.get("inode"),
        record.get("manager_version"),
        record.get("manager_features"),
        observation_path,
        observation_size,
        observation_mode,
        observation_digest,
        observation_device,
        observation_inode,
        *tool_values,
    )
    (
        boot_id,
        owner,
        pid,
        starttime,
        path,
        size,
        mode,
        sha256,
        executable_device,
        executable_inode,
        version,
        features,
        *_,
    ) = values
    mode_octal = executable.get("mode_octal")
    if not isinstance(boot_id, str):
        raise ManagerEpochError("manager epoch boot_id is invalid")
    try:
        boot_raw = boot_id.encode("ascii") + b"\n"
    except UnicodeEncodeError as exc:
        raise ManagerEpochError("manager epoch boot_id is not ASCII") from exc
    if _BOOT_ID_RE.fullmatch(boot_raw) is None:
        raise ManagerEpochError("manager epoch boot_id is invalid")
    if not isinstance(owner, str) or _UNIQUE_OWNER_RE.fullmatch(owner) is None:
        raise ManagerEpochError("manager epoch owner is invalid")
    if type(pid) is not int or pid <= 0:
        raise ManagerEpochError("manager epoch PID is invalid")
    if type(starttime) is not int or starttime <= 0:
        raise ManagerEpochError("manager epoch starttime is invalid")
    if not isinstance(path, str) or not os.path.isabs(path):
        raise ManagerEpochError("manager epoch executable path is invalid")
    if type(size) is not int or size <= 0:
        raise ManagerEpochError("manager epoch executable size is invalid")
    if type(mode) is not int or not 0 <= mode <= 0o7777:
        raise ManagerEpochError("manager epoch executable mode is invalid")
    if mode_octal is not None and (
        not isinstance(mode_octal, str) or re.fullmatch(r"[0-7]{4}", mode_octal) is None or mode_octal != f"{mode:04o}"
    ):
        raise ManagerEpochError("manager epoch executable mode forms disagree")
    if not isinstance(sha256, str) or _SHA256_RE.fullmatch(sha256) is None:
        raise ManagerEpochError("manager epoch executable SHA-256 is invalid")
    if (
        type(executable_device) is not int
        or executable_device < 0
        or type(executable_inode) is not int
        or executable_inode <= 0
    ):
        raise ManagerEpochError("manager epoch executable device/inode is invalid")
    if not isinstance(version, str) or not version:
        raise ManagerEpochError("manager epoch Version is invalid")
    if not isinstance(features, str) or not features:
        raise ManagerEpochError("manager epoch Features are invalid")
    return values


def same_epoch(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    """Return true only for two complete, equal manager/boot identities."""

    try:
        return _identity_tuple(left) == _identity_tuple(right)
    except ManagerEpochError:
        return False


def capture_manager_epoch(
    *,
    sudo_path: str | os.PathLike[str] = DEFAULT_SUDO_PATH,
    python_path: str | os.PathLike[str] = DEFAULT_PYTHON_PATH,
    attestor_path: str | os.PathLike[str] = DEFAULT_ATTESTOR_PATH,
    busctl_path: str | os.PathLike[str] = BUSCTL,
) -> dict[str, Any]:
    """Capture a double-checked epoch with injectable fixture tool paths."""

    first, first_evidence = _capture_once(
        sudo_path=sudo_path,
        python_path=python_path,
        attestor_path=attestor_path,
        busctl_path=busctl_path,
    )
    second, second_evidence = _capture_once(
        sudo_path=sudo_path,
        python_path=python_path,
        attestor_path=attestor_path,
        busctl_path=busctl_path,
    )
    if not same_epoch(first, second):
        raise ManagerEpochError("manager/boot epoch changed across the double capture")
    first_executable = first["manager_executable"]
    second_executable = second["manager_executable"]
    if (
        first_executable["device"],
        first_executable["inode"],
    ) != (
        second_executable["device"],
        second_executable["inode"],
    ):
        raise ManagerEpochError("manager executable dev/inode changed across double capture")
    result = dict(second)
    result["capture_evidence"] = {
        "protocol": "double-privileged-attestation-v1",
        "samples": [first_evidence, second_evidence],
    }
    return result


def _write_exclusive(path: Path, raw: bytes) -> None:
    absolute = os.path.abspath(os.fspath(path))
    parent, name = os.path.split(absolute)
    if not name or name in {".", ".."}:
        raise ManagerEpochError("output final component is invalid")
    parent_flags = (
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        parent_fd = os.open(parent, parent_flags)
    except OSError as exc:
        raise ManagerEpochError(f"cannot open output parent directory: {exc}") from exc
    try:
        output_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(
                name,
                output_flags,
                0o644,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise ManagerEpochError(f"cannot create output with O_EXCL: {exc}") from exc
        try:
            offset = 0
            while offset < len(raw):
                written = os.write(descriptor, raw[offset:])
                if written <= 0:
                    raise ManagerEpochError("short output write")
                offset += written
            os.fsync(descriptor)
            if os.fstat(descriptor).st_size != len(raw):
                raise ManagerEpochError("output size does not match payload")
        finally:
            os.close(descriptor)
    finally:
        os.close(parent_fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Capture a strict systemd user-manager/boot epoch.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="new JSON path; created exactly once with O_EXCL",
    )
    arguments = parser.parse_args(argv)
    try:
        epoch = capture_manager_epoch()
        raw = (
            json.dumps(
                epoch,
                sort_keys=True,
                indent=2,
                ensure_ascii=True,
            )
            + "\n"
        ).encode("ascii")
        _write_exclusive(arguments.output, raw)
    except ManagerEpochError as exc:
        print(
            f"MANAGER_EPOCH_AUTHORITY_ERROR: {exc}",
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "schema": SCHEMA,
                "status": "MANAGER_EPOCH_CAPTURED",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
