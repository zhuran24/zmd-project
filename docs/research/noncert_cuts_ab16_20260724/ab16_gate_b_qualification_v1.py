#!/usr/bin/env python3
"""Persistent, research-only Gate-B qualification owner for one AB16 bootstrap.

This module owns the three qualification locks, one exec-persistent Gate-B
publisher process, and the terminal bootstrap handoff.  It cannot launch an
arm or solver and grants no production, certified, cut, or bound authority.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import ctypes
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import select
import shutil
import socket
import stat
import subprocess
import sys
from typing import Any


QUALIFICATION_SCHEMA = "noncert-cuts-ab16-gate-b-qualification-v1"
OWNER_REQUEST_SCHEMA = "noncert-cuts-ab16-gate-b-owner-request-v1"
OWNER_RESPONSE_SCHEMA = "noncert-cuts-ab16-gate-b-owner-response-v1"
HANDOFF_REQUEST_SCHEMA = "noncert-cuts-ab16-gate-b-bootstrap-handoff-request-v1"
HANDOFF_RESPONSE_SCHEMA = "noncert-cuts-ab16-gate-b-bootstrap-handoff-response-v1"
OWNER_RELEASE_SCHEMA = "noncert-cuts-ab16-gate-b-owner-release-v1"
RESOURCE_GATE_SCHEMA = "noncert-cuts-ab16-gate-b-resource-gate-v1"
OWNER_EXECUTION_STRATEGY = "persistent-owner-sealed-fd-oexcl-bootstrap-handoff-v1"
LOCK_PATHS = (
    "/tmp/zmd-pj-codex-heavy-validation.lock",
    "/run/user/1000/zmd_pj_prod_scale_solver.lock",
    "/run/user/1000/zmd-pj-prod-scale-solve.lock",
)
DEFAULT_LOCK_PATHS = tuple(map(Path, LOCK_PATHS))
RETAINED_FD_ROLES = (
    "lock",
    "mechanical_publisher",
    "output_directory",
    "rendered_record",
    "renderer_source",
    "request",
)
_MAX_FRAME = 16 * 1024 * 1024
_F_ADD_SEALS = getattr(fcntl, "F_ADD_SEALS", 1033)
_F_GET_SEALS = getattr(fcntl, "F_GET_SEALS", 1034)
_REQUIRED_SEALS = 0x0001 | 0x0002 | 0x0004 | 0x0008
MIN_DISK_BYTES = 16 * 1024**3
MIN_MEM_AVAILABLE = 36 * 1024**3
MIN_SWAP_FREE = 16 * 1024**3
CONFLICT_PATTERNS = (
    "ab16_formal_campaign_v1.py",
    "ab16_outer_guardian_v1.py",
    "cp_model_solver",
    "endfield",
    "gamescope",
    "organic_unit_orchestrator",
    "preflight_gate.py",
    "proton",
    "pytest",
    "steam",
    "wine",
)
FALSE_AUTHORIZATIONS = {
    "formal_campaign_creation_authorized": False,
    "organic_arm_launch_authorized": False,
    "solver_run_authorized": False,
}
_PERMITTED_PINNED_PYTHON_STDERR = {
    b"",
    b"Could not find platform dependent libraries <exec_prefix>\n",
}


class QualificationError(RuntimeError):
    """The research-only Gate-B qualification chain failed closed."""


class _OwnedDescriptor:
    """Own one descriptor until it is explicitly transferred or closed."""

    __slots__ = ("_descriptor",)

    def __init__(self) -> None:
        self._descriptor: int | None = None

    @property
    def owned(self) -> bool:
        return self._descriptor is not None

    @property
    def descriptor(self) -> int:
        descriptor = self._descriptor
        if descriptor is None:
            raise RuntimeError("descriptor ownership is absent")
        return descriptor

    def acquire(self, descriptor: int) -> int:
        if self._descriptor is not None:
            raise RuntimeError("descriptor ownership is already present")
        self._descriptor = descriptor
        return descriptor

    def release(self) -> int:
        descriptor = self.descriptor
        self._descriptor = None
        return descriptor

    def close(self) -> BaseException | None:
        if self._descriptor is None:
            return None
        descriptor = self.release()
        try:
            os.close(descriptor)
        except BaseException as exc:
            return exc
        return None

    def close_preserving(self, primary: BaseException) -> None:
        cleanup_error = self.close()
        if cleanup_error is not None:
            primary.add_note(
                "descriptor cleanup failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )


def _raise_cleanup_error(label: str, error: BaseException) -> None:
    if isinstance(error, QualificationError):
        raise error
    raise QualificationError(
        f"{label} cleanup failed: {type(error).__name__}: {error}"
    ) from error


def _close_descriptors(
    descriptors: Sequence[int],
    *,
    primary: BaseException | None,
) -> None:
    cleanup_errors: list[BaseException] = []
    for descriptor in reversed(tuple(descriptors)):
        try:
            os.close(descriptor)
        except BaseException as exc:
            cleanup_errors.append(exc)
    if primary is not None:
        for cleanup_error in cleanup_errors:
            primary.add_note(
                "descriptor cleanup failed: "
                f"{type(cleanup_error).__name__}: {cleanup_error}"
            )
    elif cleanup_errors:
        _raise_cleanup_error("descriptor set", cleanup_errors[0])


def _wait_process(
    process: subprocess.Popen[bytes],
    *,
    timeout: float | None,
) -> int:
    while True:
        try:
            return process.wait(timeout=timeout)
        except InterruptedError:
            continue


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


def _strict_json(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise QualificationError(f"{label} contains duplicate JSON key {key!r}")
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise QualificationError(f"{label} contains invalid JSON constant {value}")

    try:
        value = json.loads(
            raw,
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise QualificationError(f"{label} is not strict JSON") from exc
    if _canonical_json(value) != raw:
        raise QualificationError(f"{label} is not canonical JSON")
    return value


def _strict_unterminated_json(raw: bytes, label: str) -> Any:
    value = _strict_json(raw + b"\n", label)
    if _canonical_json(value)[:-1] != raw:
        raise QualificationError(f"{label} is not canonical unterminated JSON")
    return value


def _exact_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise QualificationError(f"{label} key set drifted")
    return value


def _signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_gid,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _proc_starttime(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise QualificationError("owner process identity is unavailable") from exc
    closing = raw.rfind(")")
    fields = raw[closing + 2 :].split()
    if closing <= 1 or len(fields) <= 19 or not fields[19].isdigit():
        raise QualificationError("owner process identity is malformed")
    return fields[19]


def _read_stable_fd(
    descriptor: int,
    *,
    label: str,
    expected_nlink: int | None = None,
    limit: int = _MAX_FRAME,
) -> bytes:
    before = os.fstat(descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or (expected_nlink is not None and before.st_nlink != expected_nlink)
        or before.st_size < 0
        or before.st_size > limit
    ):
        raise QualificationError(f"{label} is not one bounded regular file")
    os.lseek(descriptor, 0, os.SEEK_SET)
    remaining = before.st_size
    chunks: list[bytes] = []
    while remaining:
        chunk = os.read(descriptor, min(remaining, 1 << 20))
        if not chunk:
            raise QualificationError(f"{label} was truncated")
        chunks.append(chunk)
        remaining -= len(chunk)
    if os.read(descriptor, 1) or _signature(os.fstat(descriptor)) != _signature(before):
        raise QualificationError(f"{label} changed during read")
    return b"".join(chunks)


def _mode_identity(path: Path | str) -> dict[str, object]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    descriptor = _OwnedDescriptor()
    try:
        descriptor.acquire(_open_regular(absolute))
        raw = _read_stable_fd(
            descriptor.descriptor,
            label=str(absolute),
            expected_nlink=1,
            limit=1 << 30,
        )
        metadata = os.fstat(descriptor.descriptor)
    except BaseException as exc:
        descriptor.close_preserving(exc)
        raise
    close_error = descriptor.close()
    if close_error is not None:
        _raise_cleanup_error(f"{absolute} identity descriptor", close_error)
    return {
        "mode": stat.S_IMODE(metadata.st_mode),
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _unterminated_mode_record(
    path: Path | str,
    label: str,
) -> tuple[dict[str, Any], dict[str, object]]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    descriptor = _OwnedDescriptor()
    try:
        descriptor.acquire(_open_regular(absolute))
        raw = _read_stable_fd(
            descriptor.descriptor,
            label=label,
            expected_nlink=1,
            limit=4 * 1024 * 1024,
        )
        metadata = os.fstat(descriptor.descriptor)
        value = _strict_unterminated_json(raw, label)
        if type(value) is not dict:
            raise QualificationError(f"{label} is not a JSON object")
    except BaseException as exc:
        descriptor.close_preserving(exc)
        raise
    close_error = descriptor.close()
    if close_error is not None:
        _raise_cleanup_error(f"{label} descriptor", close_error)
    return value, {
        "mode": stat.S_IMODE(metadata.st_mode),
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _detached_identity(path: Path | str) -> dict[str, object]:
    identity = _mode_identity(path)
    return {
        "path": identity["path"],
        "sha256": identity["sha256"],
        "size_bytes": identity["size_bytes"],
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _literal_identity(value: str) -> dict[str, object]:
    raw = value.encode("utf-8")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW


def _open_directory(path: Path | str) -> int:
    absolute = Path(os.path.abspath(os.fspath(path)))
    if not absolute.is_absolute():
        raise QualificationError("directory path is not absolute")
    current = _OwnedDescriptor()
    try:
        current.acquire(os.open("/", _directory_flags()))
        for component in absolute.parts[1:]:
            following = _OwnedDescriptor()
            following.acquire(
                os.open(component, _directory_flags(), dir_fd=current.descriptor)
            )
            close_error = current.close()
            if close_error is not None:
                following.close_preserving(close_error)
                raise close_error
            current = following
        return current.release()
    except BaseException as exc:
        current.close_preserving(exc)
        raise


def _open_regular(path: Path | str) -> int:
    absolute = Path(os.path.abspath(os.fspath(path)))
    parent = _OwnedDescriptor()
    descriptor = _OwnedDescriptor()
    try:
        parent.acquire(_open_directory(absolute.parent))
        descriptor.acquire(
            os.open(
                absolute.name,
                os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent.descriptor,
            )
        )
        close_error = parent.close()
        if close_error is not None:
            raise close_error
        metadata = os.fstat(descriptor.descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise QualificationError(f"not one regular file: {absolute}")
        return descriptor.release()
    except BaseException as exc:
        descriptor.close_preserving(exc)
        parent.close_preserving(exc)
        raise


def _read_stable_path(
    path: Path | str,
    *,
    label: str,
    limit: int = _MAX_FRAME,
) -> bytes:
    descriptor = _OwnedDescriptor()
    try:
        descriptor.acquire(_open_regular(path))
        result = _read_stable_fd(
            descriptor.descriptor,
            label=label,
            expected_nlink=1,
            limit=limit,
        )
    except BaseException as exc:
        descriptor.close_preserving(exc)
        raise
    close_error = descriptor.close()
    if close_error is not None:
        _raise_cleanup_error(f"{label} descriptor", close_error)
    return result


def _clean_environment() -> dict[str, str]:
    return {
        "LANG": "C",
        "LC_ALL": "C",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "TZ": "UTC",
    }


def _verified_session_bus_environment() -> dict[str, str]:
    uid = os.getuid()
    if os.geteuid() != uid:
        raise QualificationError("session bus environment requires matching real/effective uid")
    runtime_path = Path(f"/run/user/{uid}")
    bus_path = runtime_path / "bus"
    expected_runtime = str(runtime_path)
    expected_address = f"unix:path={bus_path}"

    directory = _OwnedDescriptor()
    try:
        directory.acquire(_open_directory(runtime_path))
        before = os.fstat(directory.descriptor)
        bus = os.stat("bus", dir_fd=directory.descriptor, follow_symlinks=False)
        after = os.fstat(directory.descriptor)
        if (
            _signature(before) != _signature(after)
            or not stat.S_ISDIR(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o700
            or before.st_uid != uid
            or not stat.S_ISSOCK(bus.st_mode)
            or bus.st_uid != uid
            or bus.st_nlink != 1
            or bus.st_dev != before.st_dev
        ):
            raise QualificationError("fixed per-user session bus node failed validation")
    except BaseException as exc:
        directory.close_preserving(exc)
        raise
    close_error = directory.close()
    if close_error is not None:
        _raise_cleanup_error("session bus directory descriptor", close_error)
    return {
        "DBUS_SESSION_BUS_ADDRESS": expected_address,
        "XDG_RUNTIME_DIR": expected_runtime,
    }


def _preflight_environment() -> dict[str, str]:
    environment = _clean_environment()
    environment.update(_verified_session_bus_environment())
    return environment


def _lock_identity(descriptor: int, path: Path | str) -> dict[str, object]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    metadata = os.fstat(descriptor)
    parent = _OwnedDescriptor()
    try:
        parent.acquire(_open_directory(absolute.parent))
        named = os.stat(
            absolute.name,
            dir_fd=parent.descriptor,
            follow_symlinks=False,
        )
    except BaseException as exc:
        parent.close_preserving(exc)
        raise
    close_error = parent.close()
    if close_error is not None:
        _raise_cleanup_error("lock parent descriptor", close_error)
    if (
        _signature(metadata) != _signature(named)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
    ):
        raise QualificationError(f"qualification lock identity drifted: {absolute}")
    return {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "mode": stat.S_IMODE(metadata.st_mode),
        "nlink": metadata.st_nlink,
        "path": str(absolute),
        "uid": metadata.st_uid,
    }


def _acquire_lock(path: Path | str) -> int:
    absolute = Path(os.path.abspath(os.fspath(path)))
    parent = _OwnedDescriptor()
    descriptor = _OwnedDescriptor()
    try:
        parent.acquire(_open_directory(absolute.parent))
        descriptor.acquire(
            os.open(
                absolute.name,
                os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent.descriptor,
            )
        )
        close_error = parent.close()
        if close_error is not None:
            raise close_error
        _lock_identity(descriptor.descriptor, absolute)
        fcntl.flock(descriptor.descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return descriptor.release()
    except BaseException as exc:
        descriptor.close_preserving(exc)
        parent.close_preserving(exc)
        raise


def _sealed_memfd(name: str, raw: bytes) -> int:
    owner = _OwnedDescriptor()
    if hasattr(os, "memfd_create"):
        owner.acquire(
            os.memfd_create(  # type: ignore[attr-defined]
                name,
                getattr(os, "MFD_CLOEXEC", 0x0001)
                | getattr(os, "MFD_ALLOW_SEALING", 0x0002),
            )
        )
    else:
        libc = ctypes.CDLL(None, use_errno=True)
        create = libc.memfd_create
        create.argtypes = [ctypes.c_char_p, ctypes.c_uint]
        create.restype = ctypes.c_int
        descriptor = int(create(name.encode("ascii"), 0x0001 | 0x0002))
        if descriptor < 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        owner.acquire(descriptor)
    try:
        view = memoryview(raw)
        while view:
            count = os.write(owner.descriptor, view)
            if count <= 0:
                raise QualificationError("memfd write was short")
            view = view[count:]
        fcntl.fcntl(owner.descriptor, _F_ADD_SEALS, _REQUIRED_SEALS)
        if (
            fcntl.fcntl(owner.descriptor, _F_GET_SEALS) & _REQUIRED_SEALS
            != _REQUIRED_SEALS
        ):
            raise QualificationError("memfd seals are incomplete")
        os.lseek(owner.descriptor, 0, os.SEEK_SET)
        return owner.release()
    except BaseException as exc:
        owner.close_preserving(exc)
        raise


def _send_frame(
    channel: socket.socket,
    value: object,
    *,
    descriptors: Sequence[int] = (),
) -> None:
    raw = _canonical_json(value)
    ancillary = []
    if descriptors:
        import array

        ancillary = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", descriptors))]
    sent = channel.sendmsg([raw], ancillary)
    if sent != len(raw):
        raise QualificationError("control frame write was short")


def _recv_frame(
    channel: socket.socket,
    *,
    receive_descriptor: bool = False,
) -> dict[str, Any]:
    ancillary_size = socket.CMSG_SPACE(4) if receive_descriptor else 0
    raw, ancillary, flags, _address = channel.recvmsg(_MAX_FRAME, ancillary_size)
    received: list[_OwnedDescriptor] = []
    if receive_descriptor:
        import array

        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                numbers = array.array("i")
                numbers.frombytes(data[: len(data) - len(data) % numbers.itemsize])
                for descriptor in numbers:
                    owner = _OwnedDescriptor()
                    received.append(owner)
                    owner.acquire(descriptor)
    try:
        if not raw or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            raise QualificationError("control frame is absent or truncated")
        value = _strict_json(raw, "control frame")
        if type(value) is not dict:
            raise QualificationError("control frame is not an object")
        if len(received) > 1:
            raise QualificationError("control frame carries multiple descriptors")
        if received:
            value["_received_descriptor"] = received[0].release()
        return value
    except BaseException as exc:
        for owner in reversed(received):
            if owner.owned:
                owner.close_preserving(exc)
        raise


def _publish_with_literal(
    *,
    python_fd: int,
    publisher_fd: int,
    rendered_fd: int,
    directory_fd: int,
    basename: str,
) -> None:
    read_owner = _OwnedDescriptor()
    write_owner = _OwnedDescriptor()
    try:
        read_end, write_end = os.pipe2(os.O_CLOEXEC)
        read_owner.acquire(read_end)
        write_owner.acquire(write_end)
        completed = subprocess.run(
            [
                "python3.13",
                "-I",
                "-B",
                f"/proc/self/fd/{publisher_fd}",
                basename,
                str(rendered_fd),
                str(directory_fd),
                str(write_owner.descriptor),
            ],
            check=False,
            close_fds=True,
            env={
                "LANG": "C",
                "LC_ALL": "C",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "PYTHONNOUSERSITE": "1",
                "TZ": "UTC",
            },
            executable=f"/proc/self/fd/{python_fd}",
            pass_fds=(
                python_fd,
                publisher_fd,
                rendered_fd,
                directory_fd,
                write_owner.descriptor,
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        close_error = write_owner.close()
        if close_error is not None:
            raise close_error
        result = os.read(read_owner.descriptor, 4096)
    except BaseException as exc:
        write_owner.close_preserving(exc)
        read_owner.close_preserving(exc)
        raise
    close_error = read_owner.close()
    if close_error is not None:
        _raise_cleanup_error("mechanical publisher result pipe", close_error)
    permitted_stderr = {
        b"",
        b"Could not find platform dependent libraries <exec_prefix>\n",
    }
    if (
        completed.returncode != 0
        or completed.stderr not in permitted_stderr
        or not result.startswith(b"OK ")
    ):
        raise QualificationError(
            f"mechanical publisher failed: exit={completed.returncode}; stderr={completed.stderr!r}"
        )


def _owner_main(args: argparse.Namespace) -> int:
    control = socket.socket(fileno=args.control_fd)
    renderer_raw = _read_stable_fd(args.renderer_fd, label="sealed renderer", expected_nlink=0)
    publisher_raw = _read_stable_fd(args.publisher_fd, label="sealed publisher", expected_nlink=0)
    if (
        fcntl.fcntl(args.renderer_fd, _F_GET_SEALS) & _REQUIRED_SEALS != _REQUIRED_SEALS
        or fcntl.fcntl(args.publisher_fd, _F_GET_SEALS) & _REQUIRED_SEALS != _REQUIRED_SEALS
    ):
        raise QualificationError("owner source memfd seals are incomplete")
    renderer_identity = _strict_json(args.renderer_identity.encode() + b"\n", "renderer identity")
    owner_source_identity = _strict_json(args.owner_source_identity.encode() + b"\n", "owner source identity")
    python_identity = _strict_json(args.python_identity.encode() + b"\n", "Python identity")
    driver_identity = _strict_json(args.driver_identity.encode() + b"\n", "driver identity")
    publisher_identity = {
        "sha256": hashlib.sha256(publisher_raw).hexdigest(),
        "size_bytes": len(publisher_raw),
    }
    if (
        renderer_identity["sha256"] != hashlib.sha256(renderer_raw).hexdigest()
        or renderer_identity["size_bytes"] != len(renderer_raw)
    ):
        raise QualificationError("sealed renderer identity drifted")
    lock_pairs = tuple(zip(args.lock_path, args.lock_fd, strict=True))
    lock_identities = [_lock_identity(descriptor, path) for path, descriptor in lock_pairs]
    for _path, descriptor in lock_pairs:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    actor = {
        "pid": os.getpid(),
        "pid_starttime": _proc_starttime(os.getpid()),
        "role": "AB16_GATE_B_OWNER",
    }
    session_id = secrets.token_hex(32)
    _send_frame(
        control,
        {
            "actor": actor,
            "lock_identities": lock_identities,
            "schema": OWNER_RESPONSE_SCHEMA,
            "session_id": session_id,
            "state": "READY",
            "status": "PASS",
        },
    )
    retained: list[dict[str, Any]] = []
    next_sequence = 1
    bootstrap_channel: socket.socket | None = None
    handoff_complete = False
    while True:
        readable, _, _ = select.select(
            [control, *(() if bootstrap_channel is None else (bootstrap_channel,))],
            [],
            [],
        )
        if bootstrap_channel is not None and bootstrap_channel in readable:
            request = _recv_frame(bootstrap_channel)
            _exact_keys(
                request,
                {
                    "action",
                    "actor",
                    "campaign_root_identity",
                    "gate1_selection_identity",
                    "gate_b_approval_identity",
                    "gate_b_epoch_identity",
                    "lock_identities",
                    "publisher_sequences",
                    "schema",
                    "session_id",
                },
                "bootstrap handoff",
            )
            if (
                request["schema"] != HANDOFF_REQUEST_SCHEMA
                or request["action"] != "BOOTSTRAP_HANDOFF"
                or request["session_id"] != session_id
                or request["actor"] != actor
                or request["publisher_sequences"] != [1, 2]
                or request["lock_identities"] != lock_identities
                or len(retained) != 2
                or request["gate_b_epoch_identity"] != retained[0]["output_identity"]
                or request["gate_b_approval_identity"] != retained[1]["output_identity"]
            ):
                raise QualificationError("bootstrap handoff identity drifted")
            retention_projection: list[dict[str, object]] = []
            for item in retained:
                for descriptor, role in (
                    (item["request_fd"], "request"),
                    (item["rendered_fd"], "rendered_record"),
                ):
                    raw = _read_stable_fd(descriptor, label=role, expected_nlink=0)
                    if fcntl.fcntl(descriptor, _F_GET_SEALS) & _REQUIRED_SEALS != _REQUIRED_SEALS:
                        raise QualificationError(f"retained {role} seals drifted")
                    retention_projection.append(
                        {
                            "role": role,
                            "sequence": item["sequence"],
                            "sha256": hashlib.sha256(raw).hexdigest(),
                            "size_bytes": len(raw),
                        }
                    )
                if _signature(os.fstat(item["directory_fd"])) != item["directory_signature"]:
                    raise QualificationError("retained output directory drifted")
                if _mode_identity(item["output_path"]) != item["output_identity"]:
                    raise QualificationError("published output identity drifted")
            if _proc_starttime(os.getpid()) != actor["pid_starttime"]:
                raise QualificationError("owner actor identity drifted")
            for path, descriptor in lock_pairs:
                if _lock_identity(descriptor, path) not in lock_identities:
                    raise QualificationError("retained qualification lock drifted")
            retained_digest = hashlib.sha256(_canonical_json(retention_projection)).hexdigest()
            _send_frame(
                bootstrap_channel,
                {
                    "actor": actor,
                    "lock_identities": lock_identities,
                    "publisher_sequences": [1, 2],
                    "retained_fd_digest": retained_digest,
                    "retained_fd_roles": list(RETAINED_FD_ROLES),
                    "schema": HANDOFF_RESPONSE_SCHEMA,
                    "session_id": session_id,
                    "state": "BOOTSTRAP_HANDOFF_COMPLETE_FDS_RETAINED",
                    "status": "PASS",
                },
            )
            handoff_complete = True
            continue
        if control not in readable:
            continue
        request = _recv_frame(control, receive_descriptor=True)
        received = request.pop("_received_descriptor", None)
        action = request.get("action")
        if action == "PUBLISH":
            if received is not None:
                os.close(received)
                raise QualificationError("publication request carried an unexpected descriptor")
            _exact_keys(
                request,
                {"action", "kind", "output_path", "record", "schema", "sequence", "session_id"},
                "publication request",
            )
            expected_kind = "epoch" if next_sequence == 1 else "approval"
            if (
                request["schema"] != OWNER_REQUEST_SCHEMA
                or request["session_id"] != session_id
                or request["sequence"] != next_sequence
                or request["kind"] != expected_kind
                or next_sequence not in (1, 2)
            ):
                _send_frame(
                    control,
                    {
                        "code": "PUBLISH_SEQUENCE",
                        "schema": OWNER_RESPONSE_SCHEMA,
                        "state": "REJECTED",
                        "status": "FAIL_CLOSED",
                    },
                )
                continue
            output_path = Path(str(request["output_path"]))
            directory_fd = _open_directory(output_path.parent)
            try:
                try:
                    os.stat(output_path.name, dir_fd=directory_fd, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    raise QualificationError("publication output already exists")
                request_fd = _sealed_memfd(
                    f"ab16-gate-b-request-{next_sequence}",
                    _canonical_json(request),
                )
                context = {
                    "actor": actor,
                    "driver_program": driver_identity,
                    "execution_strategy": OWNER_EXECUTION_STRATEGY,
                    "mechanical_publisher": publisher_identity,
                    "output_mode": 0o444,
                    "output_path": str(output_path),
                    "owner_source": owner_source_identity,
                    "python": python_identity,
                    "qualification_session": {
                        "lock_identities": lock_identities,
                        "retained_fd_roles": list(RETAINED_FD_ROLES),
                        "sequence": next_sequence,
                        "session_id": session_id,
                        "state": "PUBLISHED_FDS_RETAINED_PENDING_BOOTSTRAP_HANDOFF",
                    },
                    "renderer_source": renderer_identity,
                }
                namespace = {
                    "__ab16_gate_b_owner_context__": context,
                    "__file__": renderer_identity["path"],
                    "__name__": "_ab16_gate_b_owner_selected",
                }
                exec(
                    compile(
                        renderer_raw,
                        renderer_identity["path"],
                        "exec",
                        dont_inherit=True,
                    ),
                    namespace,
                )
                function_name = (
                    "render_gate_b_epoch_observation"
                    if request["kind"] == "epoch"
                    else "render_gate_b_approval"
                )
                renderer = namespace.get(function_name)
                if not callable(renderer):
                    raise QualificationError("selected renderer function is absent")
                rendered = renderer(
                    {
                        "output_path": str(output_path),
                        "record": request["record"],
                    }
                )
                if not isinstance(rendered, bytes):
                    raise QualificationError("selected renderer did not return bytes")
                rendered_fd = _sealed_memfd(
                    f"ab16-gate-b-rendered-{next_sequence}",
                    rendered,
                )
                _publish_with_literal(
                    python_fd=args.python_fd,
                    publisher_fd=args.publisher_fd,
                    rendered_fd=rendered_fd,
                    directory_fd=directory_fd,
                    basename=output_path.name,
                )
                output_identity = _mode_identity(output_path)
                record = _strict_json(rendered, "rendered Gate-B record")
                retained.append(
                    {
                        "directory_fd": directory_fd,
                        "directory_signature": _signature(os.fstat(directory_fd)),
                        "output_identity": output_identity,
                        "output_path": output_path,
                        "rendered_fd": rendered_fd,
                        "request_fd": request_fd,
                        "sequence": next_sequence,
                    }
                )
                for item in retained:
                    item["directory_signature"] = _signature(
                        os.fstat(item["directory_fd"])
                    )
            except BaseException:
                os.close(directory_fd)
                raise
            _send_frame(
                control,
                {
                    "actor": actor,
                    "output_identity": output_identity,
                    "record": record,
                    "schema": OWNER_RESPONSE_SCHEMA,
                    "sequence": next_sequence,
                    "session_id": session_id,
                    "state": "PUBLISHED_FDS_RETAINED",
                    "status": "PASS",
                },
            )
            next_sequence += 1
        elif action == "ATTACH_BOOTSTRAP":
            _exact_keys(
                request,
                {"action", "schema", "session_id"},
                "bootstrap attach request",
            )
            if (
                received is None
                or request["schema"] != OWNER_REQUEST_SCHEMA
                or request["session_id"] != session_id
                or next_sequence != 3
                or bootstrap_channel is not None
            ):
                if received is not None:
                    os.close(received)
                raise QualificationError("bootstrap attach state drifted")
            bootstrap_channel = socket.socket(fileno=received)
            _send_frame(
                control,
                {
                    "schema": OWNER_RESPONSE_SCHEMA,
                    "session_id": session_id,
                    "state": "BOOTSTRAP_CHANNEL_ATTACHED",
                    "status": "PASS",
                },
            )
        elif action == "RELEASE":
            if received is not None:
                os.close(received)
                raise QualificationError("release request carried an unexpected descriptor")
            _exact_keys(
                request,
                {"action", "bootstrap_result_sha256", "schema", "session_id"},
                "owner release request",
            )
            if (
                request["schema"] != OWNER_RELEASE_SCHEMA
                or request["session_id"] != session_id
                or not handoff_complete
                or type(request["bootstrap_result_sha256"]) is not str
                or len(request["bootstrap_result_sha256"]) != 64
            ):
                raise QualificationError("owner release before complete readback")
            _send_frame(
                control,
                {
                    "schema": OWNER_RESPONSE_SCHEMA,
                    "session_id": session_id,
                    "state": "RELEASE_ACCEPTED",
                    "status": "PASS",
                },
            )
            return 0
        elif action == "ABORT":
            if received is not None:
                os.close(received)
            return 2
        else:
            if received is not None:
                os.close(received)
            raise QualificationError("unknown owner action")


class PersistentGateBOwner:
    """One exec-persistent Gate-B actor holding locks and publication FDs."""

    def __init__(
        self,
        *,
        python_path: Path,
        owner_source_path: Path,
        renderer_source_path: Path,
        renderer_identity: Mapping[str, object],
        mechanical_publisher: str,
        owner_driver: str,
        lock_paths: Sequence[Path | str] = DEFAULT_LOCK_PATHS,
    ) -> None:
        self.python_path = Path(os.path.abspath(python_path))
        self.owner_source_path = Path(os.path.abspath(owner_source_path))
        self.renderer_source_path = Path(os.path.abspath(renderer_source_path))
        self.renderer_identity = dict(renderer_identity)
        self.mechanical_publisher = mechanical_publisher
        self.owner_driver = owner_driver
        self.lock_paths = tuple(Path(os.path.abspath(os.fspath(path))) for path in lock_paths)
        if len(self.lock_paths) != 3 or len(set(self.lock_paths)) != 3:
            raise QualificationError("qualification requires exactly three distinct locks")
        self._descriptors: list[int] = []
        self._lock_fds: list[int] = []
        self._process: subprocess.Popen[bytes] | None = None
        self._control: socket.socket | None = None
        self._bootstrap_channel: socket.socket | None = None
        self.actor: dict[str, object] = {}
        self.lock_identities: list[dict[str, object]] = []
        self.session_id = ""

    def _retain_descriptor(self, descriptor: int, *, is_lock: bool = False) -> int:
        try:
            self._descriptors.append(descriptor)
        except BaseException as exc:
            owner = _OwnedDescriptor()
            owner.acquire(descriptor)
            owner.close_preserving(exc)
            raise
        if is_lock:
            try:
                self._lock_fds.append(descriptor)
            except BaseException as exc:
                self._descriptors.pop()
                owner = _OwnedDescriptor()
                owner.acquire(descriptor)
                owner.close_preserving(exc)
                raise
        return descriptor

    def _close_socket(
        self,
        attribute: str,
        *,
        errors: list[BaseException],
    ) -> None:
        channel = getattr(self, attribute)
        if channel is None:
            return
        setattr(self, attribute, None)
        try:
            channel.close()
        except BaseException as exc:
            errors.append(exc)

    @staticmethod
    def _kill_process(
        process: subprocess.Popen[bytes],
        *,
        errors: list[BaseException],
    ) -> None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        except BaseException as exc:
            errors.append(exc)

    def _cleanup(self, primary: BaseException | None) -> None:
        errors: list[BaseException] = []
        process = self._process
        control = self._control
        process_alive = False
        if process is not None:
            try:
                process_alive = process.poll() is None
            except BaseException as exc:
                errors.append(exc)
                process_alive = True
        if process is not None and process_alive:
            abort_sent = False
            if control is not None:
                try:
                    _send_frame(
                        control,
                        {
                            "action": "ABORT",
                            "schema": OWNER_REQUEST_SCHEMA,
                            "session_id": self.session_id,
                        },
                    )
                    abort_sent = True
                except BaseException as exc:
                    errors.append(exc)
            if not abort_sent:
                self._kill_process(process, errors=errors)
            try:
                _wait_process(process, timeout=5)
            except subprocess.TimeoutExpired:
                self._kill_process(process, errors=errors)
                try:
                    _wait_process(process, timeout=None)
                except BaseException as exc:
                    errors.append(exc)
            except BaseException as exc:
                errors.append(exc)
                self._kill_process(process, errors=errors)
                try:
                    _wait_process(process, timeout=None)
                except BaseException as reap_exc:
                    errors.append(reap_exc)
        elif process is not None:
            try:
                _wait_process(process, timeout=0)
            except BaseException as exc:
                errors.append(exc)

        self._close_socket("_bootstrap_channel", errors=errors)
        self._close_socket("_control", errors=errors)

        if process is not None and process.stderr is not None:
            stderr = process.stderr
            process.stderr = None
            try:
                stderr.close()
            except BaseException as exc:
                errors.append(exc)
        self._process = None

        descriptors = tuple(self._descriptors)
        self._descriptors.clear()
        self._lock_fds.clear()
        try:
            _close_descriptors(descriptors, primary=primary)
        except BaseException as exc:
            errors.append(exc)

        if primary is not None:
            for cleanup_error in errors:
                primary.add_note(
                    "Gate-B owner cleanup failed: "
                    f"{type(cleanup_error).__name__}: {cleanup_error}"
                )
        elif errors:
            _raise_cleanup_error("Gate-B owner", errors[0])

    def __enter__(self) -> PersistentGateBOwner:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, traceback
        primary = exc if isinstance(exc, BaseException) else None
        self._cleanup(primary)

    def start(self) -> None:
        if self._process is not None:
            raise QualificationError("owner session was already started")
        try:
            for path in self.lock_paths:
                self._retain_descriptor(_acquire_lock(path), is_lock=True)
            python_fd = self._retain_descriptor(_open_regular(self.python_path))
            owner_fd = self._retain_descriptor(_open_regular(self.owner_source_path))
            renderer_raw = _read_stable_path(self.renderer_source_path, label="Gate-B renderer")
            renderer_fd = self._retain_descriptor(
                _sealed_memfd("ab16-gate-b-renderer", renderer_raw)
            )
            publisher_fd = self._retain_descriptor(
                _sealed_memfd(
                    "ab16-gate-b-publisher",
                    self.mechanical_publisher.encode("utf-8"),
                )
            )
            parent, child = socket.socketpair(
                socket.AF_UNIX,
                socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
            )
            self._control = parent
            child_failure: BaseException | None = None
            try:
                parent.settimeout(60)
                python_identity = _mode_identity(self.python_path)
                owner_identity = _mode_identity(self.owner_source_path)
                expected = _canonical_json(
                    {"owner_source": owner_identity, "python": python_identity}
                ).decode("utf-8").strip()
                arguments = [
                    str(self.python_path),
                    "-I",
                    "-B",
                    "-c",
                    self.owner_driver,
                    expected,
                    str(python_fd),
                    str(owner_fd),
                    "--control-fd",
                    str(child.fileno()),
                    "--renderer-fd",
                    str(renderer_fd),
                    "--publisher-fd",
                    str(publisher_fd),
                    "--python-fd",
                    str(python_fd),
                    "--renderer-identity",
                    _canonical_json(self.renderer_identity).decode().strip(),
                    "--owner-source-identity",
                    _canonical_json(owner_identity).decode().strip(),
                    "--python-identity",
                    _canonical_json(python_identity).decode().strip(),
                    "--driver-identity",
                    _canonical_json(_literal_identity(self.owner_driver)).decode().strip(),
                ]
                for path, descriptor in zip(
                    self.lock_paths,
                    self._lock_fds,
                    strict=True,
                ):
                    arguments.extend(
                        ("--lock-path", str(path), "--lock-fd", str(descriptor))
                    )
                pass_fds = (
                    python_fd,
                    owner_fd,
                    renderer_fd,
                    publisher_fd,
                    child.fileno(),
                    *self._lock_fds,
                )
                self._process = subprocess.Popen(
                    arguments,
                    close_fds=True,
                    env=_clean_environment(),
                    executable=f"/proc/self/fd/{python_fd}",
                    pass_fds=pass_fds,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
            except BaseException as exc:
                child_failure = exc
                raise
            finally:
                try:
                    child.close()
                except BaseException as close_exc:
                    if child_failure is not None:
                        child_failure.add_note(
                            "child control socket cleanup failed: "
                            f"{type(close_exc).__name__}: {close_exc}"
                        )
                    else:
                        raise
            ready = _recv_frame(parent)
            if ready.get("status") != "PASS" or ready.get("state") != "READY":
                raise QualificationError("owner did not publish READY")
            self.actor = dict(ready["actor"])
            self.lock_identities = list(ready["lock_identities"])
            self.session_id = str(ready["session_id"])
            if (
                self.actor.get("pid") != self._process.pid
                or self.actor.get("pid_starttime") != _proc_starttime(self._process.pid)
            ):
                raise QualificationError("owner READY actor identity drifted")
        except BaseException as exc:
            self._cleanup(exc)
            raise

    def is_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def publish(
        self,
        *,
        kind: str,
        output_path: Path | str,
        record: Mapping[str, object],
    ) -> dict[str, Any]:
        if not self.is_alive() or self._control is None:
            raise QualificationError("owner is not live")
        sequence = 1 if kind == "epoch" else 2
        _send_frame(
            self._control,
            {
                "action": "PUBLISH",
                "kind": kind,
                "output_path": str(Path(os.path.abspath(os.fspath(output_path)))),
                "record": dict(record),
                "schema": OWNER_REQUEST_SCHEMA,
                "sequence": sequence,
                "session_id": self.session_id,
            },
        )
        response = _recv_frame(self._control)
        if response.get("status") != "PASS":
            raise QualificationError(
                f"OWNER_REJECTED:{response.get('code', 'UNKNOWN')}"
            )
        if (
            response.get("actor") != self.actor
            or response.get("session_id") != self.session_id
            or response.get("sequence") != sequence
        ):
            raise QualificationError("owner publication response identity drifted")
        return dict(response["record"])

    def attach_bootstrap_channel(self) -> socket.socket:
        if self._bootstrap_channel is not None or self._control is None:
            raise QualificationError("bootstrap channel was already attached")
        supervisor, owner = socket.socketpair(
            socket.AF_UNIX,
            socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC,
        )
        failure: BaseException | None = None
        try:
            _send_frame(
                self._control,
                {
                    "action": "ATTACH_BOOTSTRAP",
                    "schema": OWNER_REQUEST_SCHEMA,
                    "session_id": self.session_id,
                },
                descriptors=(owner.fileno(),),
            )
            response = _recv_frame(self._control)
            if (
                response.get("status") != "PASS"
                or response.get("state") != "BOOTSTRAP_CHANNEL_ATTACHED"
            ):
                raise QualificationError("owner rejected bootstrap channel")
            self._bootstrap_channel = supervisor
        except BaseException as exc:
            failure = exc
            try:
                supervisor.close()
            except BaseException as close_exc:
                exc.add_note(
                    "bootstrap supervisor socket cleanup failed: "
                    f"{type(close_exc).__name__}: {close_exc}"
                )
            raise
        finally:
            try:
                owner.close()
            except BaseException as close_exc:
                if failure is not None:
                    failure.add_note(
                        "bootstrap owner socket cleanup failed: "
                        f"{type(close_exc).__name__}: {close_exc}"
                    )
                else:
                    if self._bootstrap_channel is supervisor:
                        self._bootstrap_channel = None
                    try:
                        supervisor.close()
                    except BaseException as supervisor_close_exc:
                        close_exc.add_note(
                            "bootstrap supervisor socket cleanup failed: "
                            f"{type(supervisor_close_exc).__name__}: "
                            f"{supervisor_close_exc}"
                        )
                    raise
        return supervisor

    def duplicate_lock_fds(self) -> tuple[int, ...]:
        duplicated: list[_OwnedDescriptor] = []
        try:
            for descriptor in self._lock_fds:
                owner = _OwnedDescriptor()
                duplicated.append(owner)
                owner.acquire(os.dup(descriptor))
            return tuple(owner.release() for owner in duplicated)
        except BaseException as exc:
            for owner in reversed(duplicated):
                if owner.owned:
                    owner.close_preserving(exc)
            raise

    def release(self, *, bootstrap_result: bytes) -> None:
        if self._control is None or not self.is_alive():
            raise QualificationError("owner is not live for release")
        try:
            _send_frame(
                self._control,
                {
                    "action": "RELEASE",
                    "bootstrap_result_sha256": hashlib.sha256(bootstrap_result).hexdigest(),
                    "schema": OWNER_RELEASE_SCHEMA,
                    "session_id": self.session_id,
                },
            )
            response = _recv_frame(self._control)
            if (
                response.get("status") != "PASS"
                or response.get("state") != "RELEASE_ACCEPTED"
            ):
                raise QualificationError("owner rejected terminal release")
            assert self._process is not None
            try:
                return_code = _wait_process(self._process, timeout=5)
            except subprocess.TimeoutExpired as exc:
                raise QualificationError("owner did not exit after release") from exc
            if return_code != 0:
                raise QualificationError(f"owner exited with {return_code}")
        except BaseException as exc:
            self._cleanup(exc)
            raise


def _assert_absent_directory_target(path: Path | str, label: str) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    parent = _OwnedDescriptor()
    try:
        parent.acquire(_open_directory(absolute.parent))
        try:
            os.stat(
                absolute.name,
                dir_fd=parent.descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            raise QualificationError(f"{label} already exists; no-overwrite applies")
    except BaseException as exc:
        parent.close_preserving(exc)
        raise
    close_error = parent.close()
    if close_error is not None:
        _raise_cleanup_error(f"{label} parent descriptor", close_error)
    return absolute


def _mkdir_exclusive(path: Path | str, *, mode: int = 0o700) -> Path:
    absolute = _assert_absent_directory_target(path, "directory")
    parent = _OwnedDescriptor()
    try:
        parent.acquire(_open_directory(absolute.parent))
        os.mkdir(absolute.name, mode=mode, dir_fd=parent.descriptor)
        os.fsync(parent.descriptor)
    except BaseException as exc:
        parent.close_preserving(exc)
        raise
    close_error = parent.close()
    if close_error is not None:
        _raise_cleanup_error("exclusive directory parent descriptor", close_error)

    descriptor = _OwnedDescriptor()
    try:
        descriptor.acquire(_open_directory(absolute))
        metadata = os.fstat(descriptor.descriptor)
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != mode:
            raise QualificationError(f"exclusive directory mode drifted: {absolute}")
    except BaseException as exc:
        descriptor.close_preserving(exc)
        raise
    close_error = descriptor.close()
    if close_error is not None:
        _raise_cleanup_error("exclusive directory descriptor", close_error)
    return absolute


def _write_exclusive(path: Path | str, raw: bytes, *, mode: int = 0o444) -> dict[str, object]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    parent = _OwnedDescriptor()
    descriptor = _OwnedDescriptor()
    try:
        parent.acquire(_open_directory(absolute.parent))
        descriptor.acquire(
            os.open(
                absolute.name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                mode,
                dir_fd=parent.descriptor,
            )
        )
        view = memoryview(raw)
        while view:
            written = os.write(descriptor.descriptor, view)
            if written <= 0:
                raise QualificationError(f"exclusive write was short: {absolute}")
            view = view[written:]
        os.fchmod(descriptor.descriptor, mode)
        os.fsync(descriptor.descriptor)
        close_error = descriptor.close()
        if close_error is not None:
            raise close_error
        os.fsync(parent.descriptor)
    except BaseException as exc:
        descriptor.close_preserving(exc)
        parent.close_preserving(exc)
        raise
    close_error = parent.close()
    if close_error is not None:
        _raise_cleanup_error("exclusive publication parent descriptor", close_error)
    identity = _mode_identity(absolute)
    if (
        identity["mode"] != mode
        or identity["size_bytes"] != len(raw)
        or identity["sha256"] != hashlib.sha256(raw).hexdigest()
    ):
        raise QualificationError(f"exclusive publication replay drifted: {absolute}")
    return identity


def _meminfo() -> dict[str, int]:
    result: dict[str, int] = {}
    try:
        raw = Path("/proc/meminfo").read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise QualificationError("resource gate cannot read /proc/meminfo") from exc
    for line in raw.splitlines():
        fields = line.replace(":", "").split()
        if len(fields) == 3 and fields[1].isdigit() and fields[2] == "kB":
            result[fields[0]] = int(fields[1]) * 1024
    return result


def _ancestor_pids() -> set[int]:
    result: set[int] = set()
    current = os.getpid()
    while current > 1 and current not in result:
        result.add(current)
        try:
            raw = Path(f"/proc/{current}/stat").read_text(encoding="ascii")
            closing = raw.rfind(")")
            fields = raw[closing + 2 :].split()
            current = int(fields[1])
        except (FileNotFoundError, ProcessLookupError, PermissionError, IndexError, ValueError):
            break
    return result


def _same_uid_conflicts() -> list[dict[str, object]]:
    ancestors = _ancestor_pids()
    found: list[dict[str, object]] = []
    for item in Path("/proc").iterdir():
        if not item.name.isdigit():
            continue
        pid = int(item.name)
        if pid in ancestors:
            continue
        try:
            if item.stat().st_uid != os.getuid():
                continue
            command = (item / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8",
                "replace",
            ).strip()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        lowered = command.lower()
        if command and any(pattern in lowered for pattern in CONFLICT_PATTERNS):
            found.append({"command": command, "pid": pid})
    return found


def _resource_gate(
    path: Path | str,
    *,
    stage: str,
    actor: Mapping[str, object],
    session_id: str,
    lock_identities: Sequence[Mapping[str, object]],
    meminfo: Mapping[str, int] | None = None,
    disk_free: int | None = None,
    conflicts: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    memory = dict(_meminfo() if meminfo is None else meminfo)
    free = shutil.disk_usage(path).free if disk_free is None else disk_free
    heavy = list(_same_uid_conflicts() if conflicts is None else conflicts)
    if (
        type(memory.get("MemAvailable")) is not int
        or memory["MemAvailable"] < MIN_MEM_AVAILABLE
        or type(memory.get("SwapFree")) is not int
        or memory["SwapFree"] < MIN_SWAP_FREE
        or type(free) is not int
        or free < MIN_DISK_BYTES
        or heavy
    ):
        raise QualificationError(
            "Gate-B resource gate failed: "
            f"MemAvailable={memory.get('MemAvailable')}, "
            f"SwapFree={memory.get('SwapFree')}, disk={free}, conflicts={heavy}"
        )
    return {
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "created_at_utc": _utc_now(),
        "lock_identities": [dict(item) for item in lock_identities],
        "measurements": {
            "disk_free_bytes": free,
            "mem_available_bytes": memory["MemAvailable"],
            "same_uid_conflicts": [],
            "swap_free_bytes": memory["SwapFree"],
        },
        "owner_actor": dict(actor),
        "qualification_session_id": session_id,
        "schema_version": RESOURCE_GATE_SCHEMA,
        "stage": stage,
        "status": "PASS",
        "thresholds": {
            "disk_free_bytes_minimum": MIN_DISK_BYTES,
            "mem_available_bytes_minimum": MIN_MEM_AVAILABLE,
            "swap_free_bytes_minimum": MIN_SWAP_FREE,
        },
    }


def _load_bootstrap(repository: Path) -> Any:
    source = (
        repository
        / "docs"
        / "research"
        / "noncert_cuts_ab16_20260724"
        / "ab16_campaign_bootstrap_v2.py"
    )
    name = "_ab16_gate_b_qualification_bootstrap_v2"
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise QualificationError("Gate-B bootstrap module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _prepare_qualification(args: argparse.Namespace, bootstrap: Any) -> dict[str, Any]:
    repository = Path(os.path.abspath(args.repository_root))
    campaign = _assert_absent_directory_target(args.campaign_dir, "campaign directory")
    output = _assert_absent_directory_target(args.output_dir, "qualification output directory")
    bootstrap._replay_prepackage_closure()  # noqa: SLF001
    if repository != Path(str(bootstrap._BOOTSTRAP_BINDING["repository_root"])):  # noqa: SLF001
        raise QualificationError("qualification repository differs from fixed Git top level")
    gate_a, gate_a_identity = bootstrap._canonical_record(  # noqa: SLF001
        args.gate_a_receipt,
        "Gate-A receipt",
    )
    gate_a = bootstrap._validate_gate_a(gate_a)  # noqa: SLF001
    candidate, candidate_identity = bootstrap._canonical_record(  # noqa: SLF001
        args.offline_candidate,
        "offline candidate",
    )
    candidate = bootstrap.validate_candidate(candidate)
    strict_inputs = bootstrap._production_strict_inputs(repository, args)  # noqa: SLF001
    system_tools = bootstrap._cli_system_tools(args)  # noqa: SLF001
    planned, scripts, system_paths, _strict_paths = bootstrap._planned_source_identities(  # noqa: SLF001
        strict_input_paths=strict_inputs,
        system_tool_paths=system_tools,
    )
    planned_digest = bootstrap._source_set_digest(planned)  # noqa: SLF001
    scalar_fields = {
        "planned_source_set_digest",
        "repository_head",
        "repository_root",
        "run_nonce",
        "target_campaign_dir",
    }
    if (
        candidate["gate_a_receipt_identity"] != gate_a_identity
        or any(candidate[field] != gate_a[field] for field in scalar_fields)
        or candidate["planned_source_identities"] != planned
        or candidate["planned_source_set_digest"] != planned_digest
        or gate_a["target_campaign_dir"] != str(campaign)
        or gate_a["repository_root"] != str(repository)
    ):
        raise QualificationError("Gate-A/candidate/current source binding drifted")
    observation_raw = _read_stable_path(
        args.planned_source_observation,
        label="planned-source observation",
        limit=4 * 1024 * 1024,
    )
    observation = _strict_unterminated_json(
        observation_raw,
        "planned-source observation",
    )
    if observation != {
        "planned_source_identities": planned,
        "planned_source_set_digest": planned_digest,
    }:
        raise QualificationError("planned-source observation differs from candidate/current bytes")
    if gate_a["approval_id"] == args.approval_id:
        raise QualificationError("Gate-B approval identity must differ from Gate A")
    if (
        type(args.approval_id) is not str
        or bootstrap.APPROVAL_ID_RE.fullmatch(args.approval_id) is None
    ):
        raise QualificationError("Gate-B approval_id is malformed")
    bootstrap._replay_prepackage_closure(planned=planned)  # noqa: SLF001
    return {
        "bootstrap": bootstrap,
        "campaign": campaign,
        "candidate": candidate,
        "candidate_identity": candidate_identity,
        "gate_a": gate_a,
        "gate_a_identity": gate_a_identity,
        "observation_identity": {
            "path": str(Path(os.path.abspath(args.planned_source_observation))),
            "sha256": hashlib.sha256(observation_raw).hexdigest(),
            "size_bytes": len(observation_raw),
        },
        "output": output,
        "planned": planned,
        "planned_digest": planned_digest,
        "repository": repository,
        "scripts": scripts,
        "strict_inputs": strict_inputs,
        "system_paths": system_paths,
        "system_tools": system_tools,
    }


def _run_pinned_gate_a_preflight(
    context: Mapping[str, Any],
    args: argparse.Namespace,
    output_dir: Path,
) -> None:
    scripts = context["scripts"]
    python_path = Path(context["system_paths"]["python3_13"])
    entrypoint = Path(scripts["gate_a_pinned_entrypoint_v2"])
    python_owner = _OwnedDescriptor()
    entrypoint_owner = _OwnedDescriptor()
    try:
        python_fd = python_owner.acquire(_open_regular(python_path))
        entrypoint_fd = entrypoint_owner.acquire(_open_regular(entrypoint))
        observation = context["observation_identity"]
        completed = subprocess.run(
            [
                str(python_path),
                "-I",
                "-B",
                f"/proc/self/fd/{entrypoint_fd}",
                "--planned-source-observation",
                observation["path"],
                "--planned-source-observation-size",
                str(observation["size_bytes"]),
                "--planned-source-observation-sha256",
                observation["sha256"],
                "--planned-source-set-digest",
                context["planned_digest"],
                "record-preflight",
                "--",
                "--authority-root",
                str(Path(os.path.abspath(args.gate_a_authority_root))),
                "--repository-root",
                str(context["repository"]),
                "--output-dir",
                str(output_dir),
            ],
            check=False,
            close_fds=True,
            cwd=context["repository"],
            env=_preflight_environment(),
            executable=f"/proc/self/fd/{python_fd}",
            pass_fds=(python_fd, entrypoint_fd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except BaseException as exc:
        entrypoint_owner.close_preserving(exc)
        python_owner.close_preserving(exc)
        raise
    close_errors = [
        error
        for error in (entrypoint_owner.close(), python_owner.close())
        if error is not None
    ]
    if close_errors:
        _raise_cleanup_error("pinned Gate-A preflight descriptors", close_errors[0])
    try:
        summary = json.loads(completed.stdout)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise QualificationError("pinned Gate-A preflight summary is malformed") from exc
    if (
        completed.returncode != 0
        or completed.stderr not in _PERMITTED_PINNED_PYTHON_STDERR
        or type(summary) is not dict
        or summary.get("status") != "PASS"
    ):
        raise QualificationError(
            "pinned Gate-A final full preflight failed: "
            f"exit={completed.returncode}; stderr={completed.stderr!r}"
        )


def _run_bootstrap_child(
    context: Mapping[str, Any],
    args: argparse.Namespace,
    *,
    gate_b_approval: Path,
    qualification_fd: int,
    qualification_lock_fds: Mapping[str, int],
) -> tuple[bytes, dict[str, Any]]:
    python_path = Path(context["system_paths"]["python3_13"])
    bootstrap_path = Path(context["scripts"]["ab16_campaign_bootstrap_v2"])
    python_owner = _OwnedDescriptor()
    bootstrap_owner = _OwnedDescriptor()
    try:
        python_fd = python_owner.acquire(_open_regular(python_path))
        bootstrap_fd = bootstrap_owner.acquire(_open_regular(bootstrap_path))
        command = [
            str(python_path),
            "-I",
            "-B",
            f"/proc/self/fd/{bootstrap_fd}",
            "bootstrap",
            "--campaign-dir",
            str(context["campaign"]),
            "--repository-root",
            str(context["repository"]),
            "--gate-a-receipt",
            str(Path(os.path.abspath(args.gate_a_receipt))),
            "--history-freeze-manifest",
            str(Path(os.path.abspath(args.history_freeze_manifest))),
            "--cuts-mandatory-schedule",
            str(Path(os.path.abspath(args.cuts_mandatory_schedule))),
            "--legacy-control-a002",
            str(Path(os.path.abspath(args.legacy_control_a002))),
            "--python3-13",
            str(context["system_tools"]["python3_13"]),
            "--attestor-python",
            str(context["system_tools"]["attestor_python"]),
            "--busctl",
            str(context["system_tools"]["busctl"]),
            "--git",
            str(context["system_tools"]["git"]),
            "--libsystemd",
            str(context["system_tools"]["libsystemd"]),
            "--sudo",
            str(context["system_tools"]["sudo"]),
            "--systemctl",
            str(context["system_tools"]["systemctl"]),
            "--systemd-run",
            str(context["system_tools"]["systemd_run"]),
            "--offline-candidate",
            str(Path(os.path.abspath(args.offline_candidate))),
            "--gate-b-approval",
            str(gate_b_approval),
            "--gate-b-qualification-fd",
            str(qualification_fd),
        ]
        for path in LOCK_PATHS:
            command.extend(
                (
                    "--gate-b-qualification-lock-fd",
                    f"{path}={qualification_lock_fds[path]}",
                )
            )
        completed = subprocess.run(
            command,
            check=False,
            close_fds=True,
            cwd=context["repository"],
            env=_clean_environment(),
            executable=f"/proc/self/fd/{python_fd}",
            pass_fds=(
                python_fd,
                bootstrap_fd,
                qualification_fd,
                *qualification_lock_fds.values(),
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except BaseException as exc:
        bootstrap_owner.close_preserving(exc)
        python_owner.close_preserving(exc)
        raise
    close_errors = [
        error
        for error in (bootstrap_owner.close(), python_owner.close())
        if error is not None
    ]
    if close_errors:
        _raise_cleanup_error("Gate-B bootstrap child descriptors", close_errors[0])
    if (
        completed.returncode != 0
        or completed.stderr not in _PERMITTED_PINNED_PYTHON_STDERR
    ):
        raise QualificationError(
            "Gate-B bootstrap child failed: "
            f"exit={completed.returncode}; stderr={completed.stderr!r}"
        )
    result = _strict_json(completed.stdout, "Gate-B bootstrap result")
    if (
        type(result) is not dict
        or result.get("schema") != context["bootstrap"].RESULT_SCHEMA
        or result.get("status") != "FORMAL_CAMPAIGN_AUTHORITY_READY_NO_UNIT_LAUNCHED"
        or result.get("campaign_dir") != str(context["campaign"])
        or result.get("gate_b_qualification_handoff", {}).get("status") != "PASS"
    ):
        raise QualificationError("Gate-B bootstrap result readback drifted")
    return completed.stdout, result


def _build_epoch_record(
    context: Mapping[str, Any],
    *,
    capture: Mapping[str, object],
    final_identity: Mapping[str, object],
) -> dict[str, object]:
    gate_a = context["gate_a"]
    bootstrap = context["bootstrap"]
    return {
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "candidate_identity": context["candidate_identity"],
        "capture_transcript": capture["transcript"],
        "created_at_utc": _utc_now(),
        "final_full_preflight_receipt_identity": dict(final_identity),
        "gate_a_receipt_identity": context["gate_a_identity"],
        "manager_epoch": capture["manager_epoch"],
        "planned_source_set_digest": context["planned_digest"],
        "purpose": bootstrap.GATE_B_EPOCH_PURPOSE,
        "repository_head": gate_a["repository_head"],
        "repository_root": gate_a["repository_root"],
        "run_nonce": gate_a["run_nonce"],
        "schema_version": bootstrap.GATE_B_EPOCH_SCHEMA,
        "status": "PASS",
        "target_campaign_dir": gate_a["target_campaign_dir"],
    }


def _build_approval_record(
    context: Mapping[str, Any],
    args: argparse.Namespace,
    *,
    final_identity: Mapping[str, object],
    epoch_identity: Mapping[str, object],
) -> dict[str, object]:
    gate_a = context["gate_a"]
    bootstrap = context["bootstrap"]
    return {
        "approval_id": args.approval_id,
        "arm_launch_authorized": False,
        "candidate_identity": context["candidate_identity"],
        "created_at_utc": _utc_now(),
        "decision": "APPROVED",
        "final_full_preflight_receipt_identity": dict(final_identity),
        "formal_campaign_creation_authorized": True,
        "gate": "B",
        "gate_a_receipt_identity": context["gate_a_identity"],
        "gate_b_epoch_observation_identity": dict(epoch_identity),
        "planned_source_set_digest": context["planned_digest"],
        "purpose": bootstrap.GATE_B_PURPOSE,
        "repository_head": gate_a["repository_head"],
        "repository_root": gate_a["repository_root"],
        "run_nonce": gate_a["run_nonce"],
        "schema_version": bootstrap.GATE_B_SCHEMA,
        "target_campaign_dir": gate_a["target_campaign_dir"],
    }


def qualify(args: argparse.Namespace) -> dict[str, object]:
    repository = Path(os.path.abspath(args.repository_root))
    bootstrap = _load_bootstrap(repository)
    context = _prepare_qualification(args, bootstrap)
    renderer_identity = {
        field: context["planned"]["script.ab16_campaign_bootstrap_v2"][field]
        for field in ("mode", "path", "sha256", "size_bytes")
    }
    owner_source = Path(context["scripts"]["ab16_gate_b_qualification_v1"])
    with PersistentGateBOwner(
        python_path=Path(context["system_paths"]["python3_13"]),
        owner_source_path=owner_source,
        renderer_source_path=Path(context["scripts"]["ab16_campaign_bootstrap_v2"]),
        renderer_identity=renderer_identity,
        mechanical_publisher=bootstrap.OWNER_OEXCL_PUBLISH_V1,
        owner_driver=bootstrap.GATE_B_OWNER_DRIVER_V1,
    ) as owner:
        # Revalidate the current committed source closure only after all three
        # locks are held, immediately before the first resource gate.
        context = _prepare_qualification(args, bootstrap)
        gate_one = _resource_gate(
            context["output"].parent,
            stage="BEFORE_FINAL_FULL_PREFLIGHT",
            actor=owner.actor,
            session_id=owner.session_id,
            lock_identities=owner.lock_identities,
        )
        output = _mkdir_exclusive(context["output"])
        resource_dir = _mkdir_exclusive(output / "resource-gates")
        gate_one_identity = _write_exclusive(
            resource_dir / "before-final-full-preflight.json",
            _canonical_json(gate_one),
        )

        final_dir = output / "final-full-preflight"
        _run_pinned_gate_a_preflight(context, args, final_dir)
        final_receipt_path = final_dir / "receipt.json"
        final_receipt, final_identity = _unterminated_mode_record(
            final_receipt_path,
            "Gate-B final full-preflight receipt",
        )
        bootstrap._validate_final_full_preflight(  # noqa: SLF001
            final_receipt,
            gate_a=context["gate_a"],
            planned=context["planned"],
        )
        old_preflight = context["gate_a"]["full_preflight_receipt_identity"]
        if (
            final_identity["path"] == old_preflight["path"]
            or final_identity["sha256"] == old_preflight["sha256"]
        ):
            raise QualificationError("fresh Gate-B full preflight aliases Gate A")

        capture = bootstrap._capture_epoch(  # noqa: SLF001
            scripts=context["scripts"],
            system_paths=context["system_paths"],
        )
        if capture["manager_epoch"] != context["gate_a"]["manager_epoch"]:
            raise QualificationError("fresh Gate-B manager epoch differs from Gate A")
        epoch_path = output / "gate-b-epoch-observation.json"
        epoch = owner.publish(
            kind="epoch",
            output_path=epoch_path,
            record=_build_epoch_record(
                context,
                capture=capture,
                final_identity=final_identity,
            ),
        )
        epoch_identity = _mode_identity(epoch_path)
        bootstrap._validate_gate_b_epoch_observation(  # noqa: SLF001
            epoch,
            gate_a=context["gate_a"],
            gate_a_identity=context["gate_a_identity"],
            candidate_identity=context["candidate_identity"],
            final_full_preflight_identity=final_identity,
        )

        gate_two = _resource_gate(
            output,
            stage="AFTER_FINAL_FULL_PREFLIGHT_BEFORE_GATE_B_APPROVAL",
            actor=owner.actor,
            session_id=owner.session_id,
            lock_identities=owner.lock_identities,
        )
        gate_two_identity = _write_exclusive(
            resource_dir / "after-final-full-preflight.json",
            _canonical_json(gate_two),
        )
        approval_path = output / "gate-b-approval.json"
        approval = owner.publish(
            kind="approval",
            output_path=approval_path,
            record=_build_approval_record(
                context,
                args,
                final_identity=final_identity,
                epoch_identity=epoch_identity,
            ),
        )
        approval_identity = _mode_identity(approval_path)
        bootstrap._validate_gate_b(approval)  # noqa: SLF001
        epoch_session = epoch["publisher"]["qualification_session"]
        approval_session = approval["publisher"]["qualification_session"]
        if (
            epoch["publisher"]["actor"] != approval["publisher"]["actor"]
            or epoch_session["session_id"] != approval_session["session_id"]
            or epoch_session["lock_identities"] != approval_session["lock_identities"]
            or epoch_session["sequence"] != 1
            or approval_session["sequence"] != 2
        ):
            raise QualificationError("Gate-B persistent owner join drifted")

        channel = owner.attach_bootstrap_channel()
        duplicated = owner.duplicate_lock_fds()
        lock_fds = dict(zip(LOCK_PATHS, duplicated, strict=True))
        bootstrap_failure: BaseException | None = None
        try:
            bootstrap_raw, bootstrap_result = _run_bootstrap_child(
                context,
                args,
                gate_b_approval=approval_path,
                qualification_fd=channel.fileno(),
                qualification_lock_fds=lock_fds,
            )
        except BaseException as exc:
            bootstrap_failure = exc
            raise
        finally:
            _close_descriptors(duplicated, primary=bootstrap_failure)
        owner.release(bootstrap_result=bootstrap_raw)

    return {
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "bootstrap_result": bootstrap_result,
        "campaign_dir": str(context["campaign"]),
        "final_full_preflight_receipt_identity": final_identity,
        "gate_b_approval_identity": approval_identity,
        "gate_b_epoch_observation_identity": epoch_identity,
        "qualification_output_dir": str(context["output"]),
        "resource_gate_identities": [gate_one_identity, gate_two_identity],
        "schema": QUALIFICATION_SCHEMA,
        "status": "FORMAL_CAMPAIGN_AUTHORITY_READY_NO_UNIT_LAUNCHED",
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    owner = commands.add_parser("owner")
    owner.add_argument("--control-fd", type=int, required=True)
    owner.add_argument("--renderer-fd", type=int, required=True)
    owner.add_argument("--publisher-fd", type=int, required=True)
    owner.add_argument("--python-fd", type=int, required=True)
    owner.add_argument("--renderer-identity", required=True)
    owner.add_argument("--owner-source-identity", required=True)
    owner.add_argument("--python-identity", required=True)
    owner.add_argument("--driver-identity", required=True)
    owner.add_argument("--lock-path", action="append", required=True)
    owner.add_argument("--lock-fd", action="append", type=int, required=True)
    qualify_parser = commands.add_parser("qualify")
    qualify_parser.add_argument("--repository-root", type=Path, required=True)
    qualify_parser.add_argument("--campaign-dir", type=Path, required=True)
    qualify_parser.add_argument("--output-dir", type=Path, required=True)
    qualify_parser.add_argument("--gate-a-authority-root", type=Path, required=True)
    qualify_parser.add_argument("--gate-a-receipt", type=Path, required=True)
    qualify_parser.add_argument("--offline-candidate", type=Path, required=True)
    qualify_parser.add_argument("--planned-source-observation", type=Path, required=True)
    qualify_parser.add_argument("--approval-id", required=True)
    qualify_parser.add_argument("--history-freeze-manifest", type=Path, required=True)
    qualify_parser.add_argument("--cuts-mandatory-schedule", type=Path, required=True)
    qualify_parser.add_argument("--legacy-control-a002", type=Path, required=True)
    qualify_parser.add_argument(
        "--python3-13",
        type=Path,
        default=Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13"),
    )
    qualify_parser.add_argument("--attestor-python", type=Path, default=Path("/usr/bin/python3.14"))
    qualify_parser.add_argument("--busctl", type=Path, default=Path("/usr/bin/busctl"))
    qualify_parser.add_argument("--git", type=Path, default=Path("/usr/bin/git"))
    qualify_parser.add_argument("--libsystemd", type=Path, default=Path("/usr/lib/libsystemd.so.0"))
    qualify_parser.add_argument("--sudo", type=Path, default=Path("/usr/bin/sudo"))
    qualify_parser.add_argument("--systemctl", type=Path, default=Path("/usr/bin/systemctl"))
    qualify_parser.add_argument("--systemd-run", type=Path, default=Path("/usr/bin/systemd-run"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "owner":
            return _owner_main(args)
        if args.command == "qualify":
            result = qualify(args)
            sys.stdout.buffer.write(_canonical_json(result))
            return 0
        raise QualificationError("unknown qualification command")
    except Exception as exc:
        sys.stderr.buffer.write(
            _canonical_json(
                {
                    "error": str(exc),
                    "schema": QUALIFICATION_SCHEMA,
                    "status": "FAIL_CLOSED",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
