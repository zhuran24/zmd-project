#!/usr/bin/env python3
"""Pinned native capability wrapper for the prospective AB16 budget cohort.

The shared object is built before package sealing and is executable only after
the package-internal independent verifier accepts its exact bytes.  This module
contains no campaign authority and never chooses a run root.
"""

from __future__ import annotations

from collections.abc import Sequence
import ctypes
import errno
import hashlib
import os
from pathlib import Path
import stat
import subprocess
from typing import NoReturn


NATIVE_HELPER_SCHEMA = "noncert-cuts-ab16-native-budget-helper-v1"
MAX_HELPER_BYTES = 4 * 1024 * 1024


class NativeBudgetHelperError(RuntimeError):
    """The pinned native helper could not satisfy one exact capability."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise NativeBudgetHelperError(code, detail)


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def snapshot_regular(
    path: Path | str,
    *,
    executable: bool = False,
    require_single_link: bool = True,
) -> dict[str, object]:
    absolute = _absolute(path)
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        _fail("NATIVE_HELPER_OPEN_FAILED", f"{absolute}: {exc}")
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink < 1
            or (require_single_link and before.st_nlink != 1)
            or before.st_size < 1
            or before.st_size > MAX_HELPER_BYTES
            or (executable and stat.S_IMODE(before.st_mode) != 0o555)
        ):
            _fail("NATIVE_HELPER_IDENTITY_INVALID", str(absolute))
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                _fail("NATIVE_HELPER_IDENTITY_DRIFT", str(absolute))
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            _fail("NATIVE_HELPER_IDENTITY_DRIFT", str(absolute))
        after = os.fstat(descriptor)
        named = os.stat(absolute, follow_symlinks=False)
        stable = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, field) != getattr(after, field) for field in stable):
            _fail("NATIVE_HELPER_IDENTITY_DRIFT", str(absolute))
        if (
            stat.S_ISLNK(named.st_mode)
            or named.st_dev != after.st_dev
            or named.st_ino != after.st_ino
        ):
            _fail("NATIVE_HELPER_IDENTITY_DRIFT", str(absolute))
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    return {
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def build_shared_object(
    *,
    source: Path | str,
    output: Path | str,
    compiler: Path | str,
) -> dict[str, object]:
    """Build one no-overwrite helper for later package sealing."""

    source_path = _absolute(source)
    output_path = _absolute(output)
    compiler_path = _absolute(compiler)
    snapshot_regular(source_path)
    snapshot_regular(compiler_path, require_single_link=False)
    parent = output_path.parent
    parent_stat = os.stat(parent, follow_symlinks=False)
    if not stat.S_ISDIR(parent_stat.st_mode) or stat.S_ISLNK(parent_stat.st_mode):
        _fail("NATIVE_HELPER_OUTPUT_INVALID", str(parent))
    if output_path.exists() or output_path.is_symlink():
        _fail("NATIVE_HELPER_NO_OVERWRITE", str(output_path))
    staging = parent / f".{output_path.name}.build-staging"
    if staging.exists() or staging.is_symlink():
        _fail("NATIVE_HELPER_NO_OVERWRITE", str(staging))
    command = [
        str(compiler_path),
        "-shared",
        "-fPIC",
        "-O2",
        "-std=c17",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-Wl,-z,relro,-z,now",
        "-o",
        str(staging),
        str(source_path),
    ]
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        _fail(
            "NATIVE_HELPER_BUILD_FAILED",
            completed.stderr.decode("utf-8", "replace")[:4096],
        )
    staging_fd = -1
    parent_fd = -1
    try:
        staging_fd = os.open(staging, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        staging_stat = os.fstat(staging_fd)
        if not stat.S_ISREG(staging_stat.st_mode) or staging_stat.st_nlink != 1:
            _fail("NATIVE_HELPER_BUILD_INVALID", str(staging))
        os.fchmod(staging_fd, 0o555)
        os.fsync(staging_fd)
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        if renameat2(
            parent_fd,
            os.fsencode(staging.name),
            parent_fd,
            os.fsencode(output_path.name),
            1,  # RENAME_NOREPLACE
        ) != 0:
            error = ctypes.get_errno()
            if error == errno.EEXIST:
                _fail("NATIVE_HELPER_NO_OVERWRITE", str(output_path))
            _fail(
                "NATIVE_HELPER_PUBLISH_FAILED",
                f"errno={error}: {os.strerror(error)}",
            )
        os.fsync(parent_fd)
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)
        if parent_fd >= 0:
            os.close(parent_fd)
    # A failed hidden staging inode is never removed; success atomically moves
    # that same inode to the previously absent public name.
    return snapshot_regular(output_path, executable=True)


class NativeBudgetHelper:
    """Identity-bound access to the native helper's narrow ABI."""

    def __init__(self, path: Path | str, *, expected_identity: dict[str, object]) -> None:
        observed = snapshot_regular(path, executable=True)
        if (
            set(expected_identity) != {"path", "sha256", "size_bytes"}
            or observed != expected_identity
        ):
            _fail("NATIVE_HELPER_PIN_MISMATCH", str(path))
        self.identity = observed
        try:
            library = ctypes.CDLL(str(observed["path"]), use_errno=True)
        except OSError as exc:
            _fail("NATIVE_HELPER_LOAD_FAILED", str(exc))
        self._library = library
        library.ab16_memfd_create.argtypes = [ctypes.c_char_p]
        library.ab16_memfd_create.restype = ctypes.c_int
        library.ab16_expected_final_seals.argtypes = []
        library.ab16_expected_final_seals.restype = ctypes.c_int
        library.ab16_get_seals.argtypes = [ctypes.c_int]
        library.ab16_get_seals.restype = ctypes.c_int
        library.ab16_install_final_seals.argtypes = [ctypes.c_int]
        library.ab16_install_final_seals.restype = ctypes.c_int
        library.ab16_send_fd.argtypes = [ctypes.c_int, ctypes.c_int]
        library.ab16_send_fd.restype = ctypes.c_int
        library.ab16_recv_fd.argtypes = [ctypes.c_int]
        library.ab16_recv_fd.restype = ctypes.c_int
        library.ab16_close_range_allowlist.argtypes = [
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_size_t,
        ]
        library.ab16_close_range_allowlist.restype = ctypes.c_int
        library.ab16_landlock_abi.argtypes = []
        library.ab16_landlock_abi.restype = ctypes.c_int
        library.ab16_install_no_filesystem_writes_landlock.argtypes = []
        library.ab16_install_no_filesystem_writes_landlock.restype = ctypes.c_int
        library.ab16_fd_has_writable_mapping.argtypes = [ctypes.c_int]
        library.ab16_fd_has_writable_mapping.restype = ctypes.c_int
        if snapshot_regular(path, executable=True) != observed:
            _fail("NATIVE_HELPER_PIN_MISMATCH", "helper changed while loading")

    @staticmethod
    def _raise_errno(code: str) -> NoReturn:
        number = ctypes.get_errno()
        detail = os.strerror(number) if number else "native helper returned failure"
        _fail(code, f"errno={number}: {detail}")

    @property
    def final_seal_mask(self) -> int:
        return int(self._library.ab16_expected_final_seals())

    def create_memfd(self, name: str) -> int:
        if not name or "\x00" in name:
            _fail("NATIVE_MEMFD_NAME_INVALID", repr(name))
        descriptor = int(self._library.ab16_memfd_create(name.encode("ascii", "strict")))
        if descriptor < 0:
            self._raise_errno("NATIVE_MEMFD_CREATE_FAILED")
        return descriptor

    def get_seals(self, descriptor: int) -> int:
        result = int(self._library.ab16_get_seals(descriptor))
        if result < 0:
            self._raise_errno("NATIVE_MEMFD_SEAL_QUERY_FAILED")
        return result

    def install_final_seals(self, descriptor: int) -> int:
        result = int(self._library.ab16_install_final_seals(descriptor))
        if result < 0:
            self._raise_errno("NATIVE_MEMFD_SEAL_FAILED")
        if result & self.final_seal_mask != self.final_seal_mask:
            _fail("NATIVE_MEMFD_SEAL_FAILED", "final seal mask is incomplete")
        return result

    def send_fd(self, socket_fd: int, descriptor: int) -> None:
        if self._library.ab16_send_fd(socket_fd, descriptor) != 0:
            self._raise_errno("NATIVE_SCM_RIGHTS_SEND_FAILED")

    def recv_fd(self, socket_fd: int) -> int:
        descriptor = int(self._library.ab16_recv_fd(socket_fd))
        if descriptor < 0:
            self._raise_errno("NATIVE_SCM_RIGHTS_RECV_FAILED")
        return descriptor

    def close_range_allowlist(self, descriptors: Sequence[int]) -> None:
        keep = list(descriptors)
        if (
            any(type(descriptor) is not int or descriptor < 0 for descriptor in keep)
            or len(set(keep)) != len(keep)
        ):
            _fail("NATIVE_FD_ALLOWLIST_INVALID", repr(keep))
        values = (ctypes.c_int * len(keep))(*keep)
        if self._library.ab16_close_range_allowlist(values, len(keep)) != 0:
            self._raise_errno("NATIVE_CLOSE_RANGE_FAILED")

    def landlock_abi(self) -> int:
        result = int(self._library.ab16_landlock_abi())
        if result < 0:
            self._raise_errno("NATIVE_LANDLOCK_UNAVAILABLE")
        return result

    def install_no_filesystem_writes_landlock(self) -> None:
        if self._library.ab16_install_no_filesystem_writes_landlock() != 0:
            self._raise_errno("NATIVE_LANDLOCK_INSTALL_FAILED")

    def has_writable_mapping(self, descriptor: int) -> bool:
        result = int(self._library.ab16_fd_has_writable_mapping(descriptor))
        if result < 0:
            self._raise_errno("NATIVE_MEMFD_MAPPING_CHECK_FAILED")
        if result not in {0, 1}:
            _fail("NATIVE_MEMFD_MAPPING_CHECK_FAILED", f"unexpected result {result}")
        return bool(result)
