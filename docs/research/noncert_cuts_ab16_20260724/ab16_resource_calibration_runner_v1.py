#!/usr/bin/env python3
"""Publish one closed, no-authority AB16 calibration cohort.

This module is an artifact publisher, not a workload simulator.  Formal
samples must already carry the canonical result emitted by the persistent
cgroup observer while the declaration's exact command ran.  The publisher
cannot create Gate-B approval, bootstrap a campaign, consume an attempt, run a
solver, or install/lower a resource profile.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import fcntl
import hashlib
from importlib.machinery import SourceFileLoader
import importlib.util
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
import time
from types import ModuleType
from typing import Any, Final, NoReturn, cast

from devtools.research_run_contract import (
    ExclusiveRunRoot,
    build_artifact_root_manifest,
    canonical_json_bytes,
    read_stable_snapshot,
    verify_artifact_root_closure,
)


RECEIPT_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-root-receipt-v1"
)
AUTHORITY_SCOPE: Final = "AB16_RESEARCH_ONLY"
TERMINAL_RECEIPT_PATH: Final = "receipt.json"
SAMPLE_COUNT: Final = 3
FALSE_AUTHORIZATIONS: Final = {
    "formal_campaign_creation_authorized": False,
    "gate_b_approval_authorized": False,
    "organic_arm_launch_authorized": False,
    "profile_installation_authorized": False,
    "solver_run_authorized": False,
}
FIXED_PATHS: Final = {
    "aggregate": "aggregate.json",
    "declaration": "declaration.json",
    "installed_profile": "installed-profile.json",
    "profile_candidate": "profile-candidate.json",
    "observer_result_1": "observer-results/01.json",
    "observer_result_2": "observer-results/02.json",
    "observer_result_3": "observer-results/03.json",
    "sample_1": "samples/01.json",
    "sample_2": "samples/02.json",
    "sample_3": "samples/03.json",
    "validation_1": "validations/01.json",
    "validation_2": "validations/02.json",
    "validation_3": "validations/03.json",
}
OBSERVER_PROTOCOL_SCHEMA: Final = (
    "noncert-cuts-ab16-calibration-observer-protocol-v1"
)
BUNDLE_SET_RECEIPT_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-bundle-set-receipt-v1"
)
STAGE_TERMINAL_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-stage-terminal-v1"
)
BUNDLE_PATHS: Final = {
    "FORMAL_ORGANIC_ARM": "bundles/formal-organic-arm.json",
    "FULL_PREFLIGHT": "bundles/full-preflight.json",
    "GATE_B_QUALIFICATION": "bundles/gate-b-qualification.json",
}
CONTROLLER_PLAN_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-controller-plan-v1"
)
CONTROLLER_TERMINAL_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-controller-terminal-v1"
)
CONTROLLER_INSPECTION_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-controller-inspection-v1"
)
ACCEPTANCE_TERMINAL_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-acceptance-terminal-v1"
)
CONTROLLER_PLAN_MAX_BYTES: Final = 4 * 1024 * 1024
PACKAGE_WORKLOAD_FDS: Final = {
    "loader": 4,
    "package_root": 5,
    "verifier": 6,
    "workload": 7,
    "fixture": 8,
    "stage_root": 9,
    "result": 10,
    "observer": 11,
    "protocol": 12,
}
CALIBRATION_TOOL_ROLES: Final = frozenset(
    {
        "aggregator",
        "alternate_replayer",
        "fd_loader",
        "observer_harness",
        "package_verifier",
        "primary_replayer",
        "protocol",
        "runner",
        "workload",
    }
)
CALIBRATION_CGROUP_LIMITS: Final = {
    "FORMAL_ORGANIC_ARM": {
        "memory.high": 35 * 1024**3,
        "memory.max": 39 * 1024**3,
        "memory.swap.max": 16 * 1024**3,
    },
    "FULL_PREFLIGHT": {
        "memory.high": 28 * 1024**3,
        "memory.max": 35 * 1024**3,
        "memory.swap.max": 8 * 1024**3,
    },
    "GATE_B_QUALIFICATION": {
        "memory.high": 4 * 1024**3,
        "memory.max": 6 * 1024**3,
        "memory.swap.max": 2 * 1024**3,
    },
}


class CalibrationPublicationError(RuntimeError):
    """One no-overwrite, identity, or closure invariant failed."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise CalibrationPublicationError(code, detail)


_DIRECTORY_FLAGS: Final = (
    os.O_RDONLY
    | os.O_DIRECTORY
    | os.O_CLOEXEC
    | getattr(os, "O_NOFOLLOW", 0)
)
_REGULAR_FLAGS: Final = (
    os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
)


def _open_absolute_directory(path: Path, *, label: str) -> int:
    if path != path.absolute() or not path.is_absolute():
        _fail("CALIBRATION_PATH_UNTRUSTED", f"{label} is not absolute")
    opened = [os.open("/", _DIRECTORY_FLAGS)]
    primary: BaseException | None = None
    try:
        for component in path.parts[1:]:
            if component in {"", ".", ".."}:
                _fail("CALIBRATION_PATH_UNTRUSTED", f"{label} has an unsafe component")
            opened.append(
                os.open(component, _DIRECTORY_FLAGS, dir_fd=opened[-1])
            )
    except BaseException as exc:
        primary = exc
    result = opened[-1] if primary is None else -1
    to_close = opened[:-1] if primary is None else opened
    for descriptor in reversed(to_close):
        try:
            os.close(descriptor)
        except BaseException as close_error:
            if primary is None:
                primary = close_error
            else:
                primary.add_note(
                    f"{label} directory cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
    if primary is not None:
        if result >= 0:
            try:
                os.close(result)
            except BaseException as close_error:
                primary.add_note(
                    f"{label} retained directory cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise primary
    return result


def _read_fd_bytes(descriptor: int, *, label: str) -> tuple[bytes, os.stat_result]:
    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        _fail(
            "CALIBRATION_TOOL_IDENTITY_DRIFT",
            f"{label} is not a single-linked regular file",
        )
    raw = bytearray()
    offset = 0
    while offset < before.st_size:
        block = os.pread(
            descriptor,
            min(1024 * 1024, before.st_size - offset),
            offset,
        )
        if not block:
            _fail("CALIBRATION_TOOL_IDENTITY_DRIFT", f"{label} short read")
        raw.extend(block)
        offset += len(block)
    if os.pread(descriptor, 1, before.st_size):
        _fail("CALIBRATION_TOOL_IDENTITY_DRIFT", f"{label} grew while reading")
    after = os.fstat(descriptor)
    def signature(value: os.stat_result) -> tuple[int, int, int, int, int, int, int]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_nlink,
            value.st_size,
            value.st_mtime_ns,
            value.st_ctime_ns,
        )
    if signature(before) != signature(after):
        _fail("CALIBRATION_TOOL_IDENTITY_DRIFT", f"{label} changed while reading")
    return bytes(raw), after


def _validated_tool_content_identity(
    value: object,
    *,
    label: str,
) -> dict[str, object]:
    if type(value) is not dict or set(value) not in (
        {"sha256", "size_bytes"},
        {"mode", "sha256", "size_bytes"},
    ):
        _fail(
            "CALIBRATION_TOOL_IDENTITY_INVALID",
            f"{label} content identity field set drifted",
        )
    record = cast(dict[str, object], value)
    if (
        ("mode" in record and (
            type(record["mode"]) is not int
            or cast(int, record["mode"]) < 0
            or cast(int, record["mode"]) > 0o7777
        ))
        or type(record["sha256"]) is not str
        or len(record["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in record["sha256"])
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] <= 0
    ):
        _fail("CALIBRATION_TOOL_IDENTITY_INVALID", label)
    return dict(record)


def _open_pinned_tool(
    site_identity: Mapping[str, object],
    expected_content_identity: Mapping[str, object],
    *,
    label: str,
) -> int:
    _verify_declared_bytes(site_identity, label=label)
    path = Path(cast(str, site_identity["path"]))
    parent = _open_absolute_directory(path.parent, label=f"{label} parent")
    descriptor = -1
    primary: BaseException | None = None
    try:
        descriptor = os.open(path.name, _REGULAR_FLAGS, dir_fd=parent)
        raw, metadata = _read_fd_bytes(descriptor, label=label)
        expected = _validated_tool_content_identity(
            expected_content_identity,
            label=label,
        )
        actual = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
        if "mode" in expected:
            actual["mode"] = stat.S_IMODE(metadata.st_mode)
        if actual != expected:
            _fail(
                "CALIBRATION_TOOL_IDENTITY_DRIFT",
                f"{label} retained bytes/mode differ from the external pin",
            )
        rejoined = _open_absolute_directory(path.parent, label=f"{label} final parent")
        try:
            first = os.fstat(parent)
            final = os.fstat(rejoined)
            if (first.st_dev, first.st_ino) != (final.st_dev, final.st_ino):
                _fail(
                    "CALIBRATION_TOOL_IDENTITY_DRIFT",
                    f"{label} parent identity drifted",
                )
        finally:
            os.close(rejoined)
    except BaseException as exc:
        primary = exc
    try:
        os.close(parent)
    except BaseException as close_error:
        if primary is None:
            primary = close_error
        else:
            primary.add_note(
                f"{label} parent close failed: "
                f"{type(close_error).__name__}: {close_error}"
            )
    if primary is not None:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except BaseException as close_error:
                primary.add_note(
                    f"{label} descriptor cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
        raise primary
    return descriptor


def _load_module_from_fd(descriptor: int, *, module_name: str) -> ModuleType:
    origin = f"/proc/self/fd/{descriptor}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        origin,
        loader=SourceFileLoader(module_name, origin),
    )
    if spec is None or spec.loader is None:
        _fail("CALIBRATION_RETAINED_FD_LOAD_FAILED", module_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _decode_mount_path(value: str) -> str:
    return (
        value.replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\n")
        .replace("\\134", "\\")
    )


def _require_cgroup2_delegated_parent(path: Path) -> None:
    try:
        rows = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        _fail("CALIBRATION_CGROUP_PARENT_UNTRUSTED", f"mountinfo: {exc}")
    candidates: list[Path] = []
    for row in rows:
        left, separator, right = row.partition(" - ")
        if not separator:
            continue
        left_fields = left.split()
        right_fields = right.split()
        if len(left_fields) < 5 or not right_fields or right_fields[0] != "cgroup2":
            continue
        mount = Path(_decode_mount_path(left_fields[4]))
        try:
            path.relative_to(mount)
        except ValueError:
            continue
        candidates.append(mount)
    if not candidates:
        _fail(
            "CALIBRATION_CGROUP_PARENT_UNTRUSTED",
            f"{path} is not below a cgroup-v2 mount",
        )
    metadata = os.stat(path, follow_symlinks=False)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or not os.access(path, os.W_OK | os.X_OK, follow_symlinks=False)
    ):
        _fail(
            "CALIBRATION_CGROUP_PARENT_UNTRUSTED",
            f"{path} is not an owned writable delegated directory",
        )
    try:
        controllers = set(
            (path / "cgroup.controllers").read_text(encoding="ascii").split()
        )
        enabled = {
            item.lstrip("+")
            for item in (path / "cgroup.subtree_control")
            .read_text(encoding="ascii")
            .split()
        }
    except (OSError, UnicodeError) as exc:
        _fail("CALIBRATION_CGROUP_PARENT_UNTRUSTED", f"{path}: {exc}")
    if not {"memory", "io"} <= controllers or not {"memory", "io"} <= enabled:
        _fail(
            "CALIBRATION_CGROUP_PARENT_UNTRUSTED",
            "delegated parent does not expose enabled memory/io controllers",
        )


def _read_at(directory_fd: int, name: str, *, label: str) -> bytes:
    descriptor = os.open(
        name,
        os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_fd,
    )
    primary: BaseException | None = None
    try:
        chunks: list[bytes] = []
        while True:
            block = os.read(descriptor, 64 * 1024)
            if not block:
                break
            chunks.append(block)
        result = b"".join(chunks)
    except BaseException as exc:
        primary = exc
        result = b""
    try:
        os.close(descriptor)
    except BaseException as close_error:
        if primary is None:
            raise
        primary.add_note(f"{label} close failed: {close_error}")
    if primary is not None:
        raise primary
    return result


def _write_at(directory_fd: int, name: str, value: bytes, *, label: str) -> None:
    descriptor = os.open(
        name,
        os.O_WRONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_fd,
    )
    primary: BaseException | None = None
    try:
        offset = 0
        while offset < len(value):
            count = os.write(descriptor, value[offset:])
            if count <= 0:
                _fail("CALIBRATION_CGROUP_WRITE_FAILED", f"{label}: short write")
            offset += count
    except BaseException as exc:
        primary = exc
    try:
        os.close(descriptor)
    except BaseException as close_error:
        if primary is None:
            raise
        primary.add_note(f"{label} close failed: {close_error}")
    if primary is not None:
        raise primary


def _cgroup_populated(directory_fd: int) -> bool:
    raw = _read_at(directory_fd, "cgroup.events", label="cgroup.events")
    rows = dict(
        line.split(maxsplit=1)
        for line in raw.decode("ascii", errors="strict").splitlines()
        if line
    )
    if rows.get("populated") not in {"0", "1"}:
        _fail("CALIBRATION_CGROUP_UNTRUSTED", "cgroup.events lacks populated")
    return rows["populated"] == "1"


def _io_wbytes(directory_fd: int) -> tuple[int, tuple[dict[str, object], ...]]:
    raw = _read_at(directory_fd, "io.stat", label="io.stat")
    total = 0
    rows: list[dict[str, object]] = []
    for line in raw.decode("ascii", errors="strict").splitlines():
        fields = line.split()
        if not fields or ":" not in fields[0]:
            _fail("CALIBRATION_CGROUP_UNTRUSTED", "io.stat row is malformed")
        values: dict[str, int] = {}
        for item in fields[1:]:
            key, separator, raw_value = item.partition("=")
            if not separator or not raw_value.isdigit():
                _fail("CALIBRATION_CGROUP_UNTRUSTED", "io.stat value is malformed")
            values[key] = int(raw_value)
        wbytes = values.get("wbytes")
        if wbytes is None:
            _fail("CALIBRATION_CGROUP_UNTRUSTED", "io.stat row lacks wbytes")
        total += wbytes
        rows.append({"device": fields[0], "wbytes": wbytes})
    return total, tuple(rows)


class TransientCalibrationCgroup:
    def __init__(
        self,
        *,
        parent_path: Path,
        name: str,
        parent_fd: int,
        cgroup_fd: int,
        parent_identity: tuple[int, int, int, int],
        identity: tuple[int, int, int, int],
        stage: str,
        limits: dict[str, int],
        io_wbytes_before: int,
    ) -> None:
        self.parent_path = parent_path
        self.name = name
        self.parent_fd = parent_fd
        self.cgroup_fd = cgroup_fd
        self.parent_identity = parent_identity
        self.identity = identity
        self.stage = stage
        self.limits = limits
        self.io_wbytes_before = io_wbytes_before
        self.closed = False

    @property
    def path(self) -> Path:
        return self.parent_path / self.name

    @classmethod
    def create(
        cls,
        delegated_parent: Path,
        *,
        name: str,
        stage: str,
    ) -> "TransientCalibrationCgroup":
        if (
            stage not in CALIBRATION_CGROUP_LIMITS
            or not name
            or len(name) > 128
            or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in name)
        ):
            _fail("CALIBRATION_CGROUP_ARGUMENT_INVALID", f"{stage}:{name!r}")
        _require_cgroup2_delegated_parent(delegated_parent)
        parent_fd = _open_absolute_directory(
            delegated_parent,
            label="delegated cgroup parent",
        )
        child_fd = -1
        created = False
        try:
            parent_stat = os.fstat(parent_fd)
            try:
                os.mkdir(name, mode=0o700, dir_fd=parent_fd)
            except FileExistsError:
                _fail(
                    "CALIBRATION_CGROUP_NOT_FRESH",
                    f"transient cgroup already exists: {name}",
                )
            created = True
            child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
            child_stat = os.fstat(child_fd)
            limits = dict(CALIBRATION_CGROUP_LIMITS[stage])
            for control, value in sorted(limits.items()):
                _write_at(
                    child_fd,
                    control,
                    f"{value}\n".encode("ascii"),
                    label=control,
                )
                observed = _read_at(child_fd, control, label=control).strip()
                if observed != str(value).encode("ascii"):
                    _fail(
                        "CALIBRATION_CGROUP_LIMIT_DRIFT",
                        f"{control}: {observed!r}",
                    )
            if "memory.oom.group" in os.listdir(child_fd):
                _write_at(
                    child_fd,
                    "memory.oom.group",
                    b"1\n",
                    label="memory.oom.group",
                )
            if _read_at(child_fd, "cgroup.procs", label="cgroup.procs").strip():
                _fail(
                    "CALIBRATION_CGROUP_NOT_FRESH",
                    "fresh cgroup already contains a process",
                )
            before, _rows = _io_wbytes(child_fd)
            return cls(
                parent_path=delegated_parent,
                name=name,
                parent_fd=parent_fd,
                cgroup_fd=child_fd,
                parent_identity=(
                    parent_stat.st_dev,
                    parent_stat.st_ino,
                    parent_stat.st_mode,
                    parent_stat.st_uid,
                ),
                identity=(
                    child_stat.st_dev,
                    child_stat.st_ino,
                    child_stat.st_mode,
                    child_stat.st_uid,
                ),
                stage=stage,
                limits=limits,
                io_wbytes_before=before,
            )
        except BaseException as exc:
            if child_fd >= 0:
                try:
                    os.close(child_fd)
                except BaseException as close_error:
                    exc.add_note(
                        "transient cgroup setup cleanup failed: "
                        f"{type(close_error).__name__}: {close_error}"
                    )
            if created:
                try:
                    os.rmdir(name, dir_fd=parent_fd)
                except BaseException as remove_error:
                    exc.add_note(
                        "transient cgroup setup removal failed: "
                        f"{type(remove_error).__name__}: {remove_error}"
                    )
            try:
                os.close(parent_fd)
            except BaseException as close_error:
                exc.add_note(
                    "transient cgroup parent cleanup failed: "
                    f"{type(close_error).__name__}: {close_error}"
                )
            raise

    def attach_spawned_child(self, pid: int) -> None:
        if type(pid) is not int or pid <= 0:
            _fail("CALIBRATION_CGROUP_ARGUMENT_INVALID", f"PID {pid!r}")
        _write_at(
            self.cgroup_fd,
            "cgroup.procs",
            f"{pid}\n".encode("ascii"),
            label="cgroup.procs",
        )
        observed = {
            int(row)
            for row in _read_at(
                self.cgroup_fd,
                "cgroup.procs",
                label="cgroup.procs",
            )
            .decode("ascii", errors="strict")
            .splitlines()
            if row
        }
        if observed != {pid}:
            _fail(
                "CALIBRATION_CGROUP_MEMBERSHIP_DRIFT",
                f"expected only spawned PID {pid}; observed={sorted(observed)}",
            )

    def terminate_members(self, *, deadline: float) -> None:
        if not _cgroup_populated(self.cgroup_fd):
            return
        if "cgroup.kill" in os.listdir(self.cgroup_fd):
            _write_at(self.cgroup_fd, "cgroup.kill", b"1\n", label="cgroup.kill")
        else:
            for raw_pid in _read_at(
                self.cgroup_fd,
                "cgroup.procs",
                label="cgroup.procs",
            ).splitlines():
                if raw_pid.isdigit():
                    try:
                        os.kill(int(raw_pid), 9)
                    except ProcessLookupError:
                        pass
        while _cgroup_populated(self.cgroup_fd):
            if time.monotonic() >= deadline:
                _fail(
                    "CALIBRATION_CGROUP_NOT_CLOSED",
                    "cgroup remained populated after termination",
                )
            time.sleep(0.01)

    def finalize(self) -> dict[str, object]:
        if self.closed:
            _fail("CALIBRATION_CGROUP_REUSED", str(self.path))
        if _cgroup_populated(self.cgroup_fd):
            _fail("CALIBRATION_CGROUP_NOT_CLOSED", "cgroup is still populated")
        memory_peak_raw = _read_at(
            self.cgroup_fd,
            "memory.peak",
            label="memory.peak",
        ).strip()
        swap_peak_raw = _read_at(
            self.cgroup_fd,
            "memory.swap.peak",
            label="memory.swap.peak",
        ).strip()
        if not memory_peak_raw.isdigit() or not swap_peak_raw.isdigit():
            _fail("CALIBRATION_CGROUP_UNTRUSTED", "peak counter shape drifted")
        io_after, io_rows = _io_wbytes(self.cgroup_fd)
        if io_after < self.io_wbytes_before:
            _fail("CALIBRATION_CGROUP_UNTRUSTED", "io.stat wbytes decreased")
        child_stat = os.fstat(self.cgroup_fd)
        if (
            child_stat.st_dev,
            child_stat.st_ino,
            child_stat.st_mode,
            child_stat.st_uid,
        ) != self.identity:
            _fail("CALIBRATION_CGROUP_IDENTITY_DRIFT", str(self.path))
        os.close(self.cgroup_fd)
        self.cgroup_fd = -1
        os.rmdir(self.name, dir_fd=self.parent_fd)
        rejoined = _open_absolute_directory(
            self.parent_path,
            label="delegated cgroup parent final join",
        )
        try:
            parent_stat = os.fstat(self.parent_fd)
            named_stat = os.fstat(rejoined)
            expected = self.parent_identity
            if (
                parent_stat.st_dev,
                parent_stat.st_ino,
                parent_stat.st_mode,
                parent_stat.st_uid,
            ) != expected or (
                named_stat.st_dev,
                named_stat.st_ino,
                named_stat.st_mode,
                named_stat.st_uid,
            ) != expected:
                _fail("CALIBRATION_CGROUP_PARENT_DRIFT", str(self.parent_path))
        finally:
            os.close(rejoined)
        os.close(self.parent_fd)
        self.parent_fd = -1
        self.closed = True
        return {
            "cgroup_identity": {
                "device": self.identity[0],
                "inode": self.identity[1],
                "mode": stat.S_IMODE(self.identity[2]),
                "path": str(self.path),
                "uid": self.identity[3],
            },
            "io": {
                "wbytes_after": io_after,
                "wbytes_before": self.io_wbytes_before,
                "wbytes_delta": io_after - self.io_wbytes_before,
                "rows_after": list(io_rows),
            },
            "limits": dict(self.limits),
            "memory_peak_bytes": int(memory_peak_raw),
            "swap_peak_bytes": int(swap_peak_raw),
        }

    def close_after_error(self) -> None:
        primary: BaseException | None = None
        removable = False
        if self.cgroup_fd >= 0:
            try:
                self.terminate_members(deadline=time.monotonic() + 5)
                removable = not _cgroup_populated(self.cgroup_fd)
            except BaseException as exc:
                primary = exc
            try:
                os.close(self.cgroup_fd)
            except BaseException as close_error:
                if primary is None:
                    primary = close_error
                else:
                    primary.add_note(f"cgroup FD close failed: {close_error}")
            self.cgroup_fd = -1
        if self.parent_fd >= 0:
            if removable:
                try:
                    os.rmdir(self.name, dir_fd=self.parent_fd)
                except BaseException as remove_error:
                    if primary is None:
                        primary = remove_error
                    else:
                        primary.add_note(
                            f"cgroup removal failed: {remove_error}"
                        )
            try:
                os.close(self.parent_fd)
            except BaseException as close_error:
                if primary is None:
                    primary = close_error
                else:
                    primary.add_note(f"cgroup parent FD close failed: {close_error}")
            self.parent_fd = -1
        self.closed = True
        if primary is not None:
            raise primary


class _PackageWorkload:
    def __init__(
        self,
        *,
        command: list[str],
        working_directory: Path,
        observer_source: Path,
        package: Any,
        package_verifier: ModuleType,
        loader_fd: int,
        observer_fd: int,
        protocol_fd: int,
        runner_fd: int,
        verifier_fd: int,
        workload_fd: int,
        fixture_fd: int,
    ) -> None:
        self.command = command
        self.working_directory = working_directory
        self.observer_source = observer_source
        self.package = package
        self.package_verifier = package_verifier
        self.loader_fd = loader_fd
        self.observer_fd = observer_fd
        self.protocol_fd = protocol_fd
        self.runner_fd = runner_fd
        self.verifier_fd = verifier_fd
        self.workload_fd = workload_fd
        self.fixture_fd = fixture_fd

    def close(self) -> None:
        primary: BaseException | None = None
        for descriptor in (
            self.loader_fd,
            self.observer_fd,
            self.protocol_fd,
            self.runner_fd,
            self.verifier_fd,
            self.workload_fd,
            self.fixture_fd,
        ):
            try:
                os.close(descriptor)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(f"package workload FD close failed: {exc}")
        try:
            self.package.close()
        except BaseException as exc:
            if primary is None:
                primary = exc
            else:
                primary.add_note(f"retained package close failed: {exc}")
        if primary is not None:
            raise primary


class _FullWorkload:
    def __init__(
        self,
        *,
        command: list[str],
        working_directory: Path,
        observer_fd: int,
        protocol_fd: int,
        runner_fd: int,
    ) -> None:
        self.command = command
        self.working_directory = working_directory
        self.observer_fd = observer_fd
        self.protocol_fd = protocol_fd
        self.runner_fd = runner_fd

    def close(self) -> None:
        primary: BaseException | None = None
        for descriptor in (self.observer_fd, self.protocol_fd, self.runner_fd):
            try:
                os.close(descriptor)
            except BaseException as exc:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(f"full workload FD close failed: {exc}")
        if primary is not None:
            raise primary


def _load_protocol() -> ModuleType:
    source = Path(__file__).with_name("ab16_resource_calibration_v1.py")
    raw = source.read_bytes()
    expected = os.environ.get("AB16_CALIBRATION_PROTOCOL_SHA256")
    observed = hashlib.sha256(raw).hexdigest()
    if expected is not None and expected != observed:
        _fail(
            "CALIBRATION_PROTOCOL_IDENTITY_DRIFT",
            f"expected={expected}; observed={observed}",
        )
    spec = importlib.util.spec_from_file_location(
        "_ab16_resource_calibration_protocol_for_publisher",
        source,
    )
    if spec is None or spec.loader is None:
        _fail("CALIBRATION_PROTOCOL_LOAD_FAILED", str(source))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(path: Path, value: object) -> dict[str, object]:
    raw = canonical_json_bytes(value)
    return {
        "path": str(path.absolute()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _root_identity(path: Path) -> dict[str, object]:
    value = os.lstat(path)
    if (
        not stat.S_ISDIR(value.st_mode)
        or stat.S_ISLNK(value.st_mode)
        or value.st_uid != os.getuid()
    ):
        _fail(
            "CALIBRATION_ROOT_IDENTITY_INVALID",
            "run root is not one owned real directory",
        )
    return {
        "device": value.st_dev,
        "inode": value.st_ino,
        "mode": stat.S_IMODE(value.st_mode),
        "path": str(path.absolute()),
        "uid": value.st_uid,
    }


def _artifact_identity(relative: str, value: object) -> dict[str, object]:
    raw = canonical_json_bytes(value)
    return {
        "path": relative,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _read_exact(descriptor: int, count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = count
    while remaining:
        chunk = os.read(descriptor, remaining)
        if not chunk:
            _fail(
                "CALIBRATION_OBSERVER_PROTOCOL_FAILED",
                "observer pipe closed before a complete frame",
            )
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_exact_before(
    descriptor: int,
    count: int,
    *,
    deadline: float,
    label: str,
) -> bytes:
    result = b""
    while len(result) < count:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _fail("CALIBRATION_WORKLOAD_TIMEOUT", label)
        readable, _, _ = select.select([descriptor], [], [], remaining)
        if not readable:
            _fail("CALIBRATION_WORKLOAD_TIMEOUT", label)
        chunk = os.read(descriptor, count - len(result))
        if not chunk:
            _fail("CALIBRATION_WORKLOAD_START_FAILED", label)
        result += chunk
    return result


def _waitpid_before(pid: int, *, deadline: float) -> int:
    while True:
        waited, status = os.waitpid(pid, os.WNOHANG)
        if waited == pid:
            return status
        if time.monotonic() >= deadline:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
            _fail(
                "CALIBRATION_WORKLOAD_TIMEOUT",
                f"declared workload PID {pid} exceeded its timeout",
            )
        time.sleep(0.05)


def _require_waitpid_echild(*, deadline: float) -> None:
    while True:
        try:
            waited, _status = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if waited > 0:
            continue
        if time.monotonic() >= deadline:
            _fail(
                "CALIBRATION_DESCENDANT_CLOSURE_FAILED",
                "waitpid(-1, WNOHANG) did not reach ECHILD",
            )
        time.sleep(0.01)


def _read_frame(descriptor: int) -> dict[str, object]:
    size = int.from_bytes(_read_exact(descriptor, 4), "big")
    if size <= 0 or size > 16 * 1024 * 1024:
        _fail(
            "CALIBRATION_OBSERVER_PROTOCOL_FAILED",
            f"observer frame size is invalid: {size}",
        )
    raw = _read_exact(descriptor, size)
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        _fail("CALIBRATION_OBSERVER_PROTOCOL_FAILED", str(exc))
    if type(value) is not dict or canonical_json_bytes(value) != raw:
        _fail(
            "CALIBRATION_OBSERVER_PROTOCOL_FAILED",
            "observer frame is not canonical JSON",
        )
    return cast(dict[str, object], value)


def _write_frame(descriptor: int, value: object) -> None:
    raw = canonical_json_bytes(value)
    payload = len(raw).to_bytes(4, "big") + raw
    view = memoryview(payload)
    while view:
        count = os.write(descriptor, view)
        if count <= 0:
            _fail(
                "CALIBRATION_OBSERVER_PROTOCOL_FAILED",
                "observer control pipe short write",
            )
        view = view[count:]


def _process_identity(pid: int) -> dict[str, int]:
    deadline = time.monotonic() + 2.0
    while True:
        try:
            raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
            closing = raw.rfind(")")
            starttime = int(raw[closing + 2 :].split()[19])
            if starttime <= 0:
                raise ValueError("nonpositive starttime")
            return {"pid": pid, "starttime": starttime}
        except (OSError, UnicodeError, IndexError, ValueError) as exc:
            if time.monotonic() >= deadline:
                _fail(
                    "CALIBRATION_WORKLOAD_IDENTITY_FAILED",
                    f"PID {pid}: {exc}",
                )
            time.sleep(0.01)


def _install_fd_map(mapping: Mapping[int, int]) -> None:
    """Install a collision-safe fixed FD map in the pre-exec child."""

    duplicated: dict[int, int] = {}
    try:
        for target, source in mapping.items():
            duplicated[target] = os.dup(source)
        for target, source in duplicated.items():
            os.dup2(source, target, inheritable=True)
    finally:
        for descriptor in duplicated.values():
            os.close(descriptor)


def _verify_declared_bytes(identity: object, *, label: str) -> None:
    if type(identity) is not dict or set(identity) != {
        "path",
        "sha256",
        "size_bytes",
    }:
        _fail("CALIBRATION_EXECUTION_SURFACE_INVALID", f"{label} identity")
    record = cast(dict[str, object], identity)
    if (
        type(record["path"]) is not str
        or type(record["sha256"]) is not str
        or type(record["size_bytes"]) is not int
    ):
        _fail("CALIBRATION_EXECUTION_SURFACE_INVALID", f"{label} identity")
    snapshot = read_stable_snapshot(
        record["path"],
        expected_sha256=record["sha256"],
        expected_size_bytes=record["size_bytes"],
    )
    if snapshot.identity.path != str(Path(record["path"]).absolute()):
        _fail(
            "CALIBRATION_EXECUTION_SURFACE_INVALID",
            f"{label} path identity drifted",
        )


_FULL_COLLECTION_PROBE: Final = r"""
import hashlib
import json
import pathlib
import sys

import pytest

rows = []

class Collector:
    @staticmethod
    def pytest_collection_finish(session):
        rows.extend(
            {
                "nodeid": item.nodeid,
                "path": pathlib.PurePosixPath(item.nodeid.partition("::")[0]).as_posix(),
            }
            for item in session.items
        )

status = pytest.main(
    [
        "--collect-only",
        "-q",
        "-m",
        "not slow",
        "--repository-workflow=full",
        "src/tests/",
    ],
    plugins=[Collector()],
)
raw = (
    json.dumps(
        rows,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    + "\n"
).encode("utf-8")
record = {
    "collection_count": len(rows),
    "collection_sha256": hashlib.sha256(raw).hexdigest(),
    "status": int(status),
}
print("AB16_FULL_COLLECTION=" + json.dumps(record, separators=(",", ":"), sort_keys=True))
raise SystemExit(0 if status == 0 and rows else 2)
"""

_FULL_WORKER_PROBE: Final = r"""
import importlib.util
import json
import os

available = importlib.util.find_spec("xdist") is not None
count = 1
mode = "pytest-serial"
if available:
    raw = os.environ.get("PYTEST_XDIST_AUTO_NUM_WORKERS")
    if raw:
        try:
            count = int(raw)
        except ValueError:
            raise SystemExit(2)
    else:
        try:
            import psutil
        except ImportError:
            count = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
        else:
            count = psutil.cpu_count(logical=False) or psutil.cpu_count() or 1
    if count <= 0:
        raise SystemExit(2)
    mode = "pytest-xdist-auto"
print(json.dumps(
    {"count": count, "mode": mode, "xdist_available": available},
    separators=(",", ":"),
    sort_keys=True,
))
"""


def _probe_json_line(
    command: Sequence[str],
    *,
    working_directory: Path,
    timeout_seconds: float,
    prefix: str = "",
) -> dict[str, object]:
    result = subprocess.run(
        list(command),
        cwd=working_directory,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout_seconds,
        env=os.environ.copy(),
    )
    if result.returncode != 0:
        _fail(
            "CALIBRATION_FINGERPRINT_MEASUREMENT_FAILED",
            result.stderr.decode("utf-8", errors="replace")[-4096:],
        )
    lines = result.stdout.decode("utf-8", errors="strict").splitlines()
    matching = [line[len(prefix):] for line in lines if line.startswith(prefix)]
    if len(matching) != 1:
        _fail(
            "CALIBRATION_FINGERPRINT_MEASUREMENT_FAILED",
            f"expected one {prefix!r} record; observed={len(matching)}",
        )
    try:
        value = json.loads(matching[0])
    except json.JSONDecodeError as exc:
        _fail("CALIBRATION_FINGERPRINT_MEASUREMENT_FAILED", str(exc))
    if type(value) is not dict:
        _fail(
            "CALIBRATION_FINGERPRINT_MEASUREMENT_FAILED",
            "probe result is not an object",
        )
    return cast(dict[str, object], value)


def measure_full_execution_fingerprint(
    *,
    interpreter: Path,
    working_directory: Path,
    timeout_seconds: float,
) -> dict[str, object]:
    """Measure the exact full collection and effective xdist execution mode.

    This function is called immediately before the declared full command.  Its
    collection probe uses the same ``not slow`` mark, full repository workflow,
    and ``src/tests/`` target as ``preflight_gate.py --full``.  It therefore
    cannot silently reuse an xdist profile after a serial fallback.
    """

    if (
        timeout_seconds <= 0
        or not interpreter.is_absolute()
        or not working_directory.is_absolute()
    ):
        _fail(
            "CALIBRATION_FINGERPRINT_MEASUREMENT_FAILED",
            "probe arguments are malformed",
        )
    worker = _probe_json_line(
        [str(interpreter), "-I", "-B", "-c", _FULL_WORKER_PROBE],
        working_directory=working_directory,
        timeout_seconds=min(timeout_seconds, 30.0),
    )
    if set(worker) != {"count", "mode", "xdist_available"}:
        _fail(
            "CALIBRATION_FINGERPRINT_MEASUREMENT_FAILED",
            "worker probe shape drifted",
        )
    inventory = _probe_json_line(
        [str(interpreter), "-I", "-B", "-c", _FULL_COLLECTION_PROBE],
        working_directory=working_directory,
        timeout_seconds=timeout_seconds,
        prefix="AB16_FULL_COLLECTION=",
    )
    if (
        set(inventory) != {"collection_count", "collection_sha256", "status"}
        or inventory["status"] != 0
        or type(inventory["collection_count"]) is not int
        or inventory["collection_count"] <= 0
        or type(inventory["collection_sha256"]) is not str
        or len(cast(str, inventory["collection_sha256"])) != 64
        or type(worker["xdist_available"]) is not bool
        or type(worker["count"]) is not int
        or cast(int, worker["count"]) <= 0
        or worker["mode"]
        not in {"pytest-serial", "pytest-xdist-auto"}
        or (
            worker["mode"] == "pytest-xdist-auto"
            and worker["xdist_available"] is not True
        )
        or (
            worker["mode"] == "pytest-serial"
            and (
                worker["xdist_available"] is not False
                or worker["count"] != 1
            )
        )
    ):
        _fail(
            "CALIBRATION_FINGERPRINT_MEASUREMENT_FAILED",
            "measured inventory/worker record is malformed",
        )
    return {
        "test_inventory": {
            "collection_count": inventory["collection_count"],
            "collection_sha256": inventory["collection_sha256"],
        },
        "worker": dict(worker),
    }


def _validated_full_workload(
    declaration: Mapping[str, object],
    *,
    expected_calibration_tool_identities: Mapping[
        str, Mapping[str, object]
    ] | None,
) -> _FullWorkload:
    expected_tools = _validate_expected_calibration_tool_identities(
        expected_calibration_tool_identities
    )
    if type(declaration) is not dict or type(
        declaration.get("execution_surface")
    ) is not dict:
        _fail("CALIBRATION_EXECUTION_SURFACE_INVALID", "declaration is malformed")
    untrusted_surface = cast(
        dict[str, object],
        declaration["execution_surface"],
    )
    untrusted_members = cast(
        dict[str, dict[str, object]],
        untrusted_surface.get("execution_member_identities"),
    )
    if type(untrusted_members) is not dict or not {
        "calibration_observer",
        "calibration_protocol",
        "calibration_runner",
    } <= set(untrusted_members):
        _fail(
            "CALIBRATION_EXECUTION_SURFACE_INVALID",
            "full surface omits retained observer/protocol roles",
        )
    protocol_fd = _open_pinned_tool(
        untrusted_members["calibration_protocol"],
        expected_tools["protocol"],
        label="calibration protocol",
    )
    observer_fd = -1
    runner_fd = -1
    try:
        protocol = _load_module_from_fd(
            protocol_fd,
            module_name="_ab16_calibration_protocol_retained_for_full",
        )
        checked = protocol.validate_declaration(declaration)
        observer_fd = _open_pinned_tool(
            untrusted_members["calibration_observer"],
            expected_tools["observer_harness"],
            label="calibration observer",
        )
        runner_fd = _open_pinned_tool(
            untrusted_members["calibration_runner"],
            expected_tools["runner"],
            label="calibration runner",
        )
        if checked["stage"] != "FULL_PREFLIGHT":
            _fail(
                "CALIBRATION_EXECUTION_SURFACE_STAGE_MISMATCH",
                f"{checked['stage']} is not the full-preflight entrypoint",
            )
        surface = cast(dict[str, object], checked["execution_surface"])
        command = surface["command"]
        if (
            type(command) is not list
            or len(command) != 3
            or type(command[0]) is not str
            or not Path(command[0]).is_absolute()
            or command[1:] != ["scripts/preflight_gate.py", "--full"]
        ):
            _fail(
                "CALIBRATION_EXECUTION_SURFACE_INVALID",
                "full calibration command is not the fixed full-preflight command",
            )
        working_directory = Path(cast(str, surface["working_directory"]))
        if not working_directory.is_absolute():
            _fail(
                "CALIBRATION_EXECUTION_SURFACE_INVALID",
                "full calibration working directory is not absolute",
            )
        members = cast(dict[str, object], surface["execution_member_identities"])
        controls = cast(dict[str, object], surface["control_plane_identities"])
        for label, identity in sorted({**members, **controls}.items()):
            _verify_declared_bytes(identity, label=label)
        declared_paths = {
            cast(str, cast(dict[str, object], identity)["path"])
            for identity in members.values()
        }
        interpreter = str(Path(command[0]).absolute())
        preflight = str((working_directory / command[1]).absolute())
        if interpreter not in declared_paths or preflight not in declared_paths:
            _fail(
                "CALIBRATION_EXECUTION_SURFACE_INVALID",
                "interpreter or preflight source is absent from execution members",
            )
        measured = measure_full_execution_fingerprint(
            interpreter=Path(interpreter),
            working_directory=working_directory,
            timeout_seconds=1200.0,
        )
        if (
            measured["test_inventory"] != surface["test_inventory"]
            or measured["worker"] != surface["worker"]
        ):
            _fail(
                "CALIBRATION_EXECUTION_FINGERPRINT_DRIFT",
                "actual full collection or effective worker mode differs from the declaration",
            )
        observer_identity = cast(dict[str, object], checked["observer_identity"])
        if observer_identity != members["calibration_observer"]:
            _fail(
                "CALIBRATION_EXECUTION_SURFACE_INVALID",
                "full declaration observer is not the retained observer role",
            )
        result = _FullWorkload(
            command=list(command),
            working_directory=working_directory,
            observer_fd=observer_fd,
            protocol_fd=protocol_fd,
            runner_fd=runner_fd,
        )
        observer_fd = -1
        protocol_fd = -1
        runner_fd = -1
        return result
    except BaseException as exc:
        for descriptor in (observer_fd, protocol_fd, runner_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except BaseException as close_error:
                    exc.add_note(f"full role cleanup failed: {close_error}")
        raise


def _load_package_protocol(source: Path, expected: Mapping[str, object]) -> ModuleType:
    del source
    descriptor = _open_pinned_tool(
        expected,
        {
            "sha256": expected["sha256"],
            "size_bytes": expected["size_bytes"],
        },
        label="independent calibration package verifier",
    )
    try:
        return _load_module_from_fd(
            descriptor,
            module_name="_ab16_resource_calibration_package_host_verifier",
        )
    finally:
        os.close(descriptor)


def _validate_expected_calibration_tool_identities(
    value: Mapping[str, Mapping[str, object]] | None,
) -> dict[str, dict[str, object]]:
    if value is None or set(value) != CALIBRATION_TOOL_ROLES:
        _fail(
            "CALIBRATION_TOOL_IDENTITY_INVALID",
            "externally pinned calibration tool role set is not exact",
        )
    return {
        role: _validated_tool_content_identity(identity, label=role)
        for role, identity in sorted(value.items())
    }


def _validated_package_workload(
    declaration: Mapping[str, object],
    *,
    expected_calibration_tool_identities: Mapping[
        str, Mapping[str, object]
    ] | None,
) -> _PackageWorkload:
    expected_tools = _validate_expected_calibration_tool_identities(
        expected_calibration_tool_identities
    )
    if type(declaration) is not dict:
        _fail("CALIBRATION_EXECUTION_SURFACE_INVALID", "declaration is not an object")
    stage = cast(str, declaration.get("stage"))
    if stage not in {"GATE_B_QUALIFICATION", "FORMAL_ORGANIC_ARM"}:
        _fail("CALIBRATION_EXECUTION_SURFACE_INVALID", f"unexpected stage {stage!r}")
    surface_value = declaration.get("execution_surface")
    if type(surface_value) is not dict:
        _fail("CALIBRATION_EXECUTION_SURFACE_INVALID", "execution surface is absent")
    surface = cast(dict[str, object], surface_value)
    members = cast(dict[str, dict[str, object]], surface["execution_member_identities"])
    required = {
        "calibration_fd_loader",
        "calibration_observer",
        "calibration_package_receipt",
        "calibration_package_verifier",
        "calibration_package_verifier_host",
        "calibration_protocol",
        "calibration_stage_fixture",
        "calibration_workload",
        "python_interpreter",
    }
    if not required <= set(members):
        _fail(
            "CALIBRATION_EXECUTION_SURFACE_INVALID",
            f"package workload members omit {sorted(required - set(members))!r}",
        )
    controls = cast(dict[str, dict[str, object]], surface["control_plane_identities"])
    for label, identity in sorted({**members, **controls}.items()):
        _verify_declared_bytes(identity, label=label)
    receipt_identity = members["calibration_package_receipt"]
    receipt_path = Path(cast(str, receipt_identity["path"]))
    package_root = receipt_path.parent
    if receipt_path.name != "receipt.json" or not package_root.is_absolute():
        _fail(
            "CALIBRATION_EXECUTION_SURFACE_INVALID",
            "calibration package receipt path is not fixed",
        )
    host_verifier_identity = members["calibration_package_verifier_host"]
    host_verifier_fd = _open_pinned_tool(
        host_verifier_identity,
        expected_tools["package_verifier"],
        label="independent calibration package verifier",
    )
    package: Any | None = None
    verifier_error: BaseException | None = None
    try:
        package_protocol = _load_module_from_fd(
            host_verifier_fd,
            module_name="_ab16_resource_calibration_package_host_verifier",
        )
        package = package_protocol.RetainedCalibrationPackage.open(
            package_root,
            expected_receipt_identity=receipt_identity,
        )
    except BaseException as exc:
        verifier_error = exc
    try:
        os.close(host_verifier_fd)
    except BaseException as close_error:
        if verifier_error is None:
            raise
        verifier_error.add_note(
            f"independent package verifier close failed: {close_error}"
        )
    if verifier_error is not None:
        raise verifier_error
    assert package is not None
    try:
        loader_fd = package.open_role("calibration-fd-loader")
        observer_fd = package.open_role("calibration-observer")
        protocol_fd = package.open_role("calibration-protocol")
        runner_fd = package.open_role("calibration-runner")
        verifier_fd = package.open_role("calibration-package-verifier")
        workload_fd = package.open_role("calibration-workload")
        fixture_fd = package.open_fixture(stage)
        opened = (
            loader_fd,
            observer_fd,
            protocol_fd,
            runner_fd,
            verifier_fd,
            workload_fd,
            fixture_fd,
        )
        expected_by_fd = (
            members["calibration_fd_loader"],
            members["calibration_observer"],
            members["calibration_protocol"],
            members["calibration_runner"],
            members["calibration_package_verifier"],
            members["calibration_workload"],
            members["calibration_stage_fixture"],
        )
        tool_roles_by_fd = (
            "fd_loader",
            "observer_harness",
            "protocol",
            "runner",
            "package_verifier",
            "workload",
            None,
        )
        for descriptor, expected in zip(opened, expected_by_fd, strict=True):
            metadata = os.fstat(descriptor)
            digest = hashlib.sha256()
            offset = 0
            while offset < metadata.st_size:
                block = os.pread(
                    descriptor,
                    min(1024 * 1024, metadata.st_size - offset),
                    offset,
                )
                if not block:
                    _fail(
                        "CALIBRATION_PACKAGE_MEMBER_DRIFT",
                        cast(str, expected["path"]),
                    )
                digest.update(block)
                offset += len(block)
            if (
                metadata.st_size != expected["size_bytes"]
                or digest.hexdigest() != expected["sha256"]
            ):
                _fail(
                    "CALIBRATION_PACKAGE_MEMBER_DRIFT",
                    cast(str, expected["path"]),
                )
        for descriptor, role in zip(opened, tool_roles_by_fd, strict=True):
            if role is None:
                continue
            raw, metadata = _read_fd_bytes(
                descriptor,
                label=f"package role {role}",
            )
            content = {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
            expected_content = expected_tools[role]
            if "mode" in expected_content:
                content["mode"] = stat.S_IMODE(metadata.st_mode)
            if content != expected_content:
                _fail(
                    "CALIBRATION_TOOL_IDENTITY_DRIFT",
                    f"package role {role} differs from the external pin",
                )
        protocol = _load_module_from_fd(
            protocol_fd,
            module_name="_ab16_calibration_protocol_retained_for_runner",
        )
        checked = protocol.validate_declaration(declaration)
        receipt = package.receipt
        portable = cast(
            dict[str, object],
            cast(dict[str, object], checked["execution_surface"])[
                "portable_package"
            ],
        )
        host_runtime_content = {
            label: {
                "sha256": identity["sha256"],
                "size_bytes": identity["size_bytes"],
            }
            for label, identity in sorted(
                cast(
                    dict[str, dict[str, object]],
                    receipt["host_runtime_identities"],
                ).items()
            )
        }
        if (
            portable["package_receipt_identity"] != receipt_identity
            or portable["package_schema_version"] != receipt["schema_version"]
            or portable["layout"] != receipt["layout"]
            or portable["source_sets_sha256"]
            != hashlib.sha256(
                canonical_json_bytes(receipt["source_sets"])
            ).hexdigest()
            or portable["host_runtime_content_sha256"]
            != hashlib.sha256(
                canonical_json_bytes(host_runtime_content)
            ).hexdigest()
        ):
            _fail(
                "CALIBRATION_EXECUTION_SURFACE_INVALID",
                "portable package closure differs from the retained package",
            )
        roles = cast(dict[str, str], receipt["roles"])
        fixtures = cast(dict[str, str], receipt["stage_fixtures"])
        expected_package_paths = (
            roles["calibration-fd-loader"],
            roles["calibration-observer"],
            roles["calibration-protocol"],
            roles["calibration-runner"],
            roles["calibration-package-verifier"],
            roles["calibration-workload"],
            fixtures[stage],
        )
        for expected, relative in zip(expected_by_fd, expected_package_paths, strict=True):
            if Path(cast(str, expected["path"])) != package_root / relative:
                _fail(
                    "CALIBRATION_EXECUTION_SURFACE_INVALID",
                    f"package member path differs: {relative}",
                )
    except BaseException as exc:
        for descriptor in locals().get("opened", ()):
            try:
                os.close(descriptor)
            except BaseException as close_error:
                exc.add_note(f"package role cleanup failed: {close_error}")
        try:
            package.close()
        except BaseException as close_error:
            exc.add_note(f"retained package cleanup failed: {close_error}")
        raise

    try:
        command = surface["command"]
        expected_command = [
            cast(str, members["python_interpreter"]["path"]),
            "-I",
            "-B",
            f"/proc/self/fd/{PACKAGE_WORKLOAD_FDS['loader']}",
            "--stage",
            stage,
            "--package-root-fd",
            str(PACKAGE_WORKLOAD_FDS["package_root"]),
            "--package-root-path",
            str(package_root),
            "--package-receipt-sha256",
            cast(str, receipt_identity["sha256"]),
            "--package-receipt-size",
            str(receipt_identity["size_bytes"]),
            "--verifier-fd",
            str(PACKAGE_WORKLOAD_FDS["verifier"]),
            "--verifier-sha256",
            cast(str, members["calibration_package_verifier"]["sha256"]),
            "--workload-fd",
            str(PACKAGE_WORKLOAD_FDS["workload"]),
            "--fixture-fd",
            str(PACKAGE_WORKLOAD_FDS["fixture"]),
            "--stage-root-fd",
            str(PACKAGE_WORKLOAD_FDS["stage_root"]),
            "--result-fd",
            str(PACKAGE_WORKLOAD_FDS["result"]),
        ]
        if command != expected_command:
            _fail(
                "CALIBRATION_EXECUTION_SURFACE_INVALID",
                "package workload command differs from the fixed retained-FD command",
            )
        working_directory = Path(cast(str, surface["working_directory"]))
        observer_identity = cast(dict[str, object], checked["observer_identity"])
        if observer_identity != members["calibration_observer"]:
            _fail(
                "CALIBRATION_EXECUTION_SURFACE_INVALID",
                "declaration observer identity is not the package-retained observer",
            )
        return _PackageWorkload(
            command=list(expected_command),
            working_directory=working_directory,
            observer_source=Path(cast(str, observer_identity["path"])),
            package=package,
            package_verifier=package_protocol,
            loader_fd=loader_fd,
            observer_fd=observer_fd,
            protocol_fd=protocol_fd,
            runner_fd=runner_fd,
            verifier_fd=verifier_fd,
            workload_fd=workload_fd,
            fixture_fd=fixture_fd,
        )
    except BaseException as exc:
        for descriptor in opened:
            try:
                os.close(descriptor)
            except BaseException as close_error:
                exc.add_note(f"package role cleanup failed: {close_error}")
        try:
            package.close()
        except BaseException as close_error:
            exc.add_note(f"retained package cleanup failed: {close_error}")
        raise


def _publish_stage_terminal(
    root: ExclusiveRunRoot,
    *,
    stage: str,
    status: str,
    workload_result: Mapping[str, object] | None,
    cgroup_result: Mapping[str, object] | None,
) -> dict[str, object]:
    if status not in {"CLOSED_NO_AUTHORITY", "INCOMPLETE_NO_AUTHORITY"}:
        _fail("CALIBRATION_STAGE_TERMINAL_INVALID", status)
    terminal_path = (
        "receipt.json"
        if status == "CLOSED_NO_AUTHORITY"
        else "terminal-incomplete.json"
    )
    manifest = build_artifact_root_manifest(root)
    receipt = {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "cgroup_result": (
            None if cgroup_result is None else dict(cgroup_result)
        ),
        "manifest": manifest,
        "schema_version": STAGE_TERMINAL_SCHEMA,
        "stage": stage,
        "status": status,
        "terminal_self_exclusion": {
            "excluded_from_manifest": terminal_path,
            "self_hash_or_size_present": False,
        },
        "workload_result": (
            None if workload_result is None else dict(workload_result)
        ),
    }
    root.write_bytes(terminal_path, canonical_json_bytes(receipt), mode=0o400)
    if status == "CLOSED_NO_AUTHORITY":
        verify_artifact_root_closure(root, manifest, receipt_present=True)
    return receipt


def run_declared_calibration_sample(
    *,
    declaration: Mapping[str, object],
    declaration_identity: Mapping[str, object],
    sample_id: str,
    observer_result_path: Path,
    delegated_cgroup_parent: Path,
    cgroup_name: str,
    stage_disk_root: Path,
    timeout_seconds: float,
    expected_calibration_tool_identities: Mapping[
        str, Mapping[str, object]
    ],
    _prelaunch_check: Any | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Run one exact declared stage and return real observer/sample records."""

    if type(declaration) is not dict or type(declaration.get("stage")) is not str:
        _fail("CALIBRATION_EXECUTION_SURFACE_INVALID", "declaration is malformed")
    stage = cast(str, declaration["stage"])
    package_workload: _PackageWorkload | None = None
    full_workload: _FullWorkload | None = None
    if stage == "FULL_PREFLIGHT":
        full_workload = _validated_full_workload(
            declaration,
            expected_calibration_tool_identities=expected_calibration_tool_identities,
        )
        command = full_workload.command
        working_directory = full_workload.working_directory
        observer_fd = full_workload.observer_fd
        protocol_fd = full_workload.protocol_fd
    else:
        package_workload = _validated_package_workload(
            declaration,
            expected_calibration_tool_identities=expected_calibration_tool_identities,
        )
        command = package_workload.command
        working_directory = package_workload.working_directory
        observer_fd = package_workload.observer_fd
        protocol_fd = package_workload.protocol_fd
    protocol = _load_module_from_fd(
        protocol_fd,
        module_name=f"_ab16_calibration_protocol_sample_{os.getpid()}_{time.monotonic_ns()}",
    )
    checked = protocol.validate_declaration(declaration)
    if (
        timeout_seconds <= 0
        or not delegated_cgroup_parent.is_absolute()
        or not stage_disk_root.is_absolute()
        or not observer_result_path.is_absolute()
    ):
        _fail(
            "CALIBRATION_EXECUTION_SURFACE_INVALID",
            "calibration controller arguments are malformed",
        )
    stage_root = ExclusiveRunRoot.create(stage_disk_root)
    stage_root.mkdir("tmp", mode=0o700)
    cgroup_owner = TransientCalibrationCgroup.create(
        delegated_cgroup_parent,
        name=cgroup_name,
        stage=stage,
    )
    control_read, control_write = os.pipe2(os.O_CLOEXEC)
    result_read, result_write = os.pipe2(os.O_CLOEXEC)
    observer_environment = os.environ.copy()
    observer_environment["PYTHONDONTWRITEBYTECODE"] = "1"
    protocol_raw, _protocol_stat = _read_fd_bytes(
        protocol_fd,
        label="calibration protocol",
    )
    protocol_sha256 = hashlib.sha256(protocol_raw).hexdigest()
    observer = subprocess.Popen(
        [
            command[0],
            "-I",
            "-B",
            f"/proc/self/fd/{observer_fd}",
            "--cgroup",
            str(cgroup_owner.path),
            "--disk",
            str(stage_disk_root),
            "--observer-fd",
            str(observer_fd),
            "--control-fd",
            str(control_read),
            "--protocol-fd",
            str(protocol_fd),
            "--protocol-sha256",
            protocol_sha256,
            "--result-fd",
            str(result_write),
            "--timeout-seconds",
            str(timeout_seconds),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        pass_fds=(control_read, observer_fd, protocol_fd, result_write),
        env=observer_environment,
    )
    os.close(control_read)
    os.close(result_write)
    ready_read, ready_write = os.pipe2(os.O_CLOEXEC)
    release_read, release_write = os.pipe2(os.O_CLOEXEC)
    workload_result_read = -1
    workload_result_write = -1
    stage_root_fd = -1
    workload_result: dict[str, object] | None = None
    cgroup_result: dict[str, object] | None = None
    stage_terminal_published = False
    stage_terminal_attempted = False
    if package_workload is not None:
        workload_result_read, workload_result_write = os.pipe2(os.O_CLOEXEC)
        stage_root_fd = os.open(
            stage_disk_root,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0),
        )
    if _prelaunch_check is not None:
        _prelaunch_check()
    workload_pid = os.fork()
    if workload_pid == 0:
        try:
            os.close(ready_read)
            os.close(release_write)
            os.close(control_write)
            os.close(result_read)
            os.chdir(working_directory)
            os.write(ready_write, b"R")
            if os.read(release_read, 1) != b"G":
                os._exit(126)
            if package_workload is not None:
                os.close(workload_result_read)
                _install_fd_map(
                    {
                        PACKAGE_WORKLOAD_FDS["loader"]: package_workload.loader_fd,
                        PACKAGE_WORKLOAD_FDS["package_root"]: package_workload.package.root_fd,
                        PACKAGE_WORKLOAD_FDS["verifier"]: package_workload.verifier_fd,
                        PACKAGE_WORKLOAD_FDS["workload"]: package_workload.workload_fd,
                        PACKAGE_WORKLOAD_FDS["fixture"]: package_workload.fixture_fd,
                        PACKAGE_WORKLOAD_FDS["stage_root"]: stage_root_fd,
                        PACKAGE_WORKLOAD_FDS["result"]: workload_result_write,
                    }
                )
            child_environment = os.environ.copy()
            child_environment["PYTHONDONTWRITEBYTECODE"] = "1"
            child_environment["TMPDIR"] = str(stage_disk_root / "tmp")
            child_environment["TMP"] = str(stage_disk_root / "tmp")
            child_environment["TEMP"] = str(stage_disk_root / "tmp")
            if stage == "FULL_PREFLIGHT":
                if child_environment.get("PYTEST_ADDOPTS"):
                    os._exit(125)
                child_environment["PYTEST_ADDOPTS"] = (
                    f"--basetemp={stage_disk_root / 'pytest-basetemp'}"
                )
            os.execve(command[0], command, child_environment)
        except BaseException:
            os._exit(127)
    os.close(ready_write)
    os.close(release_read)
    if workload_result_write >= 0:
        os.close(workload_result_write)
        workload_result_write = -1
    workload_waited = False
    primary: BaseException | None = None
    observer_result: dict[str, object] | None = None
    sample: dict[str, object] | None = None
    try:
        deadline = time.monotonic() + timeout_seconds
        cgroup_owner.attach_spawned_child(workload_pid)
        if _read_exact_before(
            ready_read,
            1,
            deadline=deadline,
            label="workload did not join the transient cgroup",
        ) != b"R":
            _fail("CALIBRATION_WORKLOAD_START_FAILED", "child did not join cgroup")
        workload_identity = _process_identity(workload_pid)
        os.write(release_write, b"G")
        status = _waitpid_before(workload_pid, deadline=deadline)
        workload_waited = True
        exit_code = os.waitstatus_to_exitcode(status)
        cgroup_owner.terminate_members(deadline=deadline)
        if package_workload is not None:
            workload_result = _read_frame(workload_result_read)
            if (
                workload_result.get("schema_version")
                != "noncert-cuts-ab16-resource-calibration-workload-result-v1"
                or workload_result.get("authority_scope")
                != "AB16_RESOURCE_CALIBRATION_ONLY"
                or workload_result.get("authorizations")
                != {
                    "formal_attempt_consumption_authorized": False,
                    "formal_campaign_creation_authorized": False,
                    "formal_selection_authorized": False,
                    "gate_b_approval_authorized": False,
                    "organic_arm_launch_authorized": False,
                    "profile_installation_authorized": False,
                    "solver_authority_authorized": False,
                }
                or workload_result.get("status") != "PASS_NO_AUTHORITY"
                or workload_result.get("workload_fidelity")
                != cast(
                    Mapping[str, object],
                    cast(
                        Mapping[str, object],
                        checked["execution_surface"],
                    )["workload_fidelity"],
                )
                or exit_code != 0
            ):
                _fail(
                    "CALIBRATION_WORKLOAD_FAILED",
                    "package workload result or authority boundary differs",
                )
            receipt_raw = canonical_json_bytes(package_workload.package.receipt)
            package_workload.package_verifier.verify_retained_calibration_package(
                package_workload.package.root_fd,
                package_workload.package.root_path,
                expected_receipt_identity={
                    "path": str(
                        package_workload.package.root_path
                        / TERMINAL_RECEIPT_PATH
                    ),
                    "sha256": hashlib.sha256(receipt_raw).hexdigest(),
                    "size_bytes": len(receipt_raw),
                },
            )
        elif exit_code != 0:
            _fail(
                "CALIBRATION_WORKLOAD_FAILED",
                f"full preflight exited {exit_code}",
            )
        _write_frame(
            control_write,
            {
                "action": "WORKLOAD_EXITED_REQUEST_FINAL_CAPTURE",
                "schema_version": OBSERVER_PROTOCOL_SCHEMA,
            },
        )
        if _read_frame(result_read) != {
            "action": "FINAL_CAPTURE_COMPLETE",
            "schema_version": OBSERVER_PROTOCOL_SCHEMA,
        }:
            _fail(
                "CALIBRATION_OBSERVER_PROTOCOL_FAILED",
                "observer did not acknowledge final capture",
            )
        cgroup_result = cgroup_owner.finalize()
        _write_frame(
            control_write,
            {
                "action": "CGROUP_REMOVAL_COMPLETE",
                "schema_version": OBSERVER_PROTOCOL_SCHEMA,
            },
        )
        observer_result = _read_frame(result_read)
        if observer.wait(timeout=5) != 0:
            stderr = b"" if observer.stderr is None else observer.stderr.read()
            _fail(
                "CALIBRATION_OBSERVER_FAILED",
                stderr.decode("utf-8", errors="replace"),
            )
        disk = cast(dict[str, object], observer_result.get("disk"))
        io_record = cast(dict[str, object], cgroup_result["io"])
        polling_growth = cast(int, disk["growth_peak_bytes"])
        io_growth = cast(int, io_record["wbytes_delta"])
        conservative_growth = max(polling_growth, io_growth)
        disk["polling_growth_peak_bytes"] = polling_growth
        disk["cgroup_io"] = dict(io_record)
        disk["growth_peak_bytes"] = conservative_growth
        disk["peak_bytes"] = cast(int, disk["before_bytes"]) + conservative_growth
        disk["measurement_rule"] = (
            "MAX_RETAINED_TREE_POLLING_AND_CGROUP_IO_WBYTES"
        )
        observer_result["memory_peak_bytes"] = cgroup_result[
            "memory_peak_bytes"
        ]
        observer_result["swap_peak_bytes"] = cgroup_result["swap_peak_bytes"]
        observer_result["cgroup_limits"] = cgroup_result["limits"]
        cast(dict[str, object], observer_result["cgroup"])["identity"] = (
            cgroup_result["cgroup_identity"]
        )
        # A CLOSED stage terminal may only follow explicit child closure.
        # Publishing first would leave an immutable success-shaped stage root
        # if waitpid later exposed one still-live adopted/direct child.
        _require_waitpid_echild(deadline=time.monotonic() + 5)
        stage_terminal_attempted = True
        _publish_stage_terminal(
            stage_root,
            stage=stage,
            status="CLOSED_NO_AUTHORITY",
            workload_result=workload_result,
            cgroup_result=cgroup_result,
        )
        stage_terminal_published = True
        sample = protocol.build_sample(
            declaration=declaration,
            declaration_identity=declaration_identity,
            sample_id=sample_id,
            observer_result=observer_result,
            observer_result_identity=_identity(
                observer_result_path,
                observer_result,
            ),
            workload_process_identity=workload_identity,
            workload_exit_code=exit_code,
        )
    except BaseException as exc:
        primary = exc
    finally:
        if not workload_waited:
            if not cgroup_owner.closed:
                try:
                    cgroup_owner.terminate_members(
                        deadline=time.monotonic() + 5
                    )
                except BaseException as cleanup_error:
                    if primary is None:
                        primary = cleanup_error
                    else:
                        primary.add_note(
                            f"cgroup descendant cleanup failed: {cleanup_error}"
                        )
            try:
                os.waitpid(workload_pid, 0)
            except ChildProcessError:
                pass
        for descriptor in (
            ready_read,
            release_write,
            control_write,
            result_read,
            workload_result_read,
            stage_root_fd,
        ):
            if descriptor < 0:
                continue
            try:
                os.close(descriptor)
            except BaseException as close_error:
                if primary is None:
                    primary = close_error
                else:
                    primary.add_note(
                        "calibration controller descriptor close failed: "
                        f"{close_error}"
                    )
        if observer.poll() is None:
            observer.terminate()
            try:
                observer.wait(timeout=5)
            except subprocess.TimeoutExpired:
                observer.kill()
                observer.wait(timeout=5)
        if not cgroup_owner.closed:
            try:
                cgroup_owner.close_after_error()
            except BaseException as close_error:
                if primary is None:
                    primary = close_error
                else:
                    primary.add_note(
                        f"calibration cgroup cleanup failed: {close_error}"
                    )
        if not stage_terminal_published and not stage_terminal_attempted:
            try:
                _publish_stage_terminal(
                    stage_root,
                    stage=stage,
                    status="INCOMPLETE_NO_AUTHORITY",
                    workload_result=workload_result,
                    cgroup_result=cgroup_result,
                )
            except BaseException as terminal_error:
                if primary is None:
                    primary = terminal_error
                else:
                    primary.add_note(
                        f"calibration incomplete terminal failed: {terminal_error}"
                    )
        if package_workload is not None:
            try:
                package_workload.close()
            except BaseException as close_error:
                if primary is None:
                    primary = close_error
                else:
                    primary.add_note(
                        "calibration package close failed: "
                        f"{close_error}"
                    )
        if full_workload is not None:
            try:
                full_workload.close()
            except BaseException as close_error:
                if primary is None:
                    primary = close_error
                else:
                    primary.add_note(
                        f"full calibration role close failed: {close_error}"
                    )
    if primary is not None:
        raise primary
    assert observer_result is not None and sample is not None
    return observer_result, sample


def _require_exact_identity(
    actual: object,
    expected: Mapping[str, object],
    *,
    label: str,
) -> None:
    if actual != expected:
        _fail(
            "CALIBRATION_CHAIN_IDENTITY_MISMATCH",
            f"{label} identity differs from the fixed artifact bytes",
        )


def publish_calibration_cohort(
    root_path: Path | str,
    *,
    declaration: Mapping[str, object],
    observer_results: Sequence[Mapping[str, object]],
    samples: Sequence[Mapping[str, object]],
    validations: Sequence[Mapping[str, object]],
    aggregate: Mapping[str, object],
    installed_profile: Mapping[str, object],
    profile_candidate: Mapping[str, object],
    _existing_root: ExclusiveRunRoot | None = None,
    _protocol_module: ModuleType | None = None,
) -> dict[str, object]:
    """Create and close one immutable calibration root.

    The caller supplies real observer results and the already constructed
    records.  This function independently reconstructs every in-root identity
    and the pure protocol chain before it writes the first byte.
    """

    if (
        len(observer_results) != SAMPLE_COUNT
        or len(samples) != SAMPLE_COUNT
        or len(validations) != SAMPLE_COUNT
    ):
        _fail(
            "CALIBRATION_COHORT_INCOMPLETE",
            "exactly three observer/sample/validation records are required",
        )
    protocol = _load_protocol() if _protocol_module is None else _protocol_module
    root_absolute = Path(root_path).absolute()
    if Path(root_path) != root_absolute:
        _fail(
            "CALIBRATION_ROOT_PATH_INVALID",
            "calibration root path must be absolute",
        )

    declaration_identity = _identity(
        root_absolute / FIXED_PATHS["declaration"],
        declaration,
    )
    installed_profile_identity = _identity(
        root_absolute / FIXED_PATHS["installed_profile"],
        installed_profile,
    )
    checked_declaration = protocol.validate_declaration(declaration)
    _require_exact_identity(
        checked_declaration["installed_profile_identity"],
        installed_profile_identity,
        label="installed profile",
    )

    accepted: list[
        tuple[
            Mapping[str, object],
            Mapping[str, object],
            Mapping[str, object],
            Mapping[str, object],
        ]
    ] = []
    artifact_values: dict[str, object] = {
        FIXED_PATHS["aggregate"]: aggregate,
        FIXED_PATHS["declaration"]: declaration,
        FIXED_PATHS["installed_profile"]: installed_profile,
        FIXED_PATHS["profile_candidate"]: profile_candidate,
    }
    for index, (observer_result, sample, validation) in enumerate(
        zip(observer_results, samples, validations, strict=True),
        start=1,
    ):
        observer_path = FIXED_PATHS[f"observer_result_{index}"]
        sample_path = FIXED_PATHS[f"sample_{index}"]
        validation_path = FIXED_PATHS[f"validation_{index}"]
        observer_identity = _identity(root_absolute / observer_path, observer_result)
        sample_identity = _identity(root_absolute / sample_path, sample)
        validation_identity = _identity(
            root_absolute / validation_path,
            validation,
        )
        measurement_source = sample.get("measurement_source")
        if type(measurement_source) is not dict:
            _fail(
                "CALIBRATION_CHAIN_INVALID",
                f"sample {index} lacks an observer source",
            )
        _require_exact_identity(
            measurement_source.get("observer_result_identity"),
            observer_identity,
            label=f"observer result {index}",
        )
        protocol.validate_sample(
            sample,
            declaration=checked_declaration,
            declaration_identity=declaration_identity,
        )
        protocol.validate_validation(
            validation,
            sample=sample,
            sample_identity=sample_identity,
            declaration=checked_declaration,
            declaration_identity=declaration_identity,
        )
        accepted.append(
            (sample, sample_identity, validation, validation_identity)
        )
        artifact_values[observer_path] = observer_result
        artifact_values[sample_path] = sample
        artifact_values[validation_path] = validation

    aggregator_identity = aggregate.get("aggregator_identity")
    if type(aggregator_identity) is not dict:
        _fail("CALIBRATION_CHAIN_INVALID", "aggregate lacks aggregator identity")
    rebuilt_aggregate = protocol.aggregate_validations(
        declaration=checked_declaration,
        declaration_identity=declaration_identity,
        accepted=accepted,
        aggregator_identity=aggregator_identity,
    )
    if rebuilt_aggregate != aggregate:
        _fail(
            "CALIBRATION_CHAIN_INVALID",
            "aggregate is not the canonical result of the three validations",
        )
    aggregate_identity = _identity(
        root_absolute / FIXED_PATHS["aggregate"],
        aggregate,
    )
    candidate_builder_identity = profile_candidate.get(
        "candidate_builder_identity"
    )
    if type(candidate_builder_identity) is not dict:
        _fail(
            "CALIBRATION_CHAIN_INVALID",
            "profile candidate lacks builder identity",
        )
    rebuilt_candidate = protocol.build_installed_profile_candidate(
        declaration=checked_declaration,
        declaration_identity=declaration_identity,
        aggregate=aggregate,
        aggregate_identity=aggregate_identity,
        installed_profile=installed_profile,
        candidate_builder_identity=candidate_builder_identity,
    )
    if rebuilt_candidate != profile_candidate:
        _fail(
            "CALIBRATION_CHAIN_INVALID",
            "profile candidate is not the canonical preinstalled-profile result",
        )

    run_root = (
        ExclusiveRunRoot.create(root_absolute)
        if _existing_root is None
        else _existing_root
    )
    if run_root.path != root_absolute:
        _fail(
            "CALIBRATION_ROOT_IDENTITY_DRIFT",
            "retained cohort root path differs from the planned root",
        )
    if _existing_root is None:
        run_root.mkdir("observer-results", mode=0o700)
        run_root.mkdir("samples", mode=0o700)
        run_root.mkdir("validations", mode=0o700)
    artifacts: list[dict[str, object]] = []
    for relative, value in sorted(artifact_values.items()):
        if _existing_root is not None and relative == FIXED_PATHS[
            "installed_profile"
        ]:
            snapshot = read_stable_snapshot(
                root_absolute / relative,
                expected_sha256=hashlib.sha256(
                    canonical_json_bytes(value)
                ).hexdigest(),
                expected_size_bytes=len(canonical_json_bytes(value)),
            )
            if snapshot.identity.path != str((root_absolute / relative).absolute()):
                _fail(
                    "CALIBRATION_PROFILE_IDENTITY_INVALID",
                    "prewritten installed-profile path identity drifted",
                )
        else:
            run_root.write_bytes(
                relative,
                canonical_json_bytes(value),
                mode=0o400,
            )
        artifacts.append(_artifact_identity(relative, value))
    manifest = build_artifact_root_manifest(run_root)
    receipt: dict[str, object] = {
        "artifacts": artifacts,
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "fixed_paths": dict(FIXED_PATHS),
        "manifest": manifest,
        "root_identity": _root_identity(root_absolute),
        "schema_version": RECEIPT_SCHEMA,
        "status": "CLOSED_NO_LAUNCH_AUTHORITY",
    }
    run_root.write_bytes(
        TERMINAL_RECEIPT_PATH,
        canonical_json_bytes(receipt),
        mode=0o400,
    )
    verify_artifact_root_closure(
        run_root,
        manifest,
        receipt_present=True,
    )
    if _root_identity(root_absolute) != receipt["root_identity"]:
        _fail(
            "CALIBRATION_ROOT_IDENTITY_DRIFT",
            "calibration root identity changed across receipt publication",
        )
    return receipt


def publish_calibration_authorization_bundle_set(
    root_path: Path | str,
    *,
    bundles: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Publish exact canonical three-stage bundle bytes in one closed root."""

    protocol = _load_protocol()
    root_absolute = Path(root_path).absolute()
    if Path(root_path) != root_absolute:
        _fail(
            "CALIBRATION_ROOT_PATH_INVALID",
            "bundle-set root path must be absolute",
        )
    detached_paths = {
        stage: str(root_absolute / relative)
        for stage, relative in BUNDLE_PATHS.items()
    }
    bundle_set = protocol.build_calibration_authorization_bundle_set(
        bundles=bundles,
        detached_paths=detached_paths,
    )
    protocol.validate_calibration_authorization_bundle_set(bundle_set)
    records = cast(
        dict[str, dict[str, object]],
        bundle_set["resource_calibration_authorization_bundles"],
    )
    run_root = ExclusiveRunRoot.create(root_absolute)
    run_root.mkdir("bundles", mode=0o700)
    for stage, relative in sorted(BUNDLE_PATHS.items()):
        run_root.write_bytes(
            relative,
            canonical_json_bytes(records[stage]["record"]),
            mode=0o400,
        )
    manifest = build_artifact_root_manifest(run_root)
    receipt = {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "bundle_identities": bundle_set[
            "resource_calibration_bundle_identities"
        ],
        "manifest": manifest,
        "schema_version": BUNDLE_SET_RECEIPT_SCHEMA,
        "stages": sorted(BUNDLE_PATHS),
        "status": "CLOSED_NO_LAUNCH_AUTHORITY",
        "terminal_self_exclusion": {
            "excluded_from_manifest": TERMINAL_RECEIPT_PATH,
            "self_hash_or_size_present": False,
        },
    }
    run_root.write_bytes(
        TERMINAL_RECEIPT_PATH,
        canonical_json_bytes(receipt),
        mode=0o400,
    )
    verify_artifact_root_closure(
        run_root,
        manifest,
        receipt_present=True,
    )
    return {
        "bundle_set": bundle_set,
        "receipt": receipt,
    }


COHORT_INCOMPLETE_SCHEMA: Final = (
    "noncert-cuts-ab16-resource-calibration-cohort-incomplete-v1"
)
_PACKAGE_ROLE_BY_TOOL: Final = {
    "aggregator": "calibration-aggregator",
    "alternate_replayer": "calibration-alternate-replay",
    "fd_loader": "calibration-fd-loader",
    "observer_harness": "calibration-observer",
    "package_verifier": "calibration-package-verifier",
    "primary_replayer": "calibration-primary-replay",
    "protocol": "calibration-protocol",
    "runner": "calibration-runner",
    "workload": "calibration-workload",
}
_CONTROLLER_ACTIONS: Final = frozenset(
    {
        "INSPECT_NO_AUTHORITY",
        "RUN_ONE_ACCEPTANCE",
        "RUN_THREE_SAMPLE_COHORT",
    }
)
_PACKAGE_RESOURCE_ADMISSION_RELATIVE: Final = (
    "materialized/repository/docs/research/noncert_cuts_ab16_20260724/"
    "ab16_resource_admission_v1.py"
)


def _strict_json_bytes(raw: bytes, *, label: str) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                _fail("CALIBRATION_CONTROLLER_PLAN_INVALID", f"{label}: duplicate {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=pairs,
            parse_constant=lambda token: _fail(
                "CALIBRATION_CONTROLLER_PLAN_INVALID",
                f"{label}: non-finite JSON token {token}",
            ),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        _fail("CALIBRATION_CONTROLLER_PLAN_INVALID", f"{label}: {exc}")
    if type(value) is not dict or canonical_json_bytes(value) != raw:
        _fail(
            "CALIBRATION_CONTROLLER_PLAN_INVALID",
            f"{label} is not one canonical JSON object",
        )
    return cast(dict[str, object], value)


def _read_regular_fd(
    descriptor: int,
    *,
    label: str,
    maximum_bytes: int | None = None,
) -> tuple[bytes, os.stat_result]:
    flags = fcntl.fcntl(descriptor, fcntl.F_GETFL)
    before = os.fstat(descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or flags & os.O_ACCMODE != os.O_RDONLY
        or (maximum_bytes is not None and before.st_size > maximum_bytes)
    ):
        _fail(
            "CALIBRATION_CONTROLLER_FD_INVALID",
            f"{label} is not one bounded read-only regular file",
        )
    raw, after = _read_fd_bytes(descriptor, label=label)
    if (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        _fail(
            "CALIBRATION_CONTROLLER_FD_INVALID",
            f"{label} identity drifted",
        )
    return raw, after


def _open_package_member(root_fd: int, relative: str, *, label: str) -> int:
    parts = relative.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        _fail("CALIBRATION_CONTROLLER_PACKAGE_INVALID", f"{label} path is unsafe")
    directory_fd = os.dup(root_fd)
    result = -1
    primary: BaseException | None = None
    try:
        for component in parts[:-1]:
            successor = os.open(
                component,
                os.O_RDONLY
                | os.O_DIRECTORY
                | os.O_CLOEXEC
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=directory_fd,
            )
            os.close(directory_fd)
            directory_fd = successor
        result = os.open(
            parts[-1],
            os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_fd,
        )
    except BaseException as exc:
        primary = exc
    try:
        os.close(directory_fd)
    except BaseException as close_error:
        if primary is None:
            primary = close_error
        else:
            primary.add_note(f"{label} parent close failed: {close_error}")
    if primary is not None:
        if result >= 0:
            try:
                os.close(result)
            except BaseException as close_error:
                primary.add_note(f"{label} member close failed: {close_error}")
        raise primary
    return result


def _absolute_identity_from_package(
    *,
    package_root_path: Path,
    relative: str,
    relative_identity: Mapping[str, object],
) -> dict[str, object]:
    if relative_identity.get("path") != relative:
        _fail(
            "CALIBRATION_CONTROLLER_PACKAGE_INVALID",
            f"package identity path differs for {relative}",
        )
    return {
        "path": str((package_root_path / relative).absolute()),
        "sha256": relative_identity["sha256"],
        "size_bytes": relative_identity["size_bytes"],
    }


def _verify_retained_controller_package(
    *,
    package_root_fd: int,
    package_root_path: Path,
    package_receipt_identity: Mapping[str, object],
    package_verifier_fd: int,
    package_verifier_sha256: str,
    executing_runner_fd: int,
) -> tuple[
    dict[str, object],
    ModuleType,
    ModuleType | None,
    ModuleType,
    ModuleType,
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
]:
    if (
        not sys.flags.isolated
        or not sys.flags.ignore_environment
        or not sys.flags.no_user_site
        or not bool(getattr(sys.flags, "safe_path", False))
        or not sys.flags.dont_write_bytecode
        or not sys.dont_write_bytecode
    ):
        _fail(
            "CALIBRATION_CONTROLLER_PROCESS_INVALID",
            "controller requires one -I -B Python process",
        )
    root_stat = os.fstat(package_root_fd)
    if not stat.S_ISDIR(root_stat.st_mode):
        _fail(
            "CALIBRATION_CONTROLLER_PACKAGE_INVALID",
            "retained package root FD is not a directory",
        )
    verifier_raw, _verifier_stat = _read_regular_fd(
        package_verifier_fd,
        label="package verifier",
    )
    if hashlib.sha256(verifier_raw).hexdigest() != package_verifier_sha256:
        _fail(
            "CALIBRATION_CONTROLLER_PACKAGE_INVALID",
            "package verifier FD differs from its command-line pin",
        )
    verifier = _load_module_from_fd(
        package_verifier_fd,
        module_name=(
            f"_ab16_calibration_controller_package_verifier_"
            f"{os.getpid()}_{time.monotonic_ns()}"
        ),
    )
    receipt = verifier.verify_retained_calibration_package(
        package_root_fd,
        package_root_path,
        expected_receipt_identity=package_receipt_identity,
    )
    if (
        type(receipt) is not dict
        or receipt.get("status") != "CLOSED_NO_AUTHORITY"
        or type(receipt.get("authorizations")) is not dict
        or any(
            value is not False
            for value in cast(dict[str, object], receipt["authorizations"]).values()
        )
    ):
        _fail(
            "CALIBRATION_CONTROLLER_PACKAGE_INVALID",
            "package authority boundary is not entirely false",
        )
    roles = cast(dict[str, str], receipt["roles"])
    identities = cast(dict[str, dict[str, object]], receipt["member_identities"])
    runner_relative = roles["calibration-runner"]
    runner_raw, runner_stat = _read_regular_fd(
        executing_runner_fd,
        label="executing calibration runner",
    )
    expected_runner = identities[runner_relative]
    if (
        expected_runner
        != {
            "path": runner_relative,
            "sha256": hashlib.sha256(runner_raw).hexdigest(),
            "size_bytes": len(runner_raw),
        }
        or not str(Path(__file__)).startswith("/proc/self/fd/")
        or os.stat(__file__).st_dev != runner_stat.st_dev
        or os.stat(__file__).st_ino != runner_stat.st_ino
    ):
        _fail(
            "CALIBRATION_CONTROLLER_EXECUTING_SOURCE_DRIFT",
            "executing controller is not the exact retained package runner FD",
        )
    verifier_relative = roles["calibration-package-verifier"]
    if identities[verifier_relative] != {
        "path": verifier_relative,
        "sha256": hashlib.sha256(verifier_raw).hexdigest(),
        "size_bytes": len(verifier_raw),
    }:
        _fail(
            "CALIBRATION_CONTROLLER_PACKAGE_INVALID",
            "retained verifier differs from the package role identity",
        )
    expected_tools: dict[str, dict[str, object]] = {}
    absolute_tools: dict[str, dict[str, object]] = {}
    for tool, role in sorted(_PACKAGE_ROLE_BY_TOOL.items()):
        relative = roles[role]
        relative_identity = identities[relative]
        expected_tools[tool] = {
            "sha256": relative_identity["sha256"],
            "size_bytes": relative_identity["size_bytes"],
        }
        absolute_tools[tool] = _absolute_identity_from_package(
            package_root_path=package_root_path,
            relative=relative,
            relative_identity=relative_identity,
        )
    protocol_fd = _open_package_member(
        package_root_fd,
        roles["calibration-protocol"],
        label="calibration protocol",
    )
    try:
        protocol = _load_module_from_fd(
            protocol_fd,
            module_name=(
                f"_ab16_calibration_controller_protocol_"
                f"{os.getpid()}_{time.monotonic_ns()}"
            ),
        )
    finally:
        os.close(protocol_fd)
    validator_fd = _open_package_member(
        package_root_fd,
        roles["calibration-primary-replay"],
        label="calibration sample validator",
    )
    try:
        validator = _load_module_from_fd(
            validator_fd,
            module_name=(
                f"_ab16_calibration_controller_validator_"
                f"{os.getpid()}_{time.monotonic_ns()}"
            ),
        )
    finally:
        os.close(validator_fd)
    aggregator_fd = _open_package_member(
        package_root_fd,
        roles["calibration-aggregator"],
        label="calibration cohort aggregator",
    )
    try:
        aggregator = _load_module_from_fd(
            aggregator_fd,
            module_name=(
                f"_ab16_calibration_controller_aggregator_"
                f"{os.getpid()}_{time.monotonic_ns()}"
            ),
        )
    finally:
        os.close(aggregator_fd)
    admission: ModuleType | None = None
    if receipt.get("layout") == "PORTABLE_CANDIDATE_V1":
        admission_identity = identities.get(_PACKAGE_RESOURCE_ADMISSION_RELATIVE)
        if admission_identity is None:
            _fail(
                "CALIBRATION_CONTROLLER_PACKAGE_INVALID",
                "portable package omits the resource-admission execution member",
            )
        admission_fd = _open_package_member(
            package_root_fd,
            _PACKAGE_RESOURCE_ADMISSION_RELATIVE,
            label="resource admission module",
        )
        try:
            admission_raw, _admission_stat = _read_regular_fd(
                admission_fd,
                label="resource admission module",
            )
            if admission_identity != {
                "path": _PACKAGE_RESOURCE_ADMISSION_RELATIVE,
                "sha256": hashlib.sha256(admission_raw).hexdigest(),
                "size_bytes": len(admission_raw),
            }:
                _fail(
                    "CALIBRATION_CONTROLLER_PACKAGE_INVALID",
                    "resource-admission member identity drifted",
                )
            admission = _load_module_from_fd(
                admission_fd,
                module_name=(
                    f"_ab16_calibration_controller_admission_"
                    f"{os.getpid()}_{time.monotonic_ns()}"
                ),
            )
        finally:
            os.close(admission_fd)
        absolute_tools["resource_admission"] = _absolute_identity_from_package(
            package_root_path=package_root_path,
            relative=_PACKAGE_RESOURCE_ADMISSION_RELATIVE,
            relative_identity=admission_identity,
        )
    return (
        receipt,
        protocol,
        admission,
        validator,
        aggregator,
        expected_tools,
        absolute_tools,
    )


def _absolute_output_path(value: object, *, label: str) -> Path:
    if type(value) is not str:
        _fail("CALIBRATION_CONTROLLER_PLAN_INVALID", f"{label} is not a string")
    path = Path(value)
    if path != path.absolute() or not path.is_absolute() or path == Path("/"):
        _fail(
            "CALIBRATION_CONTROLLER_PLAN_INVALID",
            f"{label} is not one non-root absolute path",
        )
    return path


def _path_is_ancestor(first: Path, second: Path) -> bool:
    try:
        second.relative_to(first)
    except ValueError:
        return False
    return True


def _require_planned_outputs_fresh(paths: Sequence[Path]) -> None:
    for index, first in enumerate(paths):
        for second in paths[index + 1 :]:
            if _path_is_ancestor(first, second) or _path_is_ancestor(second, first):
                _fail(
                    "CALIBRATION_CONTROLLER_PLAN_INVALID",
                    f"planned outputs overlap: {first} and {second}",
                )
    for path in paths:
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            _fail(
                "CALIBRATION_CONTROLLER_OUTPUT_UNTRUSTED",
                f"cannot inspect planned output {path}: {exc}",
            )
        _fail(
            "CALIBRATION_CONTROLLER_NO_OVERWRITE",
            f"planned output already exists: {path}",
        )


def validate_calibration_controller_plan(
    plan: object,
    *,
    protocol: ModuleType,
    package_receipt: Mapping[str, object],
    package_receipt_identity: Mapping[str, object],
    absolute_tool_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    fields = {
        "action",
        "authority_scope",
        "authorizations",
        "cohort_root",
        "controller_root",
        "declaration",
        "delegated_cgroup_parent",
        "installed_profile",
        "outside_replay_outputs",
        "package_receipt_identity",
        "resource_admission",
        "sample_runs",
        "schema_version",
        "status",
        "timeout_seconds",
    }
    if type(plan) is not dict or set(plan) != fields:
        _fail(
            "CALIBRATION_CONTROLLER_PLAN_INVALID",
            "controller plan field set drifted",
        )
    checked = cast(dict[str, object], plan)
    action = checked["action"]
    if (
        checked["schema_version"] != CONTROLLER_PLAN_SCHEMA
        or checked["authority_scope"] != AUTHORITY_SCOPE
        or checked["authorizations"] != FALSE_AUTHORIZATIONS
        or checked["status"] != "PLANNED_NO_AUTHORITY"
        or action not in _CONTROLLER_ACTIONS
        or checked["package_receipt_identity"] != package_receipt_identity
    ):
        _fail(
            "CALIBRATION_CONTROLLER_PLAN_INVALID",
            "controller plan discriminator, package, or authority boundary drifted",
        )
    timeout = checked["timeout_seconds"]
    if type(timeout) is not int or timeout < 1 or timeout > 24 * 60 * 60:
        _fail(
            "CALIBRATION_CONTROLLER_PLAN_INVALID",
            "controller timeout is not a bounded integer",
        )
    controller_root = _absolute_output_path(
        checked["controller_root"],
        label="controller root",
    )
    cohort_root = _absolute_output_path(
        checked["cohort_root"],
        label="cohort root",
    )
    cgroup_parent = _absolute_output_path(
        checked["delegated_cgroup_parent"],
        label="delegated cgroup parent",
    )
    replay_value = checked["outside_replay_outputs"]
    if type(replay_value) is not dict or set(replay_value) != {
        "alternate",
        "primary",
    }:
        _fail(
            "CALIBRATION_CONTROLLER_PLAN_INVALID",
            "outside replay output set is not exact",
        )
    replay_outputs = {
        label: _absolute_output_path(path, label=f"{label} replay output")
        for label, path in cast(dict[str, object], replay_value).items()
    }
    sample_value = checked["sample_runs"]
    expected_sample_runs = (
        1 if action == "RUN_ONE_ACCEPTANCE" else SAMPLE_COUNT
    )
    if (
        type(sample_value) is not list
        or len(sample_value) != expected_sample_runs
    ):
        _fail(
            "CALIBRATION_CONTROLLER_PLAN_INVALID",
            f"controller plan requires exactly {expected_sample_runs} sample run(s)",
        )
    sample_runs: list[dict[str, object]] = []
    sample_ids: set[str] = set()
    cgroup_names: set[str] = set()
    stage_roots: list[Path] = []
    for index, raw in enumerate(cast(list[object], sample_value), start=1):
        if type(raw) is not dict or set(raw) != {
            "cgroup_name",
            "sample_id",
            "stage_root",
        }:
            _fail(
                "CALIBRATION_CONTROLLER_PLAN_INVALID",
                f"sample run {index} field set drifted",
            )
        row = cast(dict[str, object], raw)
        sample_id = row["sample_id"]
        cgroup_name = row["cgroup_name"]
        if (
            type(sample_id) is not str
            or type(cgroup_name) is not str
            or not sample_id
            or not cgroup_name
            or len(sample_id) > 128
            or len(cgroup_name) > 128
            or any(
                character
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
                for character in sample_id + cgroup_name
            )
            or sample_id in sample_ids
            or cgroup_name in cgroup_names
        ):
            _fail(
                "CALIBRATION_CONTROLLER_PLAN_INVALID",
                f"sample run {index} ID/cgroup name is invalid or duplicated",
            )
        stage_root = _absolute_output_path(
            row["stage_root"],
            label=f"sample run {index} stage root",
        )
        sample_ids.add(sample_id)
        cgroup_names.add(cgroup_name)
        stage_roots.append(stage_root)
        sample_runs.append(
            {
                "cgroup_name": cgroup_name,
                "sample_id": sample_id,
                "stage_root": str(stage_root),
            }
        )
    planned_outputs = [
        controller_root,
        cohort_root,
        *stage_roots,
        *replay_outputs.values(),
    ]
    _require_planned_outputs_fresh(planned_outputs)
    for name in cgroup_names:
        _require_planned_outputs_fresh([cgroup_parent / name])

    declaration = protocol.validate_declaration(checked["declaration"])
    profile = checked["installed_profile"]
    if type(profile) is not dict:
        _fail(
            "CALIBRATION_CONTROLLER_PLAN_INVALID",
            "installed profile is not an object",
        )
    profile_identity = _identity(
        cohort_root / FIXED_PATHS["installed_profile"],
        profile,
    )
    if declaration["installed_profile_identity"] != profile_identity:
        _fail(
            "CALIBRATION_CONTROLLER_PLAN_INVALID",
            "declaration does not bind the prewritten cohort profile bytes",
        )
    surface = cast(dict[str, object], declaration["execution_surface"])
    portable = cast(dict[str, object], surface["portable_package"])
    host_runtime_content = {
        label: {
            "sha256": identity["sha256"],
            "size_bytes": identity["size_bytes"],
        }
        for label, identity in sorted(
            cast(
                dict[str, dict[str, object]],
                package_receipt["host_runtime_identities"],
            ).items()
        )
    }
    if (
        portable["package_receipt_identity"] != package_receipt_identity
        or portable["layout"] != package_receipt["layout"]
        or portable["package_schema_version"]
        != package_receipt["schema_version"]
        or portable["source_sets_sha256"]
        != hashlib.sha256(
            canonical_json_bytes(package_receipt["source_sets"])
        ).hexdigest()
        or portable["host_runtime_content_sha256"]
        != hashlib.sha256(
            canonical_json_bytes(host_runtime_content)
        ).hexdigest()
    ):
        _fail(
            "CALIBRATION_CONTROLLER_PLAN_INVALID",
            "declaration package closure differs",
        )
    member_identities = cast(
        dict[str, dict[str, object]],
        surface["execution_member_identities"],
    )
    for label in (
        "calibration_aggregator",
        "calibration_observer",
        "calibration_protocol",
        "calibration_runner",
    ):
        tool = {
            "calibration_aggregator": "aggregator",
            "calibration_observer": "observer_harness",
            "calibration_protocol": "protocol",
            "calibration_runner": "runner",
        }[label]
        if member_identities.get(label) != absolute_tool_identities[tool]:
            _fail(
                "CALIBRATION_CONTROLLER_PLAN_INVALID",
                f"execution member {label} is not the retained package role",
            )
    if (
        declaration["harness_identity"] != absolute_tool_identities["runner"]
        or declaration["observer_identity"]
        != absolute_tool_identities["observer_harness"]
    ):
        _fail(
            "CALIBRATION_CONTROLLER_PLAN_INVALID",
            "declaration harness/observer identities are not package-pinned",
        )
    if action in {"RUN_ONE_ACCEPTANCE", "RUN_THREE_SAMPLE_COHORT"}:
        fidelity = cast(dict[str, object], surface["workload_fidelity"])
        if (
            package_receipt.get("layout") != "PORTABLE_CANDIDATE_V1"
            or fidelity.get("launch_admissible") is not True
        ):
            _fail(
                "CALIBRATION_CONTROLLER_PLAN_INVALID",
                "real samples require one portable launch-comparable package",
            )
        admission = checked["resource_admission"]
        if (
            type(admission) is not dict
            or set(admission)
            != {
                "allowed_same_uid_processes",
                "enforced_budget_profile",
                "enforced_budget_profile_identity",
                "cgroup_parent_contract",
                "lock_acquisition",
                "lock_identities",
                "lock_identity_format",
                "observation_context",
            }
            or type(admission["allowed_same_uid_processes"]) is not list
            or admission["allowed_same_uid_processes"] != []
            or type(admission["lock_identities"]) is not list
            or type(admission["lock_identity_format"]) is not str
            or type(admission["observation_context"]) is not dict
            or admission["lock_acquisition"]
            not in {
                "PACKAGE_PINNED_CONTROLLER_ACQUIRE",
                "RETAINED_LOCK_FD_TRANSFER",
            }
            or admission["cgroup_parent_contract"]
            != {
                "delegation": "CGROUP_V2_USER_DELEGATED_PARENT",
                "parent_path": str(cgroup_parent),
                "required_controllers": ["io", "memory"],
                "requires_owned_writable_parent": True,
                "transient_child_per_sample": True,
            }
            or member_identities.get("resource_admission")
            != absolute_tool_identities.get("resource_admission")
        ):
            _fail(
                "CALIBRATION_CONTROLLER_PLAN_INVALID",
                "real sample resource-admission contract is absent or unpinned",
            )
        stage_parents = {str(path.parent) for path in stage_roots}
        if len(stage_parents) != 1:
            _fail(
                "CALIBRATION_CONTROLLER_PLAN_INVALID",
                "three stage roots do not share one admission disk target",
            )
        if admission["enforced_budget_profile"] is None:
            if admission["enforced_budget_profile_identity"] is not None:
                _fail(
                    "CALIBRATION_CONTROLLER_PLAN_INVALID",
                    "budget profile identity exists without profile bytes",
                )
        elif (
            type(admission["enforced_budget_profile"]) is not dict
            or type(admission["enforced_budget_profile_identity"]) is not dict
        ):
            _fail(
                "CALIBRATION_CONTROLLER_PLAN_INVALID",
                "enforced budget profile pair is malformed",
            )
    elif checked["resource_admission"] is not None:
        _fail(
            "CALIBRATION_CONTROLLER_PLAN_INVALID",
            "inspect-only controller unexpectedly carries launch admission",
        )
    return {
        **checked,
        "cohort_root": str(cohort_root),
        "controller_root": str(controller_root),
        "delegated_cgroup_parent": str(cgroup_parent),
        "outside_replay_outputs": {
            label: str(path) for label, path in sorted(replay_outputs.items())
        },
        "sample_runs": sample_runs,
    }


def _terminal_receipt_identity(path: Path) -> dict[str, object]:
    snapshot = read_stable_snapshot(path)
    return {
        "path": str(path.absolute()),
        "sha256": snapshot.identity.sha256,
        "size_bytes": snapshot.identity.size_bytes,
    }


def _publish_controller_terminal(
    root: ExclusiveRunRoot,
    *,
    plan_identity: Mapping[str, object],
    package_receipt_identity: Mapping[str, object],
    stage: str,
    status: str,
    cohort_receipt_identity: Mapping[str, object] | None,
    replay_contract: Mapping[str, object] | None,
    failure: Mapping[str, object] | None,
) -> dict[str, object]:
    terminal_path = (
        "receipt.json"
        if status == "CLOSED_NO_LAUNCH_AUTHORITY"
        else "terminal-incomplete.json"
    )
    manifest = build_artifact_root_manifest(root)
    receipt = {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "cohort_receipt_identity": (
            None
            if cohort_receipt_identity is None
            else dict(cohort_receipt_identity)
        ),
        "failure": None if failure is None else dict(failure),
        "manifest": manifest,
        "package_receipt_identity": dict(package_receipt_identity),
        "plan_identity": dict(plan_identity),
        "replay_contract": (
            None if replay_contract is None else dict(replay_contract)
        ),
        "schema_version": CONTROLLER_TERMINAL_SCHEMA,
        "stage": stage,
        "status": status,
        "terminal_self_exclusion": {
            "excluded_from_manifest": terminal_path,
            "self_hash_or_size_present": False,
        },
    }
    root.write_bytes(terminal_path, canonical_json_bytes(receipt), mode=0o400)
    if status == "CLOSED_NO_LAUNCH_AUTHORITY":
        verify_artifact_root_closure(root, manifest, receipt_present=True)
    return receipt


def _close_incomplete_cohort(
    root: ExclusiveRunRoot,
    *,
    stage: str,
    failure: BaseException,
) -> None:
    if (root.path / "receipt.json").exists():
        return
    manifest = build_artifact_root_manifest(root)
    record = {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "code": getattr(failure, "code", type(failure).__name__),
        "conclusion": None,
        "manifest": manifest,
        "schema_version": COHORT_INCOMPLETE_SCHEMA,
        "stage": stage,
        "status": "INCOMPLETE_NO_AUTHORITY",
        "terminal_self_exclusion": {
            "excluded_from_manifest": "receipt.json",
            "self_hash_or_size_present": False,
        },
    }
    root.write_bytes("receipt.json", canonical_json_bytes(record), mode=0o400)
    verify_artifact_root_closure(root, manifest, receipt_present=True)


def _publish_one_acceptance_terminal(
    root: ExclusiveRunRoot,
    *,
    stage: str,
    declaration: Mapping[str, object],
    observer_result: Mapping[str, object],
    sample: Mapping[str, object],
) -> dict[str, object]:
    root.write_bytes(
        "declaration.json",
        canonical_json_bytes(declaration),
        mode=0o400,
    )
    root.write_bytes(
        "observer-results/01.json",
        canonical_json_bytes(observer_result),
        mode=0o400,
    )
    root.write_bytes(
        "samples/01.json",
        canonical_json_bytes(sample),
        mode=0o400,
    )
    manifest = build_artifact_root_manifest(root)
    receipt = {
        "authority_scope": AUTHORITY_SCOPE,
        "authorizations": dict(FALSE_AUTHORIZATIONS),
        "declaration_identity": _identity(
            root.path / "declaration.json",
            declaration,
        ),
        "manifest": manifest,
        "observer_result_identity": _identity(
            root.path / "observer-results/01.json",
            observer_result,
        ),
        "sample_identity": _identity(root.path / "samples/01.json", sample),
        "schema_version": ACCEPTANCE_TERMINAL_SCHEMA,
        "stage": stage,
        "status": "CLOSED_NO_LAUNCH_AUTHORITY",
        "terminal_self_exclusion": {
            "excluded_from_manifest": "receipt.json",
            "self_hash_or_size_present": False,
        },
    }
    root.write_bytes("receipt.json", canonical_json_bytes(receipt), mode=0o400)
    verify_artifact_root_closure(root, manifest, receipt_present=True)
    return receipt


def run_calibration_controller(
    plan: Mapping[str, object],
    *,
    protocol: ModuleType,
    package_receipt: Mapping[str, object],
    package_receipt_identity: Mapping[str, object],
    expected_tool_identities: Mapping[str, Mapping[str, object]],
    absolute_tool_identities: Mapping[str, Mapping[str, object]],
    resource_admission_module: ModuleType | None = None,
    validator_module: ModuleType | None = None,
    aggregator_module: ModuleType | None = None,
    held_resource_locks: Any | None = None,
    _sample_executor: Any = run_declared_calibration_sample,
    _admission_evaluator: Any | None = None,
) -> dict[str, object]:
    """Run or inspect one exact zero-authority calibration controller plan."""

    checked = validate_calibration_controller_plan(
        plan,
        protocol=protocol,
        package_receipt=package_receipt,
        package_receipt_identity=package_receipt_identity,
        absolute_tool_identities=absolute_tool_identities,
    )
    declaration = cast(dict[str, object], checked["declaration"])
    stage = cast(str, declaration["stage"])
    if checked["action"] == "INSPECT_NO_AUTHORITY":
        return {
            "action": "INSPECT_NO_AUTHORITY",
            "authority_scope": AUTHORITY_SCOPE,
            "authorizations": dict(FALSE_AUTHORIZATIONS),
            "package_authorizations": dict(
                cast(dict[str, object], package_receipt["authorizations"])
            ),
            "schema_version": CONTROLLER_INSPECTION_SCHEMA,
            "stage": stage,
            "status": "PASS_NO_OUTPUT",
        }
    if (
        resource_admission_module is None
        or validator_module is None
        or aggregator_module is None
        or held_resource_locks is None
    ):
        _fail(
            "CALIBRATION_CONTROLLER_ADMISSION_REQUIRED",
            "real calibration requires package-pinned admission/validator/aggregator roles and three retained locks",
        )
    admission_plan = cast(dict[str, object], checked["resource_admission"])
    live_lock_identities = held_resource_locks.identities()
    if live_lock_identities != admission_plan["lock_identities"]:
        _fail(
            "CALIBRATION_CONTROLLER_LOCK_DRIFT",
            "plan and retained three-lock identities differ",
        )
    admission_function = (
        resource_admission_module.evaluate_calibration_prelaunch_resource_admission
        if _admission_evaluator is None
        else _admission_evaluator
    )
    disk_target = Path(
        cast(
            str,
            cast(list[dict[str, object]], checked["sample_runs"])[0][
                "stage_root"
            ],
        )
    ).parent

    def evaluate_now() -> dict[str, object]:
        held_resource_locks.identities()
        result = admission_function(
            disk_target,
            stage=stage,
            lock_identities=live_lock_identities,
            lock_identity_format=admission_plan["lock_identity_format"],
            observation_context=admission_plan["observation_context"],
            installed_profile=checked["installed_profile"],
            enforced_budget_profile=admission_plan["enforced_budget_profile"],
            enforced_budget_profile_identity=admission_plan[
                "enforced_budget_profile_identity"
            ],
            allowed_same_uid_processes=admission_plan[
                "allowed_same_uid_processes"
            ],
        )
        if (
            type(result) is not dict
            or result.get("status") != "PASS_NO_LAUNCH_AUTHORITY"
            or type(result.get("authorizations")) is not dict
            or any(
                value is not False
                for value in cast(
                    dict[str, object],
                    result["authorizations"],
                ).values()
            )
            or result.get("stage") != stage
        ):
            _fail(
                "CALIBRATION_CONTROLLER_ADMISSION_INVALID",
                "package-pinned admission evaluator did not return one false-authority PASS",
            )
        return dict(result)

    controller_root: ExclusiveRunRoot | None = None
    cohort_root: ExclusiveRunRoot | None = None
    plan_identity: dict[str, object] | None = None
    try:
        initial_admission = evaluate_now()
        controller_root = ExclusiveRunRoot.create(
            cast(str, checked["controller_root"])
        )
        controller_root.mkdir("resource-admission", mode=0o700)
        controller_root.write_bytes(
            "plan.json",
            canonical_json_bytes(checked),
            mode=0o400,
        )
        controller_root.write_bytes(
            "resource-admission/initial.json",
            canonical_json_bytes(initial_admission),
            mode=0o400,
        )
        plan_identity = _identity(controller_root.path / "plan.json", checked)
        cohort_root = ExclusiveRunRoot.create(cast(str, checked["cohort_root"]))
        cohort_root.mkdir("observer-results", mode=0o700)
        cohort_root.mkdir("samples", mode=0o700)
        if checked["action"] == "RUN_THREE_SAMPLE_COHORT":
            cohort_root.mkdir("validations", mode=0o700)
        cohort_root.write_bytes(
            FIXED_PATHS["installed_profile"],
            canonical_json_bytes(checked["installed_profile"]),
            mode=0o400,
        )
        declaration_identity = _identity(
            cohort_root.path / FIXED_PATHS["declaration"],
            declaration,
        )
        observer_results: list[dict[str, object]] = []
        samples: list[dict[str, object]] = []
        validations: list[dict[str, object]] = []
        accepted: list[
            tuple[
                Mapping[str, object],
                Mapping[str, object],
                Mapping[str, object],
                Mapping[str, object],
            ]
        ] = []
        for index, run in enumerate(
            cast(list[dict[str, object]], checked["sample_runs"]),
            start=1,
        ):
            immediate_admission: list[dict[str, object]] = []

            def immediate_prelaunch() -> None:
                if immediate_admission:
                    _fail(
                        "CALIBRATION_CONTROLLER_ADMISSION_REUSED",
                        f"sample {index} invoked prelaunch admission more than once",
                    )
                immediate_admission.append(evaluate_now())

            observer_result, sample = _sample_executor(
                declaration=declaration,
                declaration_identity=declaration_identity,
                sample_id=run["sample_id"],
                observer_result_path=(
                    cohort_root.path / FIXED_PATHS[f"observer_result_{index}"]
                ),
                delegated_cgroup_parent=Path(
                    cast(str, checked["delegated_cgroup_parent"])
                ),
                cgroup_name=run["cgroup_name"],
                stage_disk_root=Path(cast(str, run["stage_root"])),
                timeout_seconds=float(cast(int, checked["timeout_seconds"])),
                expected_calibration_tool_identities=expected_tool_identities,
                _prelaunch_check=immediate_prelaunch,
            )
            if len(immediate_admission) != 1:
                _fail(
                    "CALIBRATION_CONTROLLER_ADMISSION_MISSING",
                    f"sample {index} did not recheck admission immediately before fork",
                )
            controller_root.write_bytes(
                f"resource-admission/sample-{index:02d}.json",
                canonical_json_bytes(immediate_admission[0]),
                mode=0o400,
            )
            checked_sample = protocol.validate_sample(
                sample,
                declaration=declaration,
                declaration_identity=declaration_identity,
            )
            sample_identity = _identity(
                cohort_root.path / FIXED_PATHS[f"sample_{index}"],
                checked_sample,
            )
            observer_results.append(dict(observer_result))
            samples.append(dict(checked_sample))
            if checked["action"] == "RUN_ONE_ACCEPTANCE":
                continue
            validation = validator_module.build_independent_validation(
                sample=checked_sample,
                sample_identity=sample_identity,
                declaration=declaration,
                declaration_identity=declaration_identity,
                validator_identity=absolute_tool_identities["primary_replayer"],
            )
            validation_identity = _identity(
                cohort_root.path / FIXED_PATHS[f"validation_{index}"],
                validation,
            )
            validations.append(dict(validation))
            accepted.append(
                (
                    checked_sample,
                    sample_identity,
                    validation,
                    validation_identity,
                )
            )
        if checked["action"] == "RUN_ONE_ACCEPTANCE":
            acceptance_receipt = _publish_one_acceptance_terminal(
                cohort_root,
                stage=stage,
                declaration=declaration,
                observer_result=observer_results[0],
                sample=samples[0],
            )
            cohort_receipt_identity = _identity(
                cohort_root.path / "receipt.json",
                acceptance_receipt,
            )
            assert controller_root is not None and plan_identity is not None
            return _publish_controller_terminal(
                controller_root,
                plan_identity=plan_identity,
                package_receipt_identity=package_receipt_identity,
                stage=stage,
                status="CLOSED_NO_LAUNCH_AUTHORITY",
                cohort_receipt_identity=cohort_receipt_identity,
                replay_contract=None,
                failure=None,
            )
        aggregate = aggregator_module.aggregate_validations_independently(
            declaration=declaration,
            declaration_identity=declaration_identity,
            accepted=accepted,
            aggregator_identity=absolute_tool_identities["aggregator"],
        )
        aggregate_identity = _identity(
            cohort_root.path / FIXED_PATHS["aggregate"],
            aggregate,
        )
        candidate = protocol.build_installed_profile_candidate(
            declaration=declaration,
            declaration_identity=declaration_identity,
            aggregate=aggregate,
            aggregate_identity=aggregate_identity,
            installed_profile=cast(dict[str, object], checked["installed_profile"]),
            candidate_builder_identity=absolute_tool_identities["runner"],
        )
        publish_calibration_cohort(
            cohort_root.path,
            declaration=declaration,
            observer_results=observer_results,
            samples=samples,
            validations=validations,
            aggregate=aggregate,
            installed_profile=cast(
                dict[str, object],
                checked["installed_profile"],
            ),
            profile_candidate=candidate,
            _existing_root=cohort_root,
            _protocol_module=protocol,
        )
        cohort_receipt_identity = _terminal_receipt_identity(
            cohort_root.path / "receipt.json"
        )
        replay_contract = {
            "alternate": {
                "expected_tool_identity": dict(
                    absolute_tool_identities["alternate_replayer"]
                ),
                "output": cast(
                    dict[str, object],
                    checked["outside_replay_outputs"],
                )["alternate"],
                "root": str(cohort_root.path),
                "slot": "replay-b",
            },
            "primary": {
                "expected_tool_identity": dict(
                    absolute_tool_identities["primary_replayer"]
                ),
                "output": cast(
                    dict[str, object],
                    checked["outside_replay_outputs"],
                )["primary"],
                "root": str(cohort_root.path),
                "slot": "replay-a",
            },
        }
        assert controller_root is not None and plan_identity is not None
        return _publish_controller_terminal(
            controller_root,
            plan_identity=plan_identity,
            package_receipt_identity=package_receipt_identity,
            stage=stage,
            status="CLOSED_NO_LAUNCH_AUTHORITY",
            cohort_receipt_identity=cohort_receipt_identity,
            replay_contract=replay_contract,
            failure=None,
        )
    except BaseException as exc:
        if cohort_root is not None:
            try:
                _close_incomplete_cohort(cohort_root, stage=stage, failure=exc)
            except BaseException as terminal_error:
                exc.add_note(
                    "calibration cohort incomplete close failed: "
                    f"{type(terminal_error).__name__}: {terminal_error}"
                )
        if controller_root is not None and plan_identity is not None:
            try:
                _publish_controller_terminal(
                    controller_root,
                    plan_identity=plan_identity,
                    package_receipt_identity=package_receipt_identity,
                    stage=stage,
                    status="INCOMPLETE_NO_AUTHORITY",
                    cohort_receipt_identity=None,
                    replay_contract=None,
                    failure={
                        "code": getattr(exc, "code", type(exc).__name__),
                        "conclusion": None,
                    },
                )
            except BaseException as terminal_error:
                exc.add_note(
                    "calibration controller incomplete close failed: "
                    f"{type(terminal_error).__name__}: {terminal_error}"
                )
        raise


def _controller_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root-fd", required=True, type=int)
    parser.add_argument("--package-root-path", required=True, type=Path)
    parser.add_argument("--package-receipt-sha256", required=True)
    parser.add_argument("--package-receipt-size", required=True, type=int)
    parser.add_argument("--package-verifier-fd", required=True, type=int)
    parser.add_argument("--package-verifier-sha256", required=True)
    parser.add_argument("--executing-runner-fd", required=True, type=int)
    parser.add_argument("--plan-fd", required=True, type=int)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--plan-size", required=True, type=int)
    parser.add_argument("--lock-fd", action="append", default=[], type=int)
    parser.add_argument("--acquire-fixed-locks", action="store_true")
    return parser


def calibration_controller_main(argv: Sequence[str] | None = None) -> int:
    arguments = _controller_parser().parse_args(argv)
    owned_descriptors = {
        arguments.package_root_fd,
        arguments.package_verifier_fd,
        arguments.executing_runner_fd,
        arguments.plan_fd,
        *arguments.lock_fd,
    }
    held_locks: Any | None = None
    result: dict[str, object] | None = None
    primary: BaseException | None = None
    try:
        expected_descriptor_count = 4 + len(arguments.lock_fd)
        if (
            len(owned_descriptors) != expected_descriptor_count
            or any(fd < 3 for fd in owned_descriptors)
        ):
            _fail(
                "CALIBRATION_CONTROLLER_FD_INVALID",
                "controller descriptors are not four unique retained FDs",
            )
        plan_raw, _plan_stat = _read_regular_fd(
            arguments.plan_fd,
            label="calibration controller plan",
            maximum_bytes=CONTROLLER_PLAN_MAX_BYTES,
        )
        if (
            len(plan_raw) != arguments.plan_size
            or hashlib.sha256(plan_raw).hexdigest() != arguments.plan_sha256
        ):
            _fail(
                "CALIBRATION_CONTROLLER_PLAN_INVALID",
                "retained plan bytes differ from their external pin",
            )
        package_receipt_identity = {
            "path": str(
                arguments.package_root_path.absolute() / TERMINAL_RECEIPT_PATH
            ),
            "sha256": arguments.package_receipt_sha256,
            "size_bytes": arguments.package_receipt_size,
        }
        plan = _strict_json_bytes(plan_raw, label="controller plan")
        (
            receipt,
            protocol,
            admission,
            validator,
            aggregator,
            expected_tools,
            absolute_tools,
        ) = (
            _verify_retained_controller_package(
                package_root_fd=arguments.package_root_fd,
                package_root_path=arguments.package_root_path,
                package_receipt_identity=package_receipt_identity,
                package_verifier_fd=arguments.package_verifier_fd,
                package_verifier_sha256=arguments.package_verifier_sha256,
                executing_runner_fd=arguments.executing_runner_fd,
            )
        )
        action = plan.get("action")
        if action in {"RUN_ONE_ACCEPTANCE", "RUN_THREE_SAMPLE_COHORT"}:
            if (
                admission is None
                or (bool(arguments.lock_fd) == arguments.acquire_fixed_locks)
                or (
                    arguments.lock_fd
                    and len(arguments.lock_fd) != len(admission.LOCK_PATHS)
                )
            ):
                _fail(
                    "CALIBRATION_CONTROLLER_ADMISSION_REQUIRED",
                    "real calibration requires exactly one package-owned fixed-lock acquisition mode",
                )
            admission_plan = plan.get("resource_admission")
            if type(admission_plan) is not dict:
                _fail(
                    "CALIBRATION_CONTROLLER_ADMISSION_REQUIRED",
                    "real calibration plan omits its admission join",
                )
            if arguments.acquire_fixed_locks:
                if (
                    admission_plan.get("lock_acquisition")
                    != "PACKAGE_PINNED_CONTROLLER_ACQUIRE"
                ):
                    _fail(
                        "CALIBRATION_CONTROLLER_ADMISSION_REQUIRED",
                        "plan and package-owned lock acquisition mode differ",
                    )
                held_locks = admission.HeldResourceLocks.acquire(
                    identity_format=admission_plan.get("lock_identity_format"),
                )
            else:
                if (
                    admission_plan.get("lock_acquisition")
                    != "RETAINED_LOCK_FD_TRANSFER"
                ):
                    _fail(
                        "CALIBRATION_CONTROLLER_ADMISSION_REQUIRED",
                        "plan and retained-lock transfer mode differ",
                    )
                for descriptor in arguments.lock_fd:
                    owned_descriptors.remove(descriptor)
                held_locks = admission.HeldResourceLocks.adopt_owned(
                    dict(
                        zip(
                            admission.LOCK_PATHS,
                            arguments.lock_fd,
                            strict=True,
                        )
                    ),
                    identity_format=admission_plan.get(
                        "lock_identity_format"
                    ),
                )
        elif arguments.lock_fd:
            _fail(
                "CALIBRATION_CONTROLLER_FD_INVALID",
                "inspect-only controller received heavy-lock descriptors",
            )
        elif arguments.acquire_fixed_locks:
            _fail(
                "CALIBRATION_CONTROLLER_FD_INVALID",
                "inspect-only controller requested heavy-lock acquisition",
            )
        result = run_calibration_controller(
            plan,
            protocol=protocol,
            package_receipt=receipt,
            package_receipt_identity=package_receipt_identity,
            expected_tool_identities=expected_tools,
            absolute_tool_identities=absolute_tools,
            resource_admission_module=admission,
            validator_module=validator,
            aggregator_module=aggregator,
            held_resource_locks=held_locks,
        )
    except BaseException as exc:
        primary = exc
    if held_locks is not None and not held_locks.released:
        try:
            held_locks.release_once()
        except BaseException as exc:
            if primary is None:
                primary = exc
            else:
                primary.add_note(
                    "calibration controller lock release failed: "
                    f"{type(exc).__name__}: {exc}"
                )
    for descriptor in sorted(owned_descriptors, reverse=True):
        try:
            os.close(descriptor)
        except OSError as exc:
            if exc.errno != 9:
                if primary is None:
                    primary = exc
                else:
                    primary.add_note(
                        "calibration controller FD close failed: "
                        f"{type(exc).__name__}: {exc}"
                    )
        except BaseException as exc:
            if primary is None:
                primary = exc
            else:
                primary.add_note(
                    "calibration controller FD close failed: "
                    f"{type(exc).__name__}: {exc}"
                )
    if primary is None:
        assert result is not None
        sys.stdout.buffer.write(canonical_json_bytes(result))
        return 0
    else:
        sys.stdout.buffer.write(
            canonical_json_bytes(
                {
                    "authority_scope": AUTHORITY_SCOPE,
                    "authorizations": dict(FALSE_AUTHORIZATIONS),
                    "code": getattr(primary, "code", type(primary).__name__),
                    "conclusion": None,
                    "status": "FAIL_CLOSED",
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(calibration_controller_main())
