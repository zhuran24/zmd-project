#!/usr/bin/env python3
"""Read-only privileged attestor for one systemd user-manager executable.

The file is designed to be supplied as exact bytes on stdin to a pinned
``python -I -c`` loader running under ``sudo -n``.  Its privileged surface is
limited to same-file-descriptor reads of procfs and the manager executable.
It never writes files, sends signals, manages units, starts subprocesses, or
uses the network.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Sequence


SCHEMA = "noncert-cuts-privileged-manager-attestation-v4"
MAX_PROC_STAT_BYTES = 1 << 20
MAX_BOOT_ID_BYTES = 128
MAX_EXECUTABLE_BYTES = 1 << 30

_OWNER_RE = re.compile(r":[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\Z")
_BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_BOOT_ID_RAW_RE = re.compile(
    rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    rb"[0-9a-f]{4}-[0-9a-f]{12}\n\Z"
)


class AttestorError(RuntimeError):
    """Fail-closed request, procfs, or executable identity failure."""


def _stable_pseudo_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_uid,
        metadata.st_gid,
    )


def _stable_regular_identity(metadata: os.stat_result) -> tuple[int, ...]:
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


def _read_pseudofile_same_fd(path: str, label: str, limit: int) -> bytes:
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise AttestorError(f"{label}: cannot open: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise AttestorError(f"{label}: not a regular procfs file")
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, min(65536, limit - total + 1))
            if not block:
                break
            total += len(block)
            if total > limit:
                raise AttestorError(f"{label}: exceeded the fixed read cap")
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if _stable_pseudo_identity(before) != _stable_pseudo_identity(after):
        raise AttestorError(f"{label}: changed during same-FD read")
    return b"".join(chunks)


def _pid_starttime(pid: int) -> int:
    raw = _read_pseudofile_same_fd(
        f"/proc/{pid}/stat",
        f"manager /proc/{pid}/stat",
        MAX_PROC_STAT_BYTES,
    )
    first_space = raw.find(b" ")
    right_parenthesis = raw.rfind(b")")
    if (
        first_space <= 0
        or raw[first_space + 1 : first_space + 2] != b"("
        or right_parenthesis <= first_space + 1
        or raw[right_parenthesis + 1 : right_parenthesis + 2] != b" "
    ):
        raise AttestorError("manager proc stat has invalid framing")
    if raw[:first_space] != str(pid).encode("ascii"):
        raise AttestorError("manager proc stat PID differs from request")
    fields_from_state = raw[right_parenthesis + 2 :].split()
    if len(fields_from_state) < 20:
        raise AttestorError("manager proc stat is missing starttime")
    state = fields_from_state[0]
    if len(state) != 1 or not state.isalpha():
        raise AttestorError("manager proc stat state is invalid")
    try:
        starttime = int(fields_from_state[19], 10)
    except ValueError as exc:
        raise AttestorError("manager proc stat starttime is invalid") from exc
    if starttime <= 0:
        raise AttestorError("manager proc stat starttime is not positive")
    return starttime


def _boot_id() -> str:
    raw = _read_pseudofile_same_fd(
        "/proc/sys/kernel/random/boot_id",
        "kernel boot_id",
        MAX_BOOT_ID_BYTES,
    )
    if _BOOT_ID_RAW_RE.fullmatch(raw) is None:
        raise AttestorError("kernel boot_id byte form is invalid")
    return raw[:-1].decode("ascii")


def _hash_regular_fd(
    descriptor: int,
    label: str,
) -> tuple[str, int, os.stat_result]:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode):
        raise AttestorError(f"{label}: not a regular file")
    if before.st_size <= 0 or before.st_size > MAX_EXECUTABLE_BYTES:
        raise AttestorError(f"{label}: size is outside the fixed bounds")
    try:
        position = os.lseek(descriptor, 0, os.SEEK_SET)
    except OSError as exc:
        raise AttestorError(f"{label}: cannot seek: {exc}") from exc
    if position != 0:
        raise AttestorError(f"{label}: did not seek to byte zero")
    digest = hashlib.sha256()
    total = 0
    while True:
        block = os.read(descriptor, 1 << 20)
        if not block:
            break
        total += len(block)
        if total > MAX_EXECUTABLE_BYTES:
            raise AttestorError(f"{label}: exceeded the fixed read cap")
        digest.update(block)
    after = os.fstat(descriptor)
    if _stable_regular_identity(before) != _stable_regular_identity(after):
        raise AttestorError(f"{label}: changed during same-FD hash")
    if total != before.st_size:
        raise AttestorError(f"{label}: short or extended read")
    return digest.hexdigest(), total, after


def _manager_executable(pid: int) -> dict[str, object]:
    proc_exe = f"/proc/{pid}/exe"
    try:
        actual_fd = os.open(proc_exe, os.O_RDONLY | os.O_CLOEXEC)
    except OSError as exc:
        raise AttestorError(f"manager executable: cannot open {proc_exe}: {exc}") from exc
    try:
        try:
            target_raw = os.readlink(os.fsencode(proc_exe))
        except OSError as exc:
            raise AttestorError(f"manager executable: cannot readlink {proc_exe}: {exc}") from exc
        if not isinstance(target_raw, bytes):
            raise AttestorError("manager executable: readlink did not preserve path bytes")
        if not os.path.isabs(target_raw) or target_raw.endswith(b" (deleted)"):
            raise AttestorError("manager executable: target is not live and absolute")
        try:
            target = target_raw.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise AttestorError("manager executable: target is not strict UTF-8") from exc

        try:
            target_fd = os.open(target_raw, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        except OSError as exc:
            raise AttestorError(f"manager executable: cannot open target {target!r}: {exc}") from exc
        try:
            actual_before = os.fstat(actual_fd)
            target_before = os.fstat(target_fd)
            if not stat.S_ISREG(actual_before.st_mode) or not stat.S_ISREG(target_before.st_mode):
                raise AttestorError("manager executable: executable is not regular")
            if (actual_before.st_dev, actual_before.st_ino) != (
                target_before.st_dev,
                target_before.st_ino,
            ):
                raise AttestorError("manager executable: proc and target dev/inode differ")
            actual_sha, actual_size, actual_after = _hash_regular_fd(
                actual_fd,
                "manager proc executable",
            )
            target_sha, target_size, target_after = _hash_regular_fd(
                target_fd,
                "manager target executable",
            )
        finally:
            os.close(target_fd)

        if _stable_regular_identity(actual_after) != _stable_regular_identity(target_after):
            raise AttestorError("manager executable: proc and target identities differ")
        if actual_sha != target_sha or actual_size != target_size:
            raise AttestorError("manager executable: proc and target bytes differ")
        try:
            final_target_raw = os.readlink(os.fsencode(proc_exe))
            final_proc_stat = os.stat(proc_exe, follow_symlinks=True)
        except OSError as exc:
            raise AttestorError(f"manager executable: final recheck failed: {exc}") from exc
        if final_target_raw != target_raw:
            raise AttestorError("manager executable: target changed during attestation")
        if (final_proc_stat.st_dev, final_proc_stat.st_ino) != (
            actual_after.st_dev,
            actual_after.st_ino,
        ):
            raise AttestorError("manager executable: proc dev/inode changed")
        mode = stat.S_IMODE(target_after.st_mode)
        return {
            "device": target_after.st_dev,
            "inode": target_after.st_ino,
            "mode": mode,
            "mode_octal": f"{mode:04o}",
            "path": target,
            "sha256": target_sha,
            "size_bytes": target_size,
        }
    finally:
        os.close(actual_fd)


def _parse_arguments(argv: Sequence[str]) -> tuple[int, int, str, str]:
    if len(argv) != 8:
        raise AttestorError("expected exactly four named request arguments")
    names = (
        "--pid",
        "--expected-starttime",
        "--expected-boot-id",
        "--dbus-owner",
    )
    if tuple(argv[0::2]) != names:
        raise AttestorError("request argument names or order are invalid")
    try:
        pid = int(argv[1], 10)
        starttime = int(argv[3], 10)
    except ValueError as exc:
        raise AttestorError("PID or starttime is not an integer") from exc
    boot_id = argv[5]
    owner = argv[7]
    if pid <= 0 or starttime <= 0:
        raise AttestorError("PID and starttime must be positive")
    if _BOOT_ID_RE.fullmatch(boot_id) is None:
        raise AttestorError("expected boot_id is invalid")
    if _OWNER_RE.fullmatch(owner) is None:
        raise AttestorError("D-Bus unique owner is invalid")
    return pid, starttime, boot_id, owner


def attest(argv: Sequence[str]) -> dict[str, object]:
    """Attest one request and return its strict, side-effect-free payload."""

    pid, expected_starttime, expected_boot_id, owner = _parse_arguments(argv)
    starttime_before = _pid_starttime(pid)
    boot_id_before = _boot_id()
    if starttime_before != expected_starttime:
        raise AttestorError("manager starttime differs from request")
    if boot_id_before != expected_boot_id:
        raise AttestorError("boot_id differs from request")
    executable = _manager_executable(pid)
    starttime_after = _pid_starttime(pid)
    boot_id_after = _boot_id()
    if starttime_after != starttime_before:
        raise AttestorError("manager starttime changed during attestation")
    if boot_id_after != boot_id_before:
        raise AttestorError("boot_id changed during attestation")
    return {
        "manager_executable": executable,
        "request": {
            "boot_id": expected_boot_id,
            "dbus_unique_owner": owner,
            "manager_pid": pid,
            "manager_pid_starttime": expected_starttime,
        },
        "schema": SCHEMA,
        "status": "PASS",
    }


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def main() -> int:
    try:
        payload = attest(sys.argv[1:])
    except Exception as exc:
        _emit(
            {
                "error": str(exc),
                "schema": SCHEMA,
                "status": "FAIL_CLOSED",
            }
        )
        return 2
    _emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
