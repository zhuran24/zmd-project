#!/usr/bin/env python3
"""Two-stage ordinary-user orchestrator for one prospective AB16 arm.

This file contains no import-time subprocess activity.  The public
``orchestrate_with_adapter`` entry point is adapter-driven so offline tests can
exercise the same evidence path without systemd or a solver.  A live adapter
must keep the supervisor/keeper and payload in the same selected transient
unit: after the payload is reaped, only the keeper remains while the external
observer freezes cgroup evidence; the keeper is released only after the
independent preterminal verifier returns PASS.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from types import ModuleType
from typing import Any, Protocol


PRE_RUN_SCHEMA = "noncert-cuts-ab16-organic-pre-run-authority-v1"
RUNNER_SELECTION_SCHEMA = "noncert-cuts-ab16-organic-arm-selection-v1"
DRILL_SELECTION_SCHEMA = "noncert-cuts-ab16-organic-drill-selection-v1"
LAUNCH_ENVIRONMENT_SCHEMA = "noncert-cuts-ab16-launch-environment-v1"
LAUNCH_ENVIRONMENT_KEYS = frozenset(
    {
        "DBUS_SESSION_BUS_ADDRESS",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "PYTHONHASHSEED",
        "TZ",
        "XDG_RUNTIME_DIR",
    }
)
MAX_TOOL_BYTES = 8 * 1024 * 1024
MAX_EXECUTABLE_BYTES = 64 * 1024 * 1024


class OrchestratorError(RuntimeError):
    """Authority, lifecycle, or adapter observation failed closed."""


@dataclass(frozen=True)
class ByteSnapshot:
    """One stable same-FD snapshot."""

    raw: bytes
    identity: dict[str, object]


@dataclass(frozen=True)
class LaunchEvidence:
    """Inner-unit evidence once payload is reaped and keeper is ready."""

    invocation_id: str
    supervisor_pid: int
    supervisor_starttime: int
    payload_pid: int
    payload_starttime: int
    payload_seal_monotonic_ns: int
    payload_exit_monotonic_ns: int
    payload_exit_code: int
    payload_signal: int
    payload_reaped: bool
    keeper_ready_monotonic_ns: int


@dataclass(frozen=True)
class PreterminalEvidence:
    """External observation while the keeper preserves the cgroup."""

    captured_at_monotonic_ns: int
    systemd_raw: Mapping[str, str]
    cgroup_raw: Mapping[str, str]
    payload_current_starttime: int | None
    keeper_current_starttime: int


@dataclass(frozen=True)
class TerminalEvidence:
    """External terminal metadata after keeper release."""

    captured_at_monotonic_ns: int
    systemd_raw: Mapping[str, str]


@dataclass(frozen=True)
class CleanupEvidence:
    """Independent absence checks after the unit has reached terminal state."""

    captured_at_monotonic_ns: int
    payload_current_starttime: int | None
    keeper_current_starttime: int | None
    cgroup_path: str
    cgroup_path_exists: bool
    unit_load_state: str
    matching_unit_names: Sequence[str]


@dataclass(frozen=True)
class EpochCapture:
    """One complete package-pinned live epoch and its raw transcript."""

    manager_epoch: Mapping[str, Any]
    transcript: Mapping[str, Any]


class LifecycleAdapter(Protocol):
    """Ordinary-user launch/observer seam used by live and fixture adapters."""

    def observe_manager_epoch(self, phase: str) -> EpochCapture:
        """Independently observe the current user-manager/boot epoch."""

    def monotonic_ns(self) -> int:
        """Return the observer's monotonic timestamp."""

    def launch_and_wait_for_keeper(
        self,
        *,
        unit_name: str,
        systemd_run_argv: Sequence[str],
        payload_argv: Sequence[str],
    ) -> LaunchEvidence:
        """Launch one unit and return only after its payload is reaped."""

    def capture_preterminal(
        self,
        *,
        unit_name: str,
        launch: LaunchEvidence,
    ) -> PreterminalEvidence:
        """Capture raw systemd/cgroup state while only the keeper remains."""

    def release_keeper(
        self,
        *,
        unit_name: str,
        release_path: Path,
        launch: LaunchEvidence,
    ) -> None:
        """Release the keeper after the immutable release token exists."""

    def capture_terminal(
        self,
        *,
        unit_name: str,
        invocation_id: str,
    ) -> TerminalEvidence:
        """Wait for and capture the same InvocationID's terminal metadata."""

    def capture_cleanup(
        self,
        *,
        unit_name: str,
        launch: LaunchEvidence,
        control_group: str,
    ) -> CleanupEvidence:
        """Prove no residual pid, cgroup, or unit remains."""

    def abort_and_capture_cleanup(
        self,
        *,
        unit_name: str,
        launch: LaunchEvidence,
        control_group: str | None,
    ) -> CleanupEvidence:
        """Stop only the selected InvocationID and prove no residual state."""


SYSTEMD_PRETERMINAL_FIELDS = (
    "ActiveState",
    "CollectMode",
    "SubState",
    "MainPID",
    "ControlGroup",
    "InvocationID",
    "MemoryHigh",
    "MemoryMax",
    "MemorySwapMax",
    "OOMPolicy",
    "KillMode",
    "SendSIGKILL",
    "RuntimeMaxUSec",
)
SYSTEMD_TERMINAL_FIELDS = (
    "ActiveState",
    "SubState",
    "ControlGroup",
    "InvocationID",
    "Result",
    "ExecMainCode",
    "ExecMainStatus",
)
CGROUP_FIELDS = (
    "memory.high",
    "memory.max",
    "memory.swap.max",
    "memory.current",
    "memory.peak",
    "memory.swap.current",
    "memory.events",
    "cgroup.procs",
    "cgroup.events",
)


def _strict_json(value: object, label: str = "value") -> None:
    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise OrchestratorError(f"{label} contains a non-finite float")
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _strict_json(item, f"{label}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise OrchestratorError(f"{label} contains a non-string key")
            _strict_json(item, f"{label}.{key}")
        return
    raise OrchestratorError(f"{label} is not strict JSON")


def canonical_json_bytes(value: object) -> bytes:
    _strict_json(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _open_directory_fd(path: Path) -> tuple[Path, int]:
    absolute = Path(os.path.abspath(path))
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute.anchor, flags)
    except OSError as exc:
        raise OrchestratorError("symlink or invalid path root") from exc
    try:
        for component in absolute.parts[1:]:
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return absolute, descriptor
    except OSError as exc:
        os.close(descriptor)
        raise OrchestratorError("symlink or invalid path component") from exc


def _open_regular(path: Path | str) -> tuple[Path, int]:
    absolute = Path(os.path.abspath(path))
    if absolute == Path(absolute.anchor):
        raise OrchestratorError("file path may not be the filesystem root")
    _parent, parent_descriptor = _open_directory_fd(absolute.parent)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute.name, flags, dir_fd=parent_descriptor)
    except OSError as exc:
        os.close(parent_descriptor)
        raise OrchestratorError("symlink or invalid file path") from exc
    os.close(parent_descriptor)
    return absolute, descriptor


def _stat_signature(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _hash_open_executable(
    descriptor: int,
    *,
    absolute: Path,
) -> tuple[dict[str, object], tuple[int, ...]]:
    """Hash one executable through the descriptor later passed to exec."""

    before = os.fstat(descriptor)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_EXECUTABLE_BYTES:
        raise OrchestratorError(f"invalid pinned executable: {absolute}")
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    after = os.fstat(descriptor)
    if _stat_signature(before) != _stat_signature(after) or size != after.st_size:
        raise OrchestratorError(f"pinned executable changed during same-FD hash: {absolute}")
    return (
        {
            "mode": stat.S_IMODE(after.st_mode),
            "path": str(absolute),
            "sha256": digest.hexdigest(),
            "size_bytes": size,
        },
        _stat_signature(after),
    )


def snapshot_bytes(path: Path | str) -> ByteSnapshot:
    """Read/hash one singly linked regular file through one stable FD."""

    absolute, descriptor = _open_regular(path)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_TOOL_BYTES * 8:
            raise OrchestratorError(f"invalid authority file: {absolute}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)

        def signature(item: os.stat_result) -> tuple[int, ...]:
            return (
                item.st_dev,
                item.st_ino,
                item.st_mode,
                item.st_nlink,
                item.st_size,
                item.st_mtime_ns,
                item.st_ctime_ns,
            )

        if signature(before) != signature(after):
            raise OrchestratorError(f"file changed during same-FD read: {absolute}")
        raw = b"".join(chunks)
        if len(raw) != after.st_size:
            raise OrchestratorError(f"short same-FD read: {absolute}")
        return ByteSnapshot(
            raw=raw,
            identity={
                "mode": stat.S_IMODE(after.st_mode),
                "path": str(absolute),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            },
        )
    finally:
        os.close(descriptor)


def _strict_load(snapshot: ByteSnapshot, label: str) -> Mapping[str, Any]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise OrchestratorError(f"{label} has duplicate JSON key {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            snapshot.raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(
                OrchestratorError(f"{label} has invalid constant {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OrchestratorError(f"{label} is malformed JSON") from exc
    if type(value) is not dict or canonical_json_bytes(value) != snapshot.raw:
        raise OrchestratorError(f"{label} is not canonical JSON")
    return value


def _load_pinned_environment(pre_run: Mapping[str, Any]) -> dict[str, str]:
    launch = pre_run.get("launch")
    if type(launch) is not dict:
        raise OrchestratorError("pre-run launch is absent")
    identity = launch.get("environment_identity")
    if type(identity) is not dict:
        raise OrchestratorError("launch environment identity is absent")
    snapshot = snapshot_bytes(identity.get("path", ""))
    _identity_matches(snapshot.identity, identity, "launch environment")
    record = _strict_load(snapshot, "launch environment")
    if (
        set(record) != {"clear_ambient", "schema_version", "variables"}
        or record.get("schema_version") != LAUNCH_ENVIRONMENT_SCHEMA
        or record.get("clear_ambient") is not True
        or type(record.get("variables")) is not dict
        or set(record["variables"]) != LAUNCH_ENVIRONMENT_KEYS
    ):
        raise OrchestratorError("launch environment schema drifted")
    result: dict[str, str] = {}
    for name, item in record["variables"].items():
        if type(item) is not str or not item or any(character in item for character in ("\x00", "\n", "\r")):
            raise OrchestratorError(f"launch environment {name} is invalid")
        result[name] = item
    for name in ("HOME", "XDG_RUNTIME_DIR"):
        if not Path(result[name]).is_absolute():
            raise OrchestratorError(f"launch environment {name} is not absolute")
    if any(not Path(item).is_absolute() for item in result["PATH"].split(":")):
        raise OrchestratorError("launch environment PATH is not absolute")
    if (
        result["LANG"] != "C.UTF-8"
        or result["LC_ALL"] != "C.UTF-8"
        or result["PYTHONHASHSEED"] != "0"
        or result["TZ"] != "UTC"
        or not result["DBUS_SESSION_BUS_ADDRESS"].startswith("unix:path=/")
    ):
        raise OrchestratorError("launch environment fixed values drifted")
    return result


def _identity_matches(
    observed: Mapping[str, Any],
    expected: Mapping[str, Any],
    label: str,
) -> None:
    if dict(observed) != dict(expected):
        raise OrchestratorError(f"{label} byte identity drifted")


def _load_pinned_module(
    identity: Mapping[str, Any],
    *,
    module_name: str,
) -> ModuleType:
    """Compile/exec exactly the same-FD bytes named by a package identity."""

    snapshot = snapshot_bytes(Path(str(identity["path"])))
    _identity_matches(snapshot.identity, identity, module_name)
    if len(snapshot.raw) > MAX_TOOL_BYTES:
        raise OrchestratorError(f"{module_name} exceeds tool byte cap")
    module = ModuleType(module_name)
    module.__file__ = str(identity["path"])
    sys.modules[module_name] = module
    try:
        code = compile(snapshot.raw, str(identity["path"]), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _attempt_allowlist(attempt_dir: Path) -> None:
    _absolute, descriptor = _open_directory_fd(attempt_dir)
    observed: set[str] = set()
    try:
        with os.scandir(descriptor) as entries:
            for entry in entries:
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                    raise OrchestratorError("prelaunch attempt entry is not a regular file")
                metadata = entry.stat(follow_symlinks=False)
                if metadata.st_nlink != 1:
                    raise OrchestratorError("prelaunch attempt entry is multiply linked")
                observed.add(entry.name)
    finally:
        os.close(descriptor)
    if observed != {"pre-run-authority.json", "selection.json"}:
        raise OrchestratorError("prelaunch attempt-directory allowlist drifted")


def _proc_starttime(pid: int) -> int | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except (FileNotFoundError, ProcessLookupError):
        return None
    close = raw.rfind(")")
    if close < 0:
        raise OrchestratorError("malformed proc stat comm field")
    fields = raw[close + 2 :].split()
    if len(fields) <= 19:
        raise OrchestratorError("truncated proc stat")
    try:
        return int(fields[19])
    except ValueError as exc:
        raise OrchestratorError("invalid proc starttime") from exc


def build_pinned_epoch_observer(
    pre_run: Mapping[str, Any],
) -> Callable[[str], EpochCapture]:
    """Build the sole formal/drill epoch callback from package-pinned bytes."""

    tools = pre_run.get("tool_identities")
    if type(tools) is not dict:
        raise OrchestratorError("pre-run tool identity map is absent")
    authority = _load_pinned_module(
        tools["manager_epoch_authority"],
        module_name=f"_ab16_epoch_authority_{tools['manager_epoch_authority']['sha256'][:12]}",
    )
    pinned_environment = _load_pinned_environment(pre_run)

    def observe(phase: str) -> EpochCapture:
        if phase not in {
            "launch",
            "preterminal",
            "release",
            "terminal",
            "cleanup",
            "detached-replay",
        }:
            raise OrchestratorError("unsupported manager epoch phase")
        previous_environment = os.environ.copy()
        os.environ.clear()
        os.environ.update(pinned_environment)
        try:
            captured = authority.capture_manager_epoch_with_transcript(
                attestor_path=tools["manager_attestor"]["path"],
                busctl_path=tools["busctl"]["path"],
                python_path=tools["python3_13"]["path"],
                sudo_path=tools["sudo"]["path"],
            )
        finally:
            os.environ.clear()
            os.environ.update(previous_environment)
        if type(captured) is not dict or set(captured) != {
            "manager_epoch",
            "transcript",
        }:
            raise OrchestratorError("manager epoch capture shape drifted")
        authority.validate_manager_epoch(captured["manager_epoch"])
        authority.validate_manager_epoch_capture_transcript(
            captured["transcript"],
            expected_epoch=captured["manager_epoch"],
        )
        if captured["manager_epoch"] != pre_run["manager_epoch"]:
            raise OrchestratorError("live manager/boot epoch drifted")
        rounds = captured["transcript"].get("rounds")
        if type(rounds) is not list or len(rounds) != 2:
            raise OrchestratorError("manager epoch transcript round count drifted")
        expected_roles = {
            "busctl": ("observation_toolchain", "busctl"),
            "manager_attestor": ("attestation_toolchain", "attestor"),
            "python3_13": ("attestation_toolchain", "python"),
            "sudo": ("attestation_toolchain", "sudo"),
        }
        for round_record in rounds:
            for role, (group, member) in expected_roles.items():
                observed = round_record[group][member]
                expected = tools[role]
                if any(observed.get(field) != expected[field] for field in expected):
                    raise OrchestratorError(f"manager epoch transcript {role} identity drifted")
        return EpochCapture(
            manager_epoch=captured["manager_epoch"],
            transcript=captured["transcript"],
        )

    return observe


class SubprocessLifecycleAdapter:
    """Ordinary-user systemd/cgroup implementation for the live path."""

    def __init__(
        self,
        *,
        pre_run: Mapping[str, Any],
        epoch_observer: Callable[[str], EpochCapture],
        run: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
        monotonic: Callable[[], float] = time.monotonic,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.pre_run = pre_run
        self.epoch_observer = epoch_observer
        self.run = run
        self._monotonic = monotonic
        self._monotonic_ns = monotonic_ns
        self.sleep = sleep
        self.systemctl = str(pre_run["launch"]["systemctl_path"])
        self.environment = _load_pinned_environment(pre_run)
        tools = pre_run.get("tool_identities")
        if type(tools) is not dict:
            raise OrchestratorError("pre-run tool identities are absent")
        self.executable_identities: dict[
            str,
            tuple[str, Mapping[str, Any]],
        ] = {}
        for role in ("systemctl", "systemd_run"):
            identity = tools.get(role)
            if type(identity) is not dict or type(identity.get("path")) is not str:
                raise OrchestratorError(f"pre-run {role} identity is invalid")
            if identity["path"] in self.executable_identities:
                raise OrchestratorError("pinned system-tool paths must be distinct")
            self.executable_identities[identity["path"]] = (role, identity)

    def observe_manager_epoch(self, phase: str) -> EpochCapture:
        observed = self.epoch_observer(phase)
        if not isinstance(observed, EpochCapture):
            raise OrchestratorError("epoch observer returned wrong capture type")
        return observed

    def monotonic_ns(self) -> int:
        return self._monotonic_ns()

    def _run(
        self,
        argv: Sequence[str],
        *,
        timeout: float,
        allowed_exit_codes: frozenset[int] = frozenset({0}),
    ) -> subprocess.CompletedProcess[bytes]:
        command = list(argv)
        if not command or command[0] not in self.executable_identities:
            raise OrchestratorError("ordinary-user executable is not package-pinned")
        role, expected = self.executable_identities[command[0]]
        parent, parent_descriptor = _open_directory_fd(Path(command[0]).parent)
        absolute = parent / Path(command[0]).name
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(
                absolute.name,
                flags,
                dir_fd=parent_descriptor,
            )
        except OSError as exc:
            os.close(parent_descriptor)
            raise OrchestratorError("pinned executable path is invalid or symlinked") from exc
        try:
            observed, before_signature = _hash_open_executable(
                descriptor,
                absolute=absolute,
            )
            _identity_matches(observed, expected, "ordinary-user executable")
            exec_command = command.copy()
            exec_command[0] = {
                "systemctl": "systemctl",
                "systemd_run": "systemd-run",
            }[role]
            completed = self.run(
                exec_command,
                check=False,
                close_fds=True,
                cwd=self.pre_run["launch"]["cwd"],
                env=dict(self.environment),
                executable=f"/proc/self/fd/{descriptor}",
                pass_fds=(descriptor,),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
            try:
                current_path = os.stat(
                    absolute.name,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
            except OSError as exc:
                raise OrchestratorError("pinned executable path changed during execution") from exc
            if (
                not stat.S_ISREG(current_path.st_mode)
                or current_path.st_dev != before_signature[0]
                or current_path.st_ino != before_signature[1]
            ):
                raise OrchestratorError("pinned executable path changed during execution")
            post_observed, after_signature = _hash_open_executable(
                descriptor,
                absolute=absolute,
            )
            if before_signature != after_signature or post_observed != observed:
                raise OrchestratorError("pinned executable bytes or metadata changed during execution")
        finally:
            os.close(descriptor)
            os.close(parent_descriptor)
        if completed.returncode not in allowed_exit_codes:
            raise OrchestratorError(f"ordinary-user command failed ({completed.returncode}): {argv[0]}")
        return completed

    @staticmethod
    def _parse_show(raw: bytes, fields: Sequence[str]) -> dict[str, str]:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise OrchestratorError("systemctl show output is not UTF-8") from exc
        result: dict[str, str] = {}
        for line in text.splitlines():
            key, separator, value = line.partition("=")
            if not separator or key in result:
                raise OrchestratorError("systemctl show output malformed/duplicated")
            result[key] = value
        if set(result) != set(fields):
            raise OrchestratorError("systemctl show field set drifted")
        return result

    def _show(self, unit_name: str, fields: Sequence[str]) -> dict[str, str]:
        argv = [self.systemctl, "--user", "show", unit_name]
        argv.extend(f"--property={field}" for field in fields)
        completed = self._run(argv, timeout=15)
        return self._parse_show(completed.stdout, fields)

    @staticmethod
    def _read_cgroup_file(control_group: str, name: str) -> str:
        if not control_group.startswith("/"):
            raise OrchestratorError("ControlGroup is not absolute")
        parts = Path(control_group).parts[1:]
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise OrchestratorError("ControlGroup path is unsafe")
        path = Path("/sys/fs/cgroup").joinpath(*parts, name)
        absolute, descriptor = _open_regular(path)
        try:
            before = os.fstat(descriptor)
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(descriptor)
            if (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            ):
                raise OrchestratorError(f"cgroup file changed during read: {name}")
            try:
                return b"".join(chunks).decode("ascii").rstrip("\n")
            except UnicodeDecodeError as exc:
                raise OrchestratorError(f"cgroup file is not ASCII: {name}") from exc
        finally:
            os.close(descriptor)

    def launch_and_wait_for_keeper(
        self,
        *,
        unit_name: str,
        systemd_run_argv: Sequence[str],
        payload_argv: Sequence[str],
    ) -> LaunchEvidence:
        if os.geteuid() != os.getuid() or os.geteuid() == 0:
            raise OrchestratorError("live adapter must run as the ordinary selected user")
        if list(payload_argv) != self.pre_run["launch"]["payload_argv"]:
            raise OrchestratorError("live payload argv drifted")
        self._run(systemd_run_argv, timeout=30)
        inner_path = Path(self.pre_run["output_paths"]["inner"])
        deadline = self._monotonic() + int(self.pre_run["resource_contract"]["runtime_max_seconds"]) - 60
        while self._monotonic() <= deadline:
            if os.path.lexists(inner_path):
                snapshot = snapshot_bytes(inner_path)
                value = _strict_load(snapshot, "inner lifecycle")
                if (
                    value.get("schema_version") != "noncert-cuts-ab16-inner-lifecycle-v1"
                    or value.get("unit_name") != unit_name
                ):
                    raise OrchestratorError("live inner lifecycle schema/unit drifted")
                return LaunchEvidence(
                    invocation_id=value["invocation_id"],
                    supervisor_pid=value["supervisor_pid"],
                    supervisor_starttime=value["supervisor_starttime"],
                    payload_pid=value["payload_pid"],
                    payload_starttime=value["payload_starttime"],
                    payload_seal_monotonic_ns=value["payload_seal_monotonic_ns"],
                    payload_exit_monotonic_ns=value["payload_exit_monotonic_ns"],
                    payload_exit_code=value["payload_exit_code"],
                    payload_signal=value["payload_signal"],
                    payload_reaped=value["payload_reaped"],
                    keeper_ready_monotonic_ns=value["keeper_ready_monotonic_ns"],
                )
            self.sleep(0.05)
        raise OrchestratorError("inner lifecycle did not appear before internal deadline")

    def capture_preterminal(
        self,
        *,
        unit_name: str,
        launch: LaunchEvidence,
    ) -> PreterminalEvidence:
        systemd_raw = self._show(unit_name, SYSTEMD_PRETERMINAL_FIELDS)
        control_group = systemd_raw["ControlGroup"]
        cgroup_raw = {name: self._read_cgroup_file(control_group, name) for name in CGROUP_FIELDS}
        return PreterminalEvidence(
            captured_at_monotonic_ns=self._monotonic_ns(),
            systemd_raw=systemd_raw,
            cgroup_raw=cgroup_raw,
            payload_current_starttime=_proc_starttime(launch.payload_pid),
            keeper_current_starttime=_proc_starttime(launch.supervisor_pid) or 0,
        )

    def release_keeper(
        self,
        *,
        unit_name: str,
        release_path: Path,
        launch: LaunchEvidence,
    ) -> None:
        del unit_name, launch
        snapshot_bytes(release_path)

    def capture_terminal(
        self,
        *,
        unit_name: str,
        invocation_id: str,
    ) -> TerminalEvidence:
        deadline = self._monotonic() + 30
        while self._monotonic() <= deadline:
            raw = self._show(unit_name, SYSTEMD_TERMINAL_FIELDS)
            if raw["InvocationID"] != invocation_id:
                raise OrchestratorError("terminal InvocationID drifted")
            if raw["ActiveState"] in {"inactive", "failed"}:
                return TerminalEvidence(
                    captured_at_monotonic_ns=self._monotonic_ns(),
                    systemd_raw=raw,
                )
            self.sleep(0.05)
        raise OrchestratorError("unit did not reach terminal state")

    def capture_cleanup(
        self,
        *,
        unit_name: str,
        launch: LaunchEvidence,
        control_group: str,
    ) -> CleanupEvidence:
        return self._cleanup_selected_unit(
            unit_name=unit_name,
            launch=launch,
            control_group=control_group,
        )

    def abort_and_capture_cleanup(
        self,
        *,
        unit_name: str,
        launch: LaunchEvidence,
        control_group: str | None,
    ) -> CleanupEvidence:
        return self._cleanup_selected_unit(
            unit_name=unit_name,
            launch=launch,
            control_group=control_group or "",
        )

    def _selected_unit_state(
        self,
        *,
        unit_name: str,
        expected_invocation_id: str,
    ) -> tuple[bool, str]:
        shown = self._run(
            [
                self.systemctl,
                "--user",
                "show",
                unit_name,
                "--property=InvocationID",
                "--property=ControlGroup",
            ],
            timeout=15,
            allowed_exit_codes=frozenset({0, 1, 4, 5}),
        )
        if not shown.stdout:
            return False, ""
        state = self._parse_show(
            shown.stdout,
            ("InvocationID", "ControlGroup"),
        )
        observed_invocation = state["InvocationID"]
        if observed_invocation and observed_invocation != expected_invocation_id:
            raise OrchestratorError("refusing cleanup of reused unit with different InvocationID")
        return bool(observed_invocation), state["ControlGroup"]

    def _cleanup_selected_unit(
        self,
        *,
        unit_name: str,
        launch: LaunchEvidence,
        control_group: str,
    ) -> CleanupEvidence:
        present, observed_control_group = self._selected_unit_state(
            unit_name=unit_name,
            expected_invocation_id=launch.invocation_id,
        )
        if control_group and observed_control_group and control_group != observed_control_group:
            raise OrchestratorError("selected unit ControlGroup drifted before cleanup")
        effective_control_group = control_group or observed_control_group
        if present and (not effective_control_group or not effective_control_group.startswith("/")):
            raise OrchestratorError("selected unit ControlGroup unavailable before cleanup")
        if present:
            self._run(
                [self.systemctl, "--user", "stop", unit_name],
                timeout=15,
                allowed_exit_codes=frozenset({0, 5}),
            )
            self._run(
                [self.systemctl, "--user", "reset-failed", unit_name],
                timeout=15,
                allowed_exit_codes=frozenset({0, 1, 5}),
            )
        deadline = self._monotonic() + 30
        while self._monotonic() <= deadline:
            load = self._run(
                [
                    self.systemctl,
                    "--user",
                    "show",
                    unit_name,
                    "--property=LoadState",
                    "--value",
                ],
                timeout=15,
                allowed_exit_codes=frozenset({0, 1, 4, 5}),
            )
            unit_load_state = load.stdout.decode("utf-8").strip() or "not-found"
            listed = self._run(
                [
                    self.systemctl,
                    "--user",
                    "list-units",
                    "--all",
                    "--plain",
                    "--no-legend",
                    unit_name,
                ],
                timeout=15,
            )
            matching = [line.split()[0] for line in listed.stdout.decode("utf-8").splitlines() if line.split()]
            cgroup_path = (
                Path("/sys/fs/cgroup").joinpath(*Path(effective_control_group).parts[1:])
                if effective_control_group
                else None
            )
            evidence = CleanupEvidence(
                captured_at_monotonic_ns=self._monotonic_ns(),
                payload_current_starttime=_proc_starttime(launch.payload_pid),
                keeper_current_starttime=_proc_starttime(launch.supervisor_pid),
                cgroup_path=effective_control_group,
                cgroup_path_exists=(cgroup_path.exists() if cgroup_path is not None else False),
                unit_load_state=unit_load_state,
                matching_unit_names=matching,
            )
            if (
                evidence.payload_current_starttime is None
                and evidence.keeper_current_starttime is None
                and evidence.cgroup_path_exists is False
                and evidence.unit_load_state == "not-found"
                and not evidence.matching_unit_names
            ):
                return evidence
            self.sleep(0.05)
        raise OrchestratorError("selected unit cleanup did not reach absence")


def _write_epoch(
    *,
    lifecycle: ModuleType,
    pre_run: Mapping[str, Any],
    adapter: LifecycleAdapter,
    phase: str,
) -> tuple[Mapping[str, Any], dict[str, object]]:
    capture = adapter.observe_manager_epoch(phase)
    transcript_path = Path(pre_run["epoch_transcript_paths"][phase])
    transcript_identity = lifecycle.write_json_exclusive(
        transcript_path,
        capture.transcript,
    )
    observation = lifecycle.build_epoch_observation(
        phase=phase,
        slot=pre_run["slot"],
        observed_epoch=capture.manager_epoch,
        observed_at_monotonic_ns=adapter.monotonic_ns(),
        capture_transcript_identity=transcript_identity,
    )
    output = Path(pre_run["epoch_observation_paths"][phase])
    identity = lifecycle.write_json_exclusive(output, observation)
    return observation, identity


def _orchestrate_with_adapter_unprotected(
    *,
    pre_run_path: Path | str,
    selection_path: Path | str,
    adapter: LifecycleAdapter,
    cleanup_state: dict[str, Any],
) -> dict[str, object]:
    """Execute and independently replay one selected two-stage arm.

    The caller is responsible for owning the campaign locks.  This function
    consumes the selected arm on any post-selection exception; it never retries.
    """

    pre_run_snapshot = snapshot_bytes(pre_run_path)
    selection_snapshot = snapshot_bytes(selection_path)
    pre_run = _strict_load(pre_run_snapshot, "pre-run authority")
    selection = _strict_load(selection_snapshot, "runner selection")
    cleanup_state.update(
        {
            "pre_run": pre_run,
            "pre_run_identity": pre_run_snapshot.identity,
            "selection": selection,
            "selection_identity": selection_snapshot.identity,
        }
    )
    if pre_run.get("schema_version") != PRE_RUN_SCHEMA or selection.get("schema_version") not in {
        RUNNER_SELECTION_SCHEMA,
        DRILL_SELECTION_SCHEMA,
    }:
        raise OrchestratorError("pre-run/selection schema mismatch")
    tool_identities = pre_run.get("tool_identities")
    if type(tool_identities) is not dict:
        raise OrchestratorError("pre-run lacks tool identities")
    lifecycle = _load_pinned_module(
        tool_identities["organic_resource_lifecycle"],
        module_name=f"_ab16_lifecycle_{pre_run_snapshot.identity['sha256'][:12]}",
    )
    cleanup_state["lifecycle"] = lifecycle
    verifier = _load_pinned_module(
        tool_identities["organic_resource_verifier"],
        module_name=f"_ab16_resource_verifier_{pre_run_snapshot.identity['sha256'][:12]}",
    )
    current = snapshot_bytes(Path(__file__))
    _identity_matches(
        current.identity,
        tool_identities["organic_unit_orchestrator"],
        "organic unit orchestrator",
    )
    lifecycle.validate_pre_run_authority(pre_run)
    lifecycle.validate_runner_selection(
        selection,
        pre_run_authority=pre_run,
        pre_run_authority_identity=pre_run_snapshot.identity,
    )
    _attempt_allowlist(Path(pre_run["attempt_dir"]))
    launch_observation, _launch_epoch_identity = _write_epoch(
        lifecycle=lifecycle,
        pre_run=pre_run,
        adapter=adapter,
        phase="launch",
    )
    systemd_argv = lifecycle.build_systemd_run_argv(
        systemd_run_path=pre_run["launch"]["systemd_run_path"],
        unit_name=pre_run["unit_name"],
        supervisor_argv=pre_run["launch"]["supervisor_argv"],
        resource_contract=pre_run["resource_contract"],
        execution_class=pre_run["execution_class"],
    )
    launch = adapter.launch_and_wait_for_keeper(
        unit_name=pre_run["unit_name"],
        systemd_run_argv=systemd_argv,
        payload_argv=pre_run["launch"]["payload_argv"],
    )
    cleanup_state["launch"] = launch
    payload_result = verifier.snapshot_json(pre_run["output_paths"]["attempt_result"])
    inner_snapshot = verifier.snapshot_json(pre_run["output_paths"]["inner"])
    inner = inner_snapshot.value
    observed_launch = {
        "invocation_id": launch.invocation_id,
        "keeper_pid": launch.supervisor_pid,
        "keeper_ready_monotonic_ns": launch.keeper_ready_monotonic_ns,
        "keeper_starttime": launch.supervisor_starttime,
        "payload_exit_code": launch.payload_exit_code,
        "payload_exit_monotonic_ns": launch.payload_exit_monotonic_ns,
        "payload_pid": launch.payload_pid,
        "payload_reaped": launch.payload_reaped,
        "payload_seal_monotonic_ns": launch.payload_seal_monotonic_ns,
        "payload_signal": launch.payload_signal,
        "payload_starttime": launch.payload_starttime,
        "supervisor_pid": launch.supervisor_pid,
        "supervisor_starttime": launch.supervisor_starttime,
    }
    if any(inner.get(field) != value for field, value in observed_launch.items()):
        raise OrchestratorError("adapter launch evidence differs from supervisor inner bytes")
    if (
        inner.get("manager_epoch_observation") != launch_observation
        or inner.get("payload_result_identity") != payload_result.identity
    ):
        raise OrchestratorError("supervisor inner authority/result join failed")
    inner_identity = inner_snapshot.identity
    preterminal_observation, _preterminal_epoch_identity = _write_epoch(
        lifecycle=lifecycle,
        pre_run=pre_run,
        adapter=adapter,
        phase="preterminal",
    )
    observed_preterminal = adapter.capture_preterminal(
        unit_name=pre_run["unit_name"],
        launch=launch,
    )
    cleanup_state["control_group"] = observed_preterminal.systemd_raw.get("ControlGroup")
    preterminal = lifecycle.build_preterminal_record(
        pre_run,
        pre_run_snapshot.identity,
        selection,
        selection_snapshot.identity,
        inner_identity,
        invocation_id=launch.invocation_id,
        preterminal_observation=preterminal_observation,
        observed_at_monotonic_ns=observed_preterminal.captured_at_monotonic_ns,
        systemd_raw=observed_preterminal.systemd_raw,
        cgroup_raw=observed_preterminal.cgroup_raw,
        payload_current_starttime=observed_preterminal.payload_current_starttime,
        keeper_current_starttime=observed_preterminal.keeper_current_starttime,
    )
    lifecycle.write_json_exclusive(
        Path(pre_run["output_paths"]["preterminal"]),
        preterminal,
    )
    resource_receipt = verifier.verify_preterminal_paths(
        pre_run_path=pre_run_path,
        selection_path=selection_path,
        inner_path=pre_run["output_paths"]["inner"],
        preterminal_path=pre_run["output_paths"]["preterminal"],
        payload_result_path=pre_run["output_paths"]["attempt_result"],
        output_path=pre_run["output_paths"]["resource_verification"],
    )
    resource_identity = verifier.snapshot_json(pre_run["output_paths"]["resource_verification"]).identity
    if resource_receipt.get("status") != "PASS":
        raise OrchestratorError("independent preterminal verifier did not PASS")
    release_observation, _release_epoch_identity = _write_epoch(
        lifecycle=lifecycle,
        pre_run=pre_run,
        adapter=adapter,
        phase="release",
    )
    preterminal_identity = verifier.snapshot_json(pre_run["output_paths"]["preterminal"]).identity
    release = lifecycle.build_release_record(
        pre_run,
        pre_run_snapshot.identity,
        selection,
        selection_snapshot.identity,
        invocation_id=launch.invocation_id,
        release_observation=release_observation,
        preterminal_identity=preterminal_identity,
        resource_verification_identity=resource_identity,
        keeper_pid=launch.supervisor_pid,
        keeper_starttime=launch.supervisor_starttime,
        release_monotonic_ns=adapter.monotonic_ns(),
    )
    release_path = Path(pre_run["output_paths"]["release"])
    release_identity = lifecycle.write_json_exclusive(release_path, release)
    adapter.release_keeper(
        unit_name=pre_run["unit_name"],
        release_path=release_path,
        launch=launch,
    )
    terminal_observation, _terminal_epoch_identity = _write_epoch(
        lifecycle=lifecycle,
        pre_run=pre_run,
        adapter=adapter,
        phase="terminal",
    )
    observed_terminal = adapter.capture_terminal(
        unit_name=pre_run["unit_name"],
        invocation_id=launch.invocation_id,
    )
    terminal = lifecycle.build_terminal_record(
        pre_run,
        pre_run_snapshot.identity,
        selection,
        selection_snapshot.identity,
        release_identity,
        invocation_id=launch.invocation_id,
        terminal_observation=terminal_observation,
        captured_at_monotonic_ns=observed_terminal.captured_at_monotonic_ns,
        systemd_raw=observed_terminal.systemd_raw,
    )
    terminal_identity = lifecycle.write_json_exclusive(
        Path(pre_run["output_paths"]["terminal"]),
        terminal,
    )
    cleanup_observation, _cleanup_epoch_identity = _write_epoch(
        lifecycle=lifecycle,
        pre_run=pre_run,
        adapter=adapter,
        phase="cleanup",
    )
    control_group = resource_receipt["derived"]["control_group"]
    cleanup_state["control_group"] = control_group
    observed_cleanup = adapter.capture_cleanup(
        unit_name=pre_run["unit_name"],
        launch=launch,
        control_group=control_group,
    )
    cleanup = lifecycle.build_cleanup_record(
        pre_run,
        pre_run_snapshot.identity,
        selection,
        selection_snapshot.identity,
        terminal_identity,
        invocation_id=launch.invocation_id,
        cleanup_observation=cleanup_observation,
        captured_at_monotonic_ns=observed_cleanup.captured_at_monotonic_ns,
        payload_pid=launch.payload_pid,
        payload_current_starttime=observed_cleanup.payload_current_starttime,
        keeper_pid=launch.supervisor_pid,
        keeper_current_starttime=observed_cleanup.keeper_current_starttime,
        cgroup_path=observed_cleanup.cgroup_path,
        cgroup_path_exists=observed_cleanup.cgroup_path_exists,
        unit_load_state=observed_cleanup.unit_load_state,
        matching_unit_names=observed_cleanup.matching_unit_names,
    )
    lifecycle.write_json_exclusive(
        Path(pre_run["output_paths"]["cleanup"]),
        cleanup,
    )
    _detached_observation, _detached_epoch_identity = _write_epoch(
        lifecycle=lifecycle,
        pre_run=pre_run,
        adapter=adapter,
        phase="detached-replay",
    )
    detached = verifier.verify_detached_paths(
        pre_run_path=pre_run_path,
        selection_path=selection_path,
        inner_path=pre_run["output_paths"]["inner"],
        preterminal_path=pre_run["output_paths"]["preterminal"],
        payload_result_path=pre_run["output_paths"]["attempt_result"],
        resource_path=pre_run["output_paths"]["resource_verification"],
        release_path=pre_run["output_paths"]["release"],
        terminal_path=pre_run["output_paths"]["terminal"],
        cleanup_path=pre_run["output_paths"]["cleanup"],
        detached_epoch_path=pre_run["epoch_observation_paths"]["detached-replay"],
        output_path=pre_run["output_paths"]["detached_replay"],
    )
    if detached.get("status") != "PASS":
        raise OrchestratorError("detached resource/terminal replay did not PASS")
    return detached


def _validate_abort_cleanup(evidence: CleanupEvidence) -> None:
    if (
        evidence.payload_current_starttime is not None
        or evidence.keeper_current_starttime is not None
        or evidence.cgroup_path_exists is not False
        or evidence.unit_load_state != "not-found"
        or list(evidence.matching_unit_names)
    ):
        raise OrchestratorError("post-launch failure cleanup left selected-unit residual state")


def _publish_abort_cleanup(
    *,
    cleanup_state: Mapping[str, Any],
    evidence: CleanupEvidence,
    original_failure: Exception,
) -> None:
    pre_run = cleanup_state["pre_run"]
    output = Path(pre_run["output_paths"]["cleanup"])
    if os.path.lexists(output):
        snapshot_bytes(output)
        return
    lifecycle = cleanup_state["lifecycle"]
    launch = cleanup_state["launch"]
    record = {
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "production_certified_authorized": False,
            "runtime_effect_authorized": False,
        },
        "campaign_id": pre_run["campaign_id"],
        "captured_at_monotonic_ns": evidence.captured_at_monotonic_ns,
        "cgroup_path": evidence.cgroup_path,
        "cgroup_path_exists": evidence.cgroup_path_exists,
        "failure_class": type(original_failure).__name__,
        "invocation_id": launch.invocation_id,
        "keeper_current_starttime": evidence.keeper_current_starttime,
        "keeper_pid": launch.supervisor_pid,
        "matching_unit_names": list(evidence.matching_unit_names),
        "payload_current_starttime": evidence.payload_current_starttime,
        "payload_pid": launch.payload_pid,
        "pre_run_authority_identity": cleanup_state["pre_run_identity"],
        "purpose": "PROSPECTIVE_AB16_SELECTED_UNIT_FAIL_CLOSED_CLEANUP",
        "run_nonce": pre_run["run_nonce"],
        "runner_selection_identity": cleanup_state["selection_identity"],
        "schema_version": "noncert-cuts-ab16-abort-cleanup-v1",
        "slot": pre_run["slot"],
        "status": "PASS",
        "unit_load_state": evidence.unit_load_state,
        "unit_name": pre_run["unit_name"],
        "verdict": "SELECTED_UNIT_ABORT_CLEANUP_PASS",
    }
    lifecycle.write_json_exclusive(output, record)


def orchestrate_with_adapter(
    *,
    pre_run_path: Path | str,
    selection_path: Path | str,
    adapter: LifecycleAdapter,
) -> dict[str, object]:
    """Execute one arm and fail-closed clean any post-launch exception."""

    cleanup_state: dict[str, Any] = {}
    try:
        return _orchestrate_with_adapter_unprotected(
            pre_run_path=pre_run_path,
            selection_path=selection_path,
            adapter=adapter,
            cleanup_state=cleanup_state,
        )
    except Exception as original_failure:
        launch = cleanup_state.get("launch")
        if not isinstance(launch, LaunchEvidence):
            raise
        try:
            evidence = adapter.abort_and_capture_cleanup(
                unit_name=cleanup_state["pre_run"]["unit_name"],
                launch=launch,
                control_group=cleanup_state.get("control_group"),
            )
            _validate_abort_cleanup(evidence)
            _publish_abort_cleanup(
                cleanup_state=cleanup_state,
                evidence=evidence,
                original_failure=original_failure,
            )
        except Exception as cleanup_failure:
            raise OrchestratorError("post-launch failure cleanup could not be established") from ExceptionGroup(
                "selected arm failure and cleanup failure",
                [original_failure, cleanup_failure],
            )
        raise


def run_pinned_entry(
    *,
    execution_class: str,
    pre_run_path: Path | str,
    selection_path: Path | str,
) -> dict[str, object]:
    """Run the formal or disposable entry with no injectable live authority."""

    pre_run_snapshot = snapshot_bytes(pre_run_path)
    pre_run = _strict_load(pre_run_snapshot, "pre-run authority")
    if pre_run.get("execution_class") != execution_class:
        raise OrchestratorError("CLI execution class differs from pre-run authority")
    tools = pre_run.get("tool_identities")
    if type(tools) is not dict:
        raise OrchestratorError("pre-run tool identity map is absent")
    current = snapshot_bytes(Path(__file__))
    _identity_matches(
        current.identity,
        tools["organic_unit_orchestrator"],
        "organic unit orchestrator",
    )
    adapter = SubprocessLifecycleAdapter(
        pre_run=pre_run,
        epoch_observer=build_pinned_epoch_observer(pre_run),
    )
    return orchestrate_with_adapter(
        pre_run_path=pre_run_path,
        selection_path=selection_path,
        adapter=adapter,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ("drill", "formal"):
        target = subcommands.add_parser(command)
        target.add_argument("--pre-run", required=True, type=Path)
        target.add_argument("--selection", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    execution_class = "DISPOSABLE_LIVE_DRILL" if arguments.command == "drill" else "FORMAL_AB16"
    try:
        result = run_pinned_entry(
            execution_class=execution_class,
            pre_run_path=arguments.pre_run,
            selection_path=arguments.selection,
        )
    except Exception as exc:
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
