#!/usr/bin/env python3
"""Package-pinned, no-authority AB16 resource calibration observer.

The observer is intentionally not a Gate-B owner, bootstrap actor, campaign
publisher, or solver launcher.  A separate stage controller creates one fresh
transient cgroup and starts the declared workload.  This process remains alive,
samples that exact cgroup and filesystem, acknowledges a final pre-cleanup peak
read, then requires the controller to remove the cgroup before it emits its
canonical result.
"""

from __future__ import annotations

import argparse
import hashlib
from importlib.machinery import SourceFileLoader
import importlib.util
import json
import os
from pathlib import Path
import select
import stat
import time
from types import ModuleType
from typing import Final, NoReturn, Sequence


PROTOCOL_SCHEMA: Final = "noncert-cuts-ab16-calibration-observer-protocol-v1"
RESULT_SCHEMA: Final = "noncert-cuts-ab16-calibration-observer-result-v1"
MAX_FRAME_BYTES: Final = 64 * 1024
POLL_SECONDS: Final = 0.025
AUTHORITY_SCOPE: Final = "AB16_RESEARCH_ONLY"


class CalibrationObserverError(RuntimeError):
    """The persistent calibration observer could not prove peak closure."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise CalibrationObserverError(code, detail)


def _load_protocol(descriptor: int, expected_sha256: str) -> ModuleType:
    try:
        metadata = os.fstat(descriptor)
        raw = os.pread(descriptor, metadata.st_size + 1, 0)
    except OSError as exc:
        _fail(
            "CALIBRATION_PROTOCOL_IDENTITY_DRIFT",
            f"retained protocol FD is unavailable: {exc}",
        )
    digest = hashlib.sha256(raw).hexdigest()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or len(raw) != metadata.st_size
        or digest != expected_sha256
    ):
        _fail(
            "CALIBRATION_PROTOCOL_IDENTITY_DRIFT",
            "retained calibration protocol bytes differ from the package pin",
        )
    origin = f"/proc/self/fd/{descriptor}"
    spec = importlib.util.spec_from_file_location(
        f"_ab16_calibration_protocol_{digest[:16]}",
        origin,
        loader=SourceFileLoader(
            f"_ab16_calibration_protocol_{digest[:16]}",
            origin,
        ),
    )
    if spec is None or spec.loader is None:
        _fail(
            "CALIBRATION_PROTOCOL_LOAD_FAILED",
            "cannot create the calibration protocol module",
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _close_unknown_fds(allowed: set[int]) -> None:
    try:
        observed = {
            int(name)
            for name in os.listdir("/proc/self/fd")
            if name.isdigit()
        }
    except OSError as exc:
        _fail(
            "CALIBRATION_OBSERVER_FD_SURFACE_INVALID",
            f"cannot enumerate /proc/self/fd: {exc}",
        )
    for descriptor in sorted(observed - allowed - {0, 1, 2}):
        try:
            os.close(descriptor)
        except OSError:
            pass


def _canonical(value: object) -> bytes:
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


def _write_frame(descriptor: int, value: object) -> None:
    raw = _canonical(value)
    if len(raw) > MAX_FRAME_BYTES:
        _fail("CALIBRATION_OBSERVER_PROTOCOL_ERROR", "outgoing frame is too large")
    header = len(raw).to_bytes(4, "big")
    view = memoryview(header + raw)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            _fail(
                "CALIBRATION_OBSERVER_PROTOCOL_ERROR",
                "short write on observer pipe",
            )
        view = view[written:]


def _read_exact(descriptor: int, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = os.read(descriptor, remaining)
        if not chunk:
            _fail(
                "CALIBRATION_OBSERVER_PROTOCOL_ERROR",
                "observer control pipe closed",
            )
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_frame(descriptor: int) -> dict[str, object]:
    size = int.from_bytes(_read_exact(descriptor, 4), "big")
    if not 0 < size <= MAX_FRAME_BYTES:
        _fail(
            "CALIBRATION_OBSERVER_PROTOCOL_ERROR",
            "incoming frame size is invalid",
        )
    raw = _read_exact(descriptor, size)

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                _fail(
                    "CALIBRATION_OBSERVER_PROTOCOL_ERROR",
                    f"duplicate JSON key {key!r}",
                )
            result[key] = value
        return result

    try:
        value = json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                CalibrationObserverError(
                    "CALIBRATION_OBSERVER_PROTOCOL_ERROR",
                    f"invalid JSON constant {token}",
                )
            ),
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        _fail(
            "CALIBRATION_OBSERVER_PROTOCOL_ERROR",
            f"invalid canonical JSON frame: {exc}",
        )
    if type(value) is not dict or _canonical(value) != raw:
        _fail(
            "CALIBRATION_OBSERVER_PROTOCOL_ERROR",
            "control frame is not one canonical JSON object",
        )
    return value


def _counter(path: Path, label: str) -> int:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        _fail("CALIBRATION_CGROUP_UNAVAILABLE", f"{label}: {exc}")
    if len(raw) > 128 or not raw.endswith(b"\n"):
        _fail("CALIBRATION_CGROUP_UNTRUSTED", f"{label} counter shape drifted")
    text = raw[:-1]
    if not text or not text.isdigit():
        _fail("CALIBRATION_CGROUP_UNTRUSTED", f"{label} is not an integer")
    return int(text)


def _directory_identity(path: Path, label: str) -> tuple[int, int, int, int]:
    try:
        value = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        _fail("CALIBRATION_PATH_UNAVAILABLE", f"{label}: {exc}")
    if not stat.S_ISDIR(value.st_mode) or stat.S_ISLNK(value.st_mode):
        _fail("CALIBRATION_PATH_UNTRUSTED", f"{label} is not one real directory")
    return value.st_dev, value.st_ino, value.st_mode, value.st_uid


def _node_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_gid,
        value.st_size,
        value.st_blocks,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _regular_file_allocation(
    value: os.stat_result,
    *,
    relative: str,
    observed_inodes: set[tuple[int, int]],
) -> int:
    """Return one unambiguous regular-file allocation.

    The measured tree is a byte-budget surface, not a pathname alias graph.
    An inode with another hard link can name storage outside this tree, and
    two in-tree names for one inode would make a pathname sum double-count it.
    """

    if value.st_nlink != 1:
        _fail(
            "CALIBRATION_DISK_HARDLINK_REJECTED",
            f"{relative}: regular-file link count is {value.st_nlink}",
        )
    identity = (value.st_dev, value.st_ino)
    if identity in observed_inodes:
        _fail(
            "CALIBRATION_DISK_HARDLINK_REJECTED",
            f"{relative}: regular-file inode was already enumerated",
        )
    observed_inodes.add(identity)
    return value.st_blocks * 512


def _open_absolute_directory_no_symlinks(path: Path, label: str) -> int:
    absolute = path.absolute()
    if path != absolute or not absolute.is_absolute():
        _fail("CALIBRATION_PATH_UNTRUSTED", f"{label} is not absolute")
    current = os.open(
        "/",
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        for component in absolute.parts[1:]:
            if component in {"", ".", ".."}:
                _fail(
                    "CALIBRATION_PATH_UNTRUSTED",
                    f"{label} contains an unsafe component",
                )
            successor = os.open(
                component,
                os.O_RDONLY
                | os.O_CLOEXEC
                | os.O_DIRECTORY
                | os.O_NOFOLLOW,
                dir_fd=current,
            )
            try:
                os.close(current)
            except BaseException as exc:
                try:
                    os.close(successor)
                except BaseException as close_error:
                    exc.add_note(
                        "calibration successor close also failed: "
                        f"{type(close_error).__name__}: {close_error}"
                    )
                raise
            current = successor
        metadata = os.fstat(current)
        if not stat.S_ISDIR(metadata.st_mode):
            _fail(
                "CALIBRATION_PATH_UNTRUSTED",
                f"{label} is not one retained directory",
            )
        return current
    except BaseException:
        os.close(current)
        raise


def _disk_used(path: Path) -> int:
    """Return allocated bytes in one exact stage-owned tree.

    This deliberately does not use filesystem-wide ``statvfs`` counters:
    unrelated host I/O is neither part of the stage workload nor trustworthy
    evidence for its retained/scratch requirement.  Every directory FD remains
    retained until the complete enumeration and final member/signature replay.
    """

    root = _open_absolute_directory_no_symlinks(
        path,
        "calibration disk target",
    )
    root_metadata = os.fstat(root)
    root_identity = (
        root_metadata.st_dev,
        root_metadata.st_ino,
        root_metadata.st_mode,
        root_metadata.st_uid,
    )
    directories: list[
        tuple[int, tuple[int, ...], tuple[str, ...], str]
    ] = []
    regular_nodes: list[
        tuple[int, str, tuple[int, ...], str]
    ] = []
    observed_regular_inodes: set[tuple[int, int]] = set()
    total = 0
    primary: BaseException | None = None
    try:
        pending: list[tuple[int, str]] = [(root, ".")]
        root = -1
        while pending:
            directory_fd, relative = pending.pop()
            metadata = os.fstat(directory_fd)
            if not stat.S_ISDIR(metadata.st_mode):
                _fail(
                    "CALIBRATION_PATH_UNTRUSTED",
                    f"calibration tree directory drifted: {relative}",
                )
            names = tuple(
                sorted(
                    os.listdir(directory_fd),
                    key=lambda value: os.fsencode(value),
                )
            )
            if any(
                not isinstance(name, str)
                or name in {"", ".", ".."}
                or "/" in name
                for name in names
            ):
                _fail(
                    "CALIBRATION_PATH_UNTRUSTED",
                    f"calibration tree member name is unsafe: {relative}",
                )
            directories.append(
                (
                    directory_fd,
                    _node_signature(metadata),
                    names,
                    relative,
                )
            )
            total += metadata.st_blocks * 512
            for name in names:
                child_relative = (
                    name if relative == "." else f"{relative}/{name}"
                )
                child = os.stat(
                    name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
                if stat.S_ISDIR(child.st_mode):
                    child_fd = os.open(
                        name,
                        os.O_RDONLY
                        | os.O_CLOEXEC
                        | os.O_DIRECTORY
                        | os.O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                    if _node_signature(os.fstat(child_fd)) != _node_signature(
                        child
                    ):
                        os.close(child_fd)
                        _fail(
                            "CALIBRATION_PATH_UNTRUSTED",
                            "calibration tree directory changed while opening: "
                            f"{child_relative}",
                        )
                    pending.append((child_fd, child_relative))
                    continue
                if not stat.S_ISREG(child.st_mode):
                    _fail(
                        "CALIBRATION_PATH_UNTRUSTED",
                        "calibration tree contains a symlink or special node: "
                        f"{child_relative}",
                    )
                child_fd = os.open(
                    name,
                    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=directory_fd,
                )
                opened = os.fstat(child_fd)
                if _node_signature(opened) != _node_signature(child):
                    os.close(child_fd)
                    _fail(
                        "CALIBRATION_PATH_UNTRUSTED",
                        "calibration tree file changed while opening: "
                        f"{child_relative}",
                    )
                regular_nodes.append(
                    (
                        directory_fd,
                        name,
                        _node_signature(opened),
                        child_relative,
                    )
                )
                total += _regular_file_allocation(
                    opened,
                    relative=child_relative,
                    observed_inodes=observed_regular_inodes,
                )
                os.close(child_fd)

        for directory_fd, signature, names, relative in directories:
            if (
                _node_signature(os.fstat(directory_fd)) != signature
                or tuple(
                    sorted(
                        os.listdir(directory_fd),
                        key=lambda value: os.fsencode(value),
                    )
                )
                != names
            ):
                _fail(
                    "CALIBRATION_PATH_UNTRUSTED",
                    "calibration tree directory/member set drifted: "
                    f"{relative}",
                )
        for directory_fd, name, signature, relative in regular_nodes:
            observed = os.stat(
                name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
            if _node_signature(observed) != signature:
                _fail(
                    "CALIBRATION_PATH_UNTRUSTED",
                    f"calibration tree file drifted: {relative}",
                )
        rejoined = _open_absolute_directory_no_symlinks(
            path,
            "calibration disk target final join",
        )
        try:
            rejoined_metadata = os.fstat(rejoined)
            if (
                _node_signature(rejoined_metadata) != directories[0][1]
                or (
                    rejoined_metadata.st_dev,
                    rejoined_metadata.st_ino,
                    rejoined_metadata.st_mode,
                    rejoined_metadata.st_uid,
                )
                != root_identity
            ):
                _fail(
                    "CALIBRATION_PATH_UNTRUSTED",
                    "calibration disk target identity drifted",
                )
        finally:
            os.close(rejoined)
        return total
    except BaseException as exc:
        primary = exc
        raise
    finally:
        if root >= 0:
            try:
                os.close(root)
            except BaseException as close_error:
                if primary is None:
                    raise
                primary.add_note(
                    "calibration root close failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        for directory_fd, _signature, _names, relative in reversed(
            directories
        ):
            try:
                os.close(directory_fd)
            except BaseException as close_error:
                if primary is None:
                    primary = close_error
                else:
                    primary.add_note(
                        "calibration directory close failed for "
                        f"{relative}: {type(close_error).__name__}: "
                        f"{close_error}"
                    )
        if primary is not None and not isinstance(
            primary,
            CalibrationObserverError,
        ):
            raise primary


def _process_identity() -> dict[str, int]:
    pid = os.getpid()
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        closing = raw.rfind(")")
        starttime = int(raw[closing + 2 :].split()[19])
    except (OSError, UnicodeError, IndexError, ValueError) as exc:
        _fail(
            "CALIBRATION_OBSERVER_IDENTITY_FAILED",
            f"cannot capture observer PID/starttime: {exc}",
        )
    if starttime <= 0:
        _fail(
            "CALIBRATION_OBSERVER_IDENTITY_FAILED",
            "observer starttime is not positive",
        )
    return {"pid": pid, "starttime": starttime}


def _sample(cgroup: Path, disk: Path) -> tuple[int, int, int]:
    return (
        _counter(cgroup / "memory.peak", "memory.peak"),
        _counter(cgroup / "memory.swap.peak", "memory.swap.peak"),
        _disk_used(disk),
    )


def observe(
    *,
    cgroup: Path,
    disk: Path,
    control_fd: int,
    result_fd: int,
    timeout_seconds: float,
    poll_seconds: float = POLL_SECONDS,
) -> dict[str, object]:
    """Run the persistent half of one fresh transient-cgroup measurement."""

    if (
        type(control_fd) is not int
        or control_fd < 0
        or type(result_fd) is not int
        or result_fd < 0
        or control_fd == result_fd
    ):
        _fail(
            "CALIBRATION_OBSERVER_PROTOCOL_ERROR",
            "control/result descriptors are invalid",
        )
    if timeout_seconds <= 0 or poll_seconds <= 0:
        _fail(
            "CALIBRATION_OBSERVER_PROTOCOL_ERROR",
            "observer timeout/poll interval is invalid",
        )
    cgroup_identity = _directory_identity(cgroup, "calibration cgroup")
    disk_identity = _directory_identity(disk, "calibration disk target")
    disk_before = _disk_used(disk)
    memory_peak = 0
    swap_peak = 0
    disk_peak = disk_before
    sample_count = 0
    deadline = time.monotonic() + timeout_seconds
    final_capture = False
    while True:
        if time.monotonic() >= deadline:
            _fail(
                "CALIBRATION_OBSERVER_TIMEOUT",
                "workload-exit signal was not received",
            )
        memory, swap, disk_used = _sample(cgroup, disk)
        sample_count += 1
        memory_peak = max(memory_peak, memory)
        swap_peak = max(swap_peak, swap)
        disk_peak = max(disk_peak, disk_used)
        ready, _, _ = select.select([control_fd], [], [], poll_seconds)
        if not ready:
            continue
        request = _read_frame(control_fd)
        if request != {
            "action": "WORKLOAD_EXITED_REQUEST_FINAL_CAPTURE",
            "schema_version": PROTOCOL_SCHEMA,
        }:
            _fail(
                "CALIBRATION_OBSERVER_PROTOCOL_ERROR",
                "observer received an unexpected control action",
            )
        memory, swap, disk_used = _sample(cgroup, disk)
        sample_count += 1
        memory_peak = max(memory_peak, memory)
        swap_peak = max(swap_peak, swap)
        disk_peak = max(disk_peak, disk_used)
        if (
            _directory_identity(cgroup, "calibration cgroup") != cgroup_identity
            or _directory_identity(disk, "calibration disk target") != disk_identity
        ):
            _fail(
                "CALIBRATION_PATH_UNTRUSTED",
                "cgroup or disk identity drifted before final capture",
            )
        final_capture = True
        _write_frame(
            result_fd,
            {
                "action": "FINAL_CAPTURE_COMPLETE",
                "schema_version": PROTOCOL_SCHEMA,
            },
        )
        break

    request = _read_frame(control_fd)
    if request != {
        "action": "CGROUP_REMOVAL_COMPLETE",
        "schema_version": PROTOCOL_SCHEMA,
    }:
        _fail(
            "CALIBRATION_OBSERVER_PROTOCOL_ERROR",
            "observer received an unexpected removal action",
        )
    if os.path.lexists(cgroup):
        _fail(
            "CALIBRATION_CGROUP_NOT_CLOSED",
            "transient cgroup still exists after removal acknowledgement",
        )
    disk_after = _disk_used(disk)
    result = {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": {
            "formal_campaign_creation_authorized": False,
            "gate_b_approval_authorized": False,
            "organic_arm_launch_authorized": False,
            "profile_installation_authorized": False,
            "solver_run_authorized": False,
        },
        "cgroup": {
            "disappeared_after_peak_read": True,
            "identity": {
                "device": cgroup_identity[0],
                "inode": cgroup_identity[1],
                "mode": stat.S_IMODE(cgroup_identity[2]),
                "path": str(cgroup.absolute()),
                "uid": cgroup_identity[3],
            },
            "peak_read_before_disappearance": final_capture,
        },
        "disk": {
            "after_bytes": disk_after,
            "before_bytes": disk_before,
            "growth_peak_bytes": disk_peak - disk_before,
            "peak_bytes": disk_peak,
            "target_identity": {
                "device": disk_identity[0],
                "inode": disk_identity[1],
                "mode": stat.S_IMODE(disk_identity[2]),
                "path": str(disk.absolute()),
                "uid": disk_identity[3],
            },
        },
        "memory_peak_bytes": memory_peak,
        "observer_process_identity": _process_identity(),
        "sample_count": sample_count,
        "schema_version": RESULT_SCHEMA,
        "status": "PEAKS_CAPTURED_BEFORE_CGROUP_DISAPPEARANCE",
        "swap_peak_bytes": swap_peak,
    }
    _write_frame(result_fd, result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cgroup", required=True, type=Path)
    parser.add_argument("--disk", required=True, type=Path)
    parser.add_argument("--observer-fd", required=True, type=int)
    parser.add_argument("--control-fd", required=True, type=int)
    parser.add_argument("--protocol-fd", required=True, type=int)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--result-fd", required=True, type=int)
    parser.add_argument("--timeout-seconds", required=True, type=float)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    _load_protocol(arguments.protocol_fd, arguments.protocol_sha256)
    _close_unknown_fds({arguments.control_fd, arguments.result_fd})
    try:
        observe(
            cgroup=arguments.cgroup,
            disk=arguments.disk,
            control_fd=arguments.control_fd,
            result_fd=arguments.result_fd,
            timeout_seconds=arguments.timeout_seconds,
        )
    except BaseException as exc:
        failure = {
            "authority_scope": AUTHORITY_SCOPE,
            "code": getattr(exc, "code", type(exc).__name__),
            "conclusion": None,
            "schema_version": RESULT_SCHEMA,
            "status": "FAIL_CLOSED",
        }
        try:
            _write_frame(arguments.result_fd, failure)
        except BaseException:
            pass
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
