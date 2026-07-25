#!/usr/bin/env python3
"""Cuts Gate 1 v4 two-stage resource and terminal lifecycle.

This module is deliberately independent of the v1-v3 closeout tools and of
the SMM3 authority implementation.  The target transient unit runs an
ordinary-user supervisor and its payload in one cgroup.  After the payload is
reaped, the supervisor remains as the sole keeper.  An ordinary-user observer
captures the live cgroup, an independent verifier authorizes release, and the
observer then freezes terminal and cleanup evidence.

The production adapter only invokes ``systemctl --user`` and reads procfs or
cgroupfs.  Tests inject a fake adapter; importing this module never launches a
unit, solver, or subprocess.
"""

from __future__ import annotations

import argparse
import base64
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import subprocess
import time
from typing import Any, Protocol


SELECTION_SCHEMA = "noncert-cuts-gate1-v4-child-selection-v1"
INNER_SCHEMA = "noncert-cuts-gate1-v4-inner-lifecycle-v1"
PRETERMINAL_SCHEMA = "noncert-cuts-gate1-v4-preterminal-resource-v1"
RELEASE_SCHEMA = "noncert-cuts-gate1-v4-release-token-v1"
TERMINAL_SCHEMA = "noncert-cuts-gate1-v4-terminal-envelope-v1"
CLEANUP_SCHEMA = "noncert-cuts-gate1-v4-cleanup-v1"

UNIT_SLOTS = (
    "q-success",
    "q-postseal-fail",
    "forced-control",
    "forced-treatment",
)
SYNTHETIC_SLOTS = frozenset({"q-success", "q-postseal-fail"})
EXPECTED_RETURNCODE = {
    "q-success": 0,
    "q-postseal-fail": 7,
    "forced-control": 0,
    "forced-treatment": 0,
}
UNIT_RE = re.compile(
    r"cuts-g1v4-[0-9a-f]{12}-"
    r"(q-success|q-postseal-fail|forced-control|forced-treatment)\.service\Z"
)
HEX32_RE = re.compile(r"[0-9a-f]{32}\Z")
HEX64_RE = re.compile(r"[0-9a-f]{64}\Z")

MEMORY_HIGH = 35 * 1024**3
MEMORY_MAX = 39 * 1024**3
MEMORY_SWAP_MAX = 16 * 1024**3
RESOURCE_CONTRACT = {
    "memory_high_bytes": MEMORY_HIGH,
    "memory_max_bytes": MEMORY_MAX,
    "memory_swap_max_bytes": MEMORY_SWAP_MAX,
    "oom_policy": "continue",
    "kill_mode": "control-group",
    "send_sigkill": True,
    "profiles": {
        "synthetic": {
            "runtime_max_seconds": 120,
            "internal_timeout_seconds": 30,
            "keeper_timeout_seconds": 90,
        },
        "formal": {
            "runtime_max_seconds": 1500,
            "internal_timeout_seconds": 1470,
            "keeper_timeout_seconds": 1490,
        },
    },
}

SYSTEMD_PRETERMINAL_FIELDS = (
    "ActiveState",
    "SubState",
    "MainPID",
    "InvocationID",
    "ControlGroup",
    "MemoryHigh",
    "MemoryMax",
    "MemorySwapMax",
    "OOMPolicy",
    "KillMode",
    "SendSIGKILL",
    "RuntimeMaxUSec",
    "Result",
    "ExecMainCode",
    "ExecMainStatus",
    "ExecMainStartTimestampMonotonic",
)
SYSTEMD_TERMINAL_FIELDS = (
    "ActiveState",
    "SubState",
    "Result",
    "ExecMainCode",
    "ExecMainStatus",
    "MainPID",
    "InvocationID",
    "ControlGroup",
    "MemoryHigh",
    "MemoryMax",
    "MemorySwapMax",
    "OOMPolicy",
    "KillMode",
    "SendSIGKILL",
    "RuntimeMaxUSec",
    "ExecMainStartTimestampMonotonic",
    "ExecMainExitTimestampMonotonic",
)
CGROUP_RAW_FIELDS = (
    "memory.high",
    "memory.max",
    "memory.swap.max",
    "memory.current",
    "memory.peak",
    "memory.swap.current",
    "memory.swap.peak",
    "memory.events",
    "memory.events.local",
    "cgroup.procs",
    "cgroup.events",
)

SYSTEMCTL = Path("/usr/bin/systemctl")
MAX_JSON_BYTES = 64 * 1024 * 1024


class LifecycleError(RuntimeError):
    """A lifecycle input, observation, or no-overwrite operation failed."""


@dataclass(frozen=True)
class DetachedDocument:
    """One same-FD byte snapshot and its parsed strict-JSON value."""

    raw: bytes
    identity: dict[str, object]
    value: Mapping[str, Any]


@dataclass(frozen=True)
class CommandEvidence:
    """Raw command evidence without lossy text normalization."""

    argv: tuple[str, ...]
    exit_code: int
    stdout: bytes
    stderr: bytes

    def as_record(self) -> dict[str, object]:
        return {
            "argv": list(self.argv),
            "exit_code": self.exit_code,
            "stdout_base64": base64.b64encode(self.stdout).decode("ascii"),
            "stdout_sha256": hashlib.sha256(self.stdout).hexdigest(),
            "stderr_base64": base64.b64encode(self.stderr).decode("ascii"),
            "stderr_sha256": hashlib.sha256(self.stderr).hexdigest(),
        }


class LifecycleAdapter(Protocol):
    """Unit-external read/cleanup surface used by lifecycle observers."""

    def show(self, unit_name: str, fields: Sequence[str]) -> CommandEvidence: ...

    def read_cgroup(
        self,
        control_group: str,
        fields: Sequence[str],
    ) -> Mapping[str, bytes]: ...

    def pid_starttime(self, pid: int) -> int | None: ...

    def cgroup_exists(self, control_group: str) -> bool: ...

    def cleanup(self, unit_name: str) -> Sequence[CommandEvidence]: ...

    def load_state(self, unit_name: str) -> CommandEvidence: ...


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _strict_json(raw: bytes, label: str) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise LifecycleError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_number(value: str) -> object:
        raise LifecycleError(f"{label}: non-integer JSON number {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject_number,
            parse_constant=reject_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"{label}: malformed strict JSON") from exc


def _exact_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LifecycleError(f"{label}: expected an object")
    return value


def _exact_keys(value: object, expected: set[str], label: str) -> Mapping[str, Any]:
    record = _exact_mapping(value, label)
    if set(record) != expected:
        raise LifecycleError(f"{label}: key set drifted")
    return record


def _exact_int(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise LifecycleError(f"{label}: expected integer >= {minimum}")
    return value


def _identity(value: object, label: str) -> Mapping[str, Any]:
    record = _exact_keys(value, {"path", "size_bytes", "sha256"}, label)
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
        or type(record["sha256"]) is not str
        or HEX64_RE.fullmatch(record["sha256"]) is None
    ):
        raise LifecycleError(f"{label}: invalid detached byte identity")
    return record


def identities_equal(left: object, right: object) -> bool:
    try:
        return dict(_identity(left, "left identity")) == dict(_identity(right, "right identity"))
    except LifecycleError:
        return False


def _snapshot_signature(metadata: os.stat_result) -> tuple[int, ...]:
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


def _reject_symlink_components(path: Path, *, require_leaf: bool) -> Path:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    parts = absolute.parts[1:] if require_leaf else absolute.parent.parts[1:]
    for part in parts:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise LifecycleError(f"path component unavailable: {absolute}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise LifecycleError(f"path contains symlink component: {absolute}")
    return absolute


def snapshot_regular(
    path: Path,
    *,
    expected_identity: Mapping[str, object] | None = None,
    limit: int = MAX_JSON_BYTES,
) -> tuple[bytes, dict[str, object]]:
    """Read/hash one file using one O_NOFOLLOW FD and before/after fstat."""

    absolute = _reject_symlink_components(path, require_leaf=True)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise LifecycleError(f"cannot open input: {absolute}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise LifecycleError(f"input is not a bounded regular file: {absolute}")
        chunks: list[bytes] = []
        size = 0
        while True:
            block = os.read(descriptor, min(1 << 20, limit - size + 1))
            if not block:
                break
            size += len(block)
            if size > limit:
                raise LifecycleError(f"input exceeds fixed cap: {absolute}")
            chunks.append(block)
        after = os.fstat(descriptor)
        if _snapshot_signature(before) != _snapshot_signature(after):
            raise LifecycleError(f"input descriptor drifted during read: {absolute}")
    finally:
        os.close(descriptor)
    try:
        named = os.stat(absolute, follow_symlinks=False)
    except OSError as exc:
        raise LifecycleError(f"input path disappeared after read: {absolute}") from exc
    if _snapshot_signature(after) != _snapshot_signature(named):
        raise LifecycleError(f"input path drifted after read: {absolute}")
    raw = b"".join(chunks)
    identity: dict[str, object] = {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if expected_identity is not None and not identities_equal(identity, expected_identity):
        raise LifecycleError(f"detached byte identity mismatch: {absolute}")
    return raw, identity


def load_detached_json(
    path: Path,
    *,
    expected_identity: Mapping[str, object] | None = None,
    label: str,
) -> DetachedDocument:
    raw, identity = snapshot_regular(path, expected_identity=expected_identity)
    value = _exact_mapping(_strict_json(raw, label), label)
    return DetachedDocument(raw=raw, identity=identity, value=value)


def write_exclusive(path: Path, raw: bytes) -> dict[str, object]:
    absolute = _reject_symlink_components(path, require_leaf=False)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags, 0o600)
    except OSError as exc:
        raise LifecycleError(f"cannot create output exclusively: {absolute}") from exc
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise LifecycleError(f"short output write: {absolute}")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _, identity = snapshot_regular(absolute, limit=max(MAX_JSON_BYTES, len(raw)))
    return identity


def _validate_contract(value: object) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "memory_high_bytes",
            "memory_max_bytes",
            "memory_swap_max_bytes",
            "oom_policy",
            "kill_mode",
            "send_sigkill",
            "profiles",
        },
        "selection resource_contract",
    )
    if dict(record) != RESOURCE_CONTRACT:
        raise LifecycleError("selection resource contract drifted")
    return record


def _validate_selection(value: object) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "schema_version",
            "created_at_utc",
            "purpose",
            "campaign_id",
            "run_nonce",
            "package_id",
            "repository_head",
            "selection_id",
            "campaign_root_identity",
            "manager_epoch",
            "resource_contract",
            "tools",
            "inputs",
            "units",
        },
        "Gate 1 selection",
    )
    if (
        record["schema_version"] != SELECTION_SCHEMA
        or record["purpose"] != "gate1_v4_child_suite"
        or type(record["campaign_id"]) is not str
        or HEX64_RE.fullmatch(record["campaign_id"]) is None
        or type(record["run_nonce"]) is not str
        or not record["run_nonce"]
        or type(record["package_id"]) is not str
        or HEX64_RE.fullmatch(record["package_id"]) is None
        or type(record["repository_head"]) is not str
        or len(record["repository_head"]) != 40
        or type(record["selection_id"]) is not str
        or HEX64_RE.fullmatch(record["selection_id"]) is None
    ):
        raise LifecycleError("Gate 1 selection scalar fields drifted")
    _identity(record["campaign_root_identity"], "campaign root identity")
    _exact_mapping(record["manager_epoch"], "selection manager_epoch")
    _validate_contract(record["resource_contract"])
    for group in ("tools", "inputs"):
        values = _exact_mapping(record[group], f"selection {group}")
        if not values:
            raise LifecycleError(f"selection {group} is empty")
        for role, identity in values.items():
            if type(role) is not str or not role:
                raise LifecycleError(f"selection {group} role is invalid")
            _identity(identity, f"selection {group}.{role}")
    units = _exact_keys(record["units"], set(UNIT_SLOTS), "selection units")
    token = record["campaign_id"][:12]
    seen_paths: set[str] = set()
    for slot in UNIT_SLOTS:
        unit = _exact_keys(
            units[slot],
            {
                "slot",
                "unit_name",
                "attempt_dir",
                "epoch_checkpoint_paths",
                "raw_dir",
                "terminal_dir",
                "result_path",
                "contract_profile",
            },
            f"selection units.{slot}",
        )
        expected_name = f"cuts-g1v4-{token}-{slot}.service"
        expected_profile = "synthetic" if slot in SYNTHETIC_SLOTS else "formal"
        if (
            unit["slot"] != slot
            or unit["unit_name"] != expected_name
            or UNIT_RE.fullmatch(str(unit["unit_name"])) is None
            or unit["contract_profile"] != expected_profile
        ):
            raise LifecycleError(f"selection unit identity/profile drifted: {slot}")
        attempt = Path(str(unit["attempt_dir"]))
        raw_dir = Path(str(unit["raw_dir"]))
        terminal_dir = Path(str(unit["terminal_dir"]))
        result = Path(str(unit["result_path"]))
        checkpoints = _exact_keys(
            unit["epoch_checkpoint_paths"],
            {
                "cleanup",
                "detached-replay",
                "prelaunch",
                "preterminal",
                "terminal",
            },
            f"selection units.{slot}.epoch_checkpoint_paths",
        )
        if not all(item.is_absolute() for item in (attempt, raw_dir, terminal_dir, result)):
            raise LifecycleError(f"selection unit paths must be absolute: {slot}")
        if (
            raw_dir.parent != attempt
            or terminal_dir.parent != attempt
            or result.parent != attempt
            or raw_dir.name != "raw"
            or terminal_dir.name != "terminal"
        ):
            raise LifecycleError(f"selection unit path topology drifted: {slot}")
        for phase, checkpoint_path in checkpoints.items():
            if Path(str(checkpoint_path)) != (attempt / "authority" / f"manager-epoch-{phase}.json"):
                raise LifecycleError(f"selection unit manager epoch path drifted: {slot}.{phase}")
        for item in (attempt, raw_dir, terminal_dir, result):
            text = str(item)
            if text in seen_paths:
                raise LifecycleError("selection unit paths overlap")
            seen_paths.add(text)
    body = dict(record)
    body.pop("selection_id")
    if _canonical_digest(body) != record["selection_id"]:
        raise LifecycleError("selection_id does not reseal selection semantics")
    return record


def load_gate1_selection(
    path: Path,
    *,
    expected_identity: Mapping[str, object],
) -> DetachedDocument:
    document = load_detached_json(
        path,
        expected_identity=expected_identity,
        label="Gate 1 selection",
    )
    _validate_selection(document.value)
    return document


def load_gate1_selection_bytes(
    raw: bytes,
    identity: Mapping[str, object],
) -> DetachedDocument:
    """Validate already-detached selection bytes without reopening a path."""

    checked_identity = dict(_identity(identity, "selection identity"))
    if len(raw) != checked_identity["size_bytes"] or hashlib.sha256(raw).hexdigest() != checked_identity["sha256"]:
        raise LifecycleError("selection detached bytes do not match their identity")
    value = _validate_selection(_strict_json(raw, "Gate 1 selection"))
    return DetachedDocument(raw=bytes(raw), identity=checked_identity, value=value)


def _unit(selection: Mapping[str, Any], slot: str) -> Mapping[str, Any]:
    if slot not in UNIT_SLOTS:
        raise LifecycleError(f"unknown Gate 1 unit slot: {slot}")
    return _exact_mapping(selection["units"][slot], f"selection unit {slot}")


def lifecycle_paths(selection: Mapping[str, Any], slot: str) -> dict[str, Path]:
    unit = _unit(selection, slot)
    raw_dir = Path(unit["raw_dir"])
    terminal_dir = Path(unit["terminal_dir"])
    return {
        "payload_seal": raw_dir / "payload-seal.json",
        "inner": raw_dir / "inner-lifecycle.json",
        "preterminal": terminal_dir / "preterminal.json",
        "resource_verification": terminal_dir / "resource-verification.json",
        "release": terminal_dir / "release-token.json",
        "terminal": terminal_dir / "terminal.json",
        "cleanup": terminal_dir / "cleanup.json",
        "result": Path(unit["result_path"]),
    }


def _proc_starttime(pid: int) -> int | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_bytes()
    except FileNotFoundError:
        return None
    close = raw.rfind(b")")
    if close < 0:
        raise LifecycleError(f"malformed /proc/{pid}/stat")
    fields = raw[close + 2 :].split()
    if len(fields) < 20 or not fields[19].isdigit():
        raise LifecycleError(f"malformed /proc/{pid}/stat starttime")
    return int(fields[19])


def _wait_without_reaping(
    pid: int,
    *,
    timeout_seconds: int,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
) -> os.waitid_result | None:
    deadline = monotonic() + timeout_seconds
    options = os.WEXITED | os.WNOWAIT | os.WNOHANG
    while monotonic() <= deadline:
        status = os.waitid(os.P_PID, pid, options)
        if status is not None:
            return status
        sleep(0.05)
    return None


def _terminate_exact_child(process: subprocess.Popen[bytes]) -> None:
    try:
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _returncode_from_waitid(status: os.waitid_result) -> int:
    if status.si_code == os.CLD_EXITED:
        return int(status.si_status)
    if status.si_code in {os.CLD_KILLED, os.CLD_DUMPED}:
        return -int(status.si_status)
    raise LifecycleError(f"unsupported waitid si_code: {status.si_code}")


def supervise_payload(
    *,
    selection: DetachedDocument,
    unit_slot: str,
    payload_argv: Sequence[str],
    invocation_id: str,
    popen: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
    monotonic: Callable[[], float] = time.monotonic,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Run one payload, reap it, remain as keeper, then mirror its status."""

    selected = _validate_selection(selection.value)
    unit = _unit(selected, unit_slot)
    paths = lifecycle_paths(selected, unit_slot)
    if HEX32_RE.fullmatch(invocation_id) is None:
        raise LifecycleError("supervisor InvocationID is invalid")
    if os.geteuid() != os.getuid() or os.geteuid() == 0:
        raise LifecycleError("supervisor must run as the ordinary selected user")
    if (
        not isinstance(payload_argv, Sequence)
        or isinstance(payload_argv, (str, bytes))
        or not payload_argv
        or any(type(item) is not str or not item for item in payload_argv)
    ):
        raise LifecycleError("payload argv is invalid")
    profile = selected["resource_contract"]["profiles"][unit["contract_profile"]]
    supervisor_pid = os.getpid()
    supervisor_start = _proc_starttime(supervisor_pid)
    if supervisor_start is None:
        raise LifecycleError("cannot establish supervisor starttime")
    spawned_ns = monotonic_ns()
    process = popen(
        list(payload_argv),
        close_fds=True,
        start_new_session=False,
        stdout=None,
        stderr=None,
    )
    payload_start = _proc_starttime(process.pid)
    if payload_start is None:
        _terminate_exact_child(process)
        raise LifecycleError("cannot establish payload starttime")
    wait_status = _wait_without_reaping(
        process.pid,
        timeout_seconds=profile["internal_timeout_seconds"],
        monotonic=monotonic,
        sleep=sleep,
    )
    timed_out = wait_status is None
    if timed_out:
        _terminate_exact_child(process)
        returncode = int(process.returncode)
        waitid_record: dict[str, object] | None = None
    else:
        assert wait_status is not None
        expected_returncode = _returncode_from_waitid(wait_status)
        returncode = int(process.wait())
        if returncode != expected_returncode:
            raise LifecycleError("waitid/waitpid payload status mismatch")
        waitid_record = {
            "si_pid": int(wait_status.si_pid),
            "si_uid": int(wait_status.si_uid),
            "si_signo": int(wait_status.si_signo),
            "si_status": int(wait_status.si_status),
            "si_code": int(wait_status.si_code),
        }
    reaped_ns = monotonic_ns()
    if _proc_starttime(process.pid) is not None:
        raise LifecycleError("payload remains after waitpid")
    seal_raw, seal_identity = snapshot_regular(paths["payload_seal"])
    _exact_mapping(_strict_json(seal_raw, "payload seal"), "payload seal")
    _, result_identity = snapshot_regular(paths["result"])
    inner = {
        "schema_version": INNER_SCHEMA,
        "created_at_utc": _utc_now(),
        "selection_identity": dict(selection.identity),
        "campaign_id": selected["campaign_id"],
        "run_nonce": selected["run_nonce"],
        "selection_id": selected["selection_id"],
        "manager_epoch_digest": _canonical_digest(selected["manager_epoch"]),
        "unit_slot": unit_slot,
        "unit_name": unit["unit_name"],
        "invocation_id": invocation_id,
        "contract_profile": unit["contract_profile"],
        "payload_argv": list(payload_argv),
        "supervisor_pid": supervisor_pid,
        "supervisor_starttime": supervisor_start,
        "payload_pid": process.pid,
        "payload_starttime": payload_start,
        "payload_spawned_monotonic_ns": spawned_ns,
        "payload_reaped_monotonic_ns": reaped_ns,
        "payload_reaped": True,
        "payload_timed_out": timed_out,
        "payload_returncode": returncode,
        "waitid": waitid_record,
        "payload_seal_identity": seal_identity,
        "payload_result_identity": result_identity,
        "keeper_pid": supervisor_pid,
        "keeper_starttime": supervisor_start,
        "keeper_ready_monotonic_ns": monotonic_ns(),
    }
    inner_identity = write_exclusive(paths["inner"], canonical_json_bytes(inner))
    release_deadline = monotonic() + profile["keeper_timeout_seconds"]
    release: DetachedDocument | None = None
    while monotonic() <= release_deadline:
        if os.path.lexists(paths["release"]):
            release = load_detached_json(paths["release"], label="release token")
            break
        sleep(0.05)
    if release is None:
        raise LifecycleError("keeper release token did not arrive before timeout")
    token = _exact_keys(
        release.value,
        {
            "schema_version",
            "created_at_utc",
            "selection_identity",
            "campaign_id",
            "run_nonce",
            "selection_id",
            "manager_epoch_digest",
            "unit_slot",
            "unit_name",
            "invocation_id",
            "inner_identity",
            "preterminal_identity",
            "resource_verification_identity",
            "verdict",
            "released_monotonic_ns",
        },
        "release token",
    )
    if (
        token["schema_version"] != RELEASE_SCHEMA
        or token["verdict"] != "RESOURCE_PRETERMINAL_PASS"
        or not identities_equal(token["selection_identity"], selection.identity)
        or token["campaign_id"] != selected["campaign_id"]
        or token["run_nonce"] != selected["run_nonce"]
        or token["selection_id"] != selected["selection_id"]
        or token["manager_epoch_digest"] != _canonical_digest(selected["manager_epoch"])
        or token["unit_slot"] != unit_slot
        or token["unit_name"] != unit["unit_name"]
        or token["invocation_id"] != invocation_id
        or not identities_equal(token["inner_identity"], inner_identity)
    ):
        raise LifecycleError("release token does not join the keeper")
    return returncode


def _command_record(command: CommandEvidence, expected_argv: Sequence[str]) -> dict[str, object]:
    if tuple(expected_argv) != command.argv:
        raise LifecycleError("adapter command argv drifted")
    if type(command.exit_code) is not int:
        raise LifecycleError("adapter command exit code is not an integer")
    return command.as_record()


def _decode_command(record: Mapping[str, Any], label: str) -> tuple[bytes, bytes]:
    exact = _exact_keys(
        record,
        {
            "argv",
            "exit_code",
            "stdout_base64",
            "stdout_sha256",
            "stderr_base64",
            "stderr_sha256",
        },
        label,
    )
    try:
        stdout = base64.b64decode(exact["stdout_base64"], validate=True)
        stderr = base64.b64decode(exact["stderr_base64"], validate=True)
    except (TypeError, ValueError) as exc:
        raise LifecycleError(f"{label}: invalid base64") from exc
    if (
        type(exact["argv"]) is not list
        or any(type(item) is not str for item in exact["argv"])
        or type(exact["exit_code"]) is not int
        or hashlib.sha256(stdout).hexdigest() != exact["stdout_sha256"]
        or hashlib.sha256(stderr).hexdigest() != exact["stderr_sha256"]
    ):
        raise LifecycleError(f"{label}: command evidence drifted")
    return stdout, stderr


def _show_argv(unit_name: str, fields: Sequence[str]) -> tuple[str, ...]:
    return (
        str(SYSTEMCTL),
        "--user",
        "show",
        "--no-pager",
        *(f"--property={field}" for field in fields),
        unit_name,
    )


def _load_state_argv(unit_name: str) -> tuple[str, ...]:
    return (
        str(SYSTEMCTL),
        "--user",
        "show",
        unit_name,
        "--property=LoadState",
        "--value",
    )


def _parse_show(
    evidence: CommandEvidence,
    unit_name: str,
    fields: Sequence[str],
) -> tuple[dict[str, object], dict[str, str]]:
    record = _command_record(evidence, _show_argv(unit_name, fields))
    if evidence.exit_code != 0 or evidence.stderr:
        raise LifecycleError(f"systemctl --user show failed for {unit_name}")
    try:
        text = evidence.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LifecycleError("systemctl show output is not UTF-8") from exc
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            raise LifecycleError("systemctl show emitted malformed output")
        name, value = line.split("=", 1)
        if name in parsed:
            raise LifecycleError(f"systemctl show duplicated {name}")
        parsed[name] = value
    if set(parsed) != set(fields):
        raise LifecycleError("systemctl show field set drifted")
    return record, parsed


def _raw_cgroup_record(raw: Mapping[str, bytes]) -> dict[str, object]:
    if set(raw) != set(CGROUP_RAW_FIELDS):
        raise LifecycleError("cgroup raw field set drifted")
    result: dict[str, object] = {}
    for field in CGROUP_RAW_FIELDS:
        value = raw[field]
        if type(value) is not bytes:
            raise LifecycleError(f"cgroup {field} is not raw bytes")
        result[field] = {
            "base64": base64.b64encode(value).decode("ascii"),
            "sha256": hashlib.sha256(value).hexdigest(),
        }
    return result


def _parse_nonnegative(value: str, label: str) -> int:
    if not value.isdigit():
        raise LifecycleError(f"{label} is not a nonnegative decimal integer")
    return int(value)


def _selection_join(
    output: Mapping[str, Any],
    selection: DetachedDocument,
    unit_slot: str,
) -> None:
    selected = selection.value
    unit = _unit(selected, unit_slot)
    expected = {
        "selection_identity": selection.identity,
        "campaign_id": selected["campaign_id"],
        "run_nonce": selected["run_nonce"],
        "selection_id": selected["selection_id"],
        "manager_epoch_digest": _canonical_digest(selected["manager_epoch"]),
        "unit_slot": unit_slot,
        "unit_name": unit["unit_name"],
    }
    for name, value in expected.items():
        if name.endswith("_identity"):
            if not identities_equal(output.get(name), value):
                raise LifecycleError(f"lifecycle {name} join drifted")
        elif output.get(name) != value:
            raise LifecycleError(f"lifecycle {name} join drifted")


def capture_preterminal(
    *,
    selection: DetachedDocument,
    unit_slot: str,
    adapter: LifecycleAdapter,
    output_path: Path | None = None,
    now_utc: Callable[[], str] = _utc_now,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> tuple[dict[str, object], dict[str, object]]:
    selected = _validate_selection(selection.value)
    unit = _unit(selected, unit_slot)
    paths = lifecycle_paths(selected, unit_slot)
    destination = paths["preterminal"] if output_path is None else output_path
    if destination != paths["preterminal"]:
        raise LifecycleError("preterminal output path is not selected")
    inner = load_detached_json(paths["inner"], label="inner lifecycle")
    inner_value = _exact_mapping(inner.value, "inner lifecycle")
    _selection_join(inner_value, selection, unit_slot)
    invocation = inner_value.get("invocation_id")
    if type(invocation) is not str or HEX32_RE.fullmatch(invocation) is None:
        raise LifecycleError("inner lifecycle InvocationID is invalid")
    command = adapter.show(unit["unit_name"], SYSTEMD_PRETERMINAL_FIELDS)
    systemd_command, systemd_raw = _parse_show(
        command,
        unit["unit_name"],
        SYSTEMD_PRETERMINAL_FIELDS,
    )
    control_group = systemd_raw["ControlGroup"]
    if not control_group.startswith("/"):
        raise LifecycleError("preterminal ControlGroup is unavailable")
    cgroup_raw = adapter.read_cgroup(control_group, CGROUP_RAW_FIELDS)
    keeper_pid = _exact_int(inner_value.get("keeper_pid"), "inner keeper_pid", minimum=1)
    payload_pid = _exact_int(inner_value.get("payload_pid"), "inner payload_pid", minimum=1)
    keeper_start = adapter.pid_starttime(keeper_pid)
    payload_start = adapter.pid_starttime(payload_pid)
    preterminal = {
        "schema_version": PRETERMINAL_SCHEMA,
        "captured_at_utc": now_utc(),
        "captured_monotonic_ns": monotonic_ns(),
        "selection_identity": dict(selection.identity),
        "campaign_id": selected["campaign_id"],
        "run_nonce": selected["run_nonce"],
        "selection_id": selected["selection_id"],
        "manager_epoch_digest": _canonical_digest(selected["manager_epoch"]),
        "unit_slot": unit_slot,
        "unit_name": unit["unit_name"],
        "invocation_id": invocation,
        "inner_identity": inner.identity,
        "supervisor_pid": inner_value.get("supervisor_pid"),
        "supervisor_starttime": inner_value.get("supervisor_starttime"),
        "payload_pid": payload_pid,
        "payload_starttime": inner_value.get("payload_starttime"),
        "payload_reaped": inner_value.get("payload_reaped"),
        "payload_returncode": inner_value.get("payload_returncode"),
        "keeper_pid": keeper_pid,
        "keeper_starttime": inner_value.get("keeper_starttime"),
        "keeper_current_starttime": keeper_start,
        "payload_current_starttime": payload_start,
        "control_group": control_group,
        "systemd_command": systemd_command,
        "systemd_raw": systemd_raw,
        "cgroup_raw": _raw_cgroup_record(cgroup_raw),
        "release_created": os.path.lexists(paths["release"]),
    }
    identity = write_exclusive(destination, canonical_json_bytes(preterminal))
    return preterminal, identity


def capture_terminal(
    *,
    selection: DetachedDocument,
    unit_slot: str,
    adapter: LifecycleAdapter,
    preterminal_identity: Mapping[str, object],
    release_identity: Mapping[str, object],
    timeout_seconds: int = 30,
    poll_seconds: float = 0.05,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    now_utc: Callable[[], str] = _utc_now,
) -> tuple[dict[str, object], dict[str, object]]:
    selected = _validate_selection(selection.value)
    unit = _unit(selected, unit_slot)
    paths = lifecycle_paths(selected, unit_slot)
    preterminal = load_detached_json(
        paths["preterminal"],
        expected_identity=preterminal_identity,
        label="preterminal",
    )
    release = load_detached_json(
        paths["release"],
        expected_identity=release_identity,
        label="release token",
    )
    _selection_join(preterminal.value, selection, unit_slot)
    _selection_join(release.value, selection, unit_slot)
    invocation = preterminal.value.get("invocation_id")
    deadline = monotonic() + timeout_seconds
    final_command: CommandEvidence | None = None
    final_raw: dict[str, str] | None = None
    while monotonic() <= deadline:
        command = adapter.show(unit["unit_name"], SYSTEMD_TERMINAL_FIELDS)
        _, raw = _parse_show(command, unit["unit_name"], SYSTEMD_TERMINAL_FIELDS)
        if raw["InvocationID"] != invocation:
            raise LifecycleError("terminal InvocationID drifted")
        if raw["ActiveState"] == "failed" or (raw["ActiveState"] == "active" and raw["SubState"] == "exited"):
            final_command = command
            final_raw = raw
            break
        sleep(poll_seconds)
    if final_command is None or final_raw is None:
        raise LifecycleError("unit did not reach terminal state before timeout")
    command_record, stable_raw = _parse_show(
        final_command,
        unit["unit_name"],
        SYSTEMD_TERMINAL_FIELDS,
    )
    if stable_raw != final_raw:
        raise LifecycleError("terminal systemd evidence changed while parsed")
    terminal = {
        "schema_version": TERMINAL_SCHEMA,
        "captured_at_utc": now_utc(),
        "captured_monotonic_ns": monotonic_ns(),
        "selection_identity": dict(selection.identity),
        "campaign_id": selected["campaign_id"],
        "run_nonce": selected["run_nonce"],
        "selection_id": selected["selection_id"],
        "manager_epoch_digest": _canonical_digest(selected["manager_epoch"]),
        "unit_slot": unit_slot,
        "unit_name": unit["unit_name"],
        "invocation_id": invocation,
        "inner_identity": preterminal.value["inner_identity"],
        "preterminal_identity": dict(preterminal_identity),
        "release_identity": dict(release_identity),
        "preterminal_control_group": preterminal.value["control_group"],
        "terminal_control_group_used_as_cleanup_evidence": False,
        "systemd_command": command_record,
        "systemd_raw": final_raw,
    }
    identity = write_exclusive(paths["terminal"], canonical_json_bytes(terminal))
    return terminal, identity


def capture_cleanup(
    *,
    selection: DetachedDocument,
    unit_slot: str,
    adapter: LifecycleAdapter,
    terminal_identity: Mapping[str, object],
    timeout_seconds: int = 30,
    poll_seconds: float = 0.05,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    now_utc: Callable[[], str] = _utc_now,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> tuple[dict[str, object], dict[str, object]]:
    selected = _validate_selection(selection.value)
    unit = _unit(selected, unit_slot)
    paths = lifecycle_paths(selected, unit_slot)
    inner = load_detached_json(paths["inner"], label="inner lifecycle")
    terminal = load_detached_json(
        paths["terminal"],
        expected_identity=terminal_identity,
        label="terminal envelope",
    )
    _selection_join(inner.value, selection, unit_slot)
    _selection_join(terminal.value, selection, unit_slot)
    commands = adapter.cleanup(unit["unit_name"])
    command_records: list[dict[str, object]] = []
    expected = (
        (str(SYSTEMCTL), "--user", "stop", unit["unit_name"]),
        (str(SYSTEMCTL), "--user", "reset-failed", unit["unit_name"]),
    )
    if len(commands) != len(expected):
        raise LifecycleError("cleanup command count drifted")
    for command, argv in zip(commands, expected, strict=True):
        command_records.append(_command_record(command, argv))
    payload_pid = _exact_int(inner.value.get("payload_pid"), "inner payload_pid", minimum=1)
    keeper_pid = _exact_int(inner.value.get("keeper_pid"), "inner keeper_pid", minimum=1)
    control_group = str(terminal.value["preterminal_control_group"])
    deadline = monotonic() + timeout_seconds
    load_state_command: CommandEvidence | None = None
    payload_current: int | None = None
    keeper_current: int | None = None
    cgroup_exists = True
    unit_absent = False
    while monotonic() <= deadline:
        current_command = adapter.load_state(unit["unit_name"])
        current_unit_absent = (
            current_command.exit_code == 0
            and current_command.stdout == b"not-found\n"
            and current_command.stderr == b""
        )
        current_payload = adapter.pid_starttime(payload_pid)
        current_keeper = adapter.pid_starttime(keeper_pid)
        current_cgroup = adapter.cgroup_exists(control_group)
        if (
            current_unit_absent
            and current_payload != inner.value["payload_starttime"]
            and current_keeper != inner.value["keeper_starttime"]
            and not current_cgroup
        ):
            load_state_command = current_command
            unit_absent = True
            payload_current = current_payload
            keeper_current = current_keeper
            cgroup_exists = current_cgroup
            break
        sleep(poll_seconds)
    if load_state_command is None:
        raise LifecycleError("unit/process/cgroup cleanup did not complete before timeout")
    load_state_record = _command_record(
        load_state_command,
        _load_state_argv(unit["unit_name"]),
    )
    cleanup = {
        "schema_version": CLEANUP_SCHEMA,
        "captured_at_utc": now_utc(),
        "captured_monotonic_ns": monotonic_ns(),
        "selection_identity": dict(selection.identity),
        "campaign_id": selected["campaign_id"],
        "run_nonce": selected["run_nonce"],
        "selection_id": selected["selection_id"],
        "manager_epoch_digest": _canonical_digest(selected["manager_epoch"]),
        "unit_slot": unit_slot,
        "unit_name": unit["unit_name"],
        "invocation_id": terminal.value["invocation_id"],
        "inner_identity": inner.identity,
        "terminal_identity": dict(terminal_identity),
        "cleanup_commands": command_records,
        "load_state_command": load_state_record,
        "unit_absent": unit_absent,
        "payload_pid": payload_pid,
        "payload_current_starttime": payload_current,
        "keeper_pid": keeper_pid,
        "keeper_current_starttime": keeper_current,
        "preterminal_control_group": control_group,
        "cgroup_exists": cgroup_exists,
        "terminal_control_group_used_as_cleanup_evidence": False,
    }
    identity = write_exclusive(paths["cleanup"], canonical_json_bytes(cleanup))
    return cleanup, identity


class SystemctlUserAdapter:
    """Production ordinary-user adapter for one selected unit."""

    def _run(self, argv: Sequence[str], *, timeout: int = 15) -> CommandEvidence:
        completed = subprocess.run(
            list(argv),
            check=False,
            capture_output=True,
            timeout=timeout,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )
        return CommandEvidence(
            argv=tuple(argv),
            exit_code=int(completed.returncode),
            stdout=bytes(completed.stdout),
            stderr=bytes(completed.stderr),
        )

    def show(self, unit_name: str, fields: Sequence[str]) -> CommandEvidence:
        if UNIT_RE.fullmatch(unit_name) is None:
            raise LifecycleError("refusing systemctl query outside cuts Gate 1 namespace")
        return self._run(_show_argv(unit_name, fields))

    def read_cgroup(
        self,
        control_group: str,
        fields: Sequence[str],
    ) -> Mapping[str, bytes]:
        if tuple(fields) != CGROUP_RAW_FIELDS:
            raise LifecycleError("refusing partial cgroup capture")
        pure = PurePosixPath(control_group)
        if not pure.is_absolute() or ".." in pure.parts or control_group == "/":
            raise LifecycleError("invalid selected cgroup path")
        base = Path("/sys/fs/cgroup").joinpath(*pure.parts[1:])
        result: dict[str, bytes] = {}
        for field in fields:
            path = base / field
            absolute = _reject_symlink_components(path, require_leaf=True)
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(absolute, flags)
            try:
                before = os.fstat(descriptor)
                chunks: list[bytes] = []
                while True:
                    block = os.read(descriptor, 1 << 20)
                    if not block:
                        break
                    chunks.append(block)
                after = os.fstat(descriptor)
                if before.st_dev != after.st_dev or before.st_ino != after.st_ino:
                    raise LifecycleError(f"cgroup file identity drifted: {field}")
            finally:
                os.close(descriptor)
            result[field] = b"".join(chunks)
        return result

    def pid_starttime(self, pid: int) -> int | None:
        return _proc_starttime(pid)

    def cgroup_exists(self, control_group: str) -> bool:
        pure = PurePosixPath(control_group)
        if not pure.is_absolute() or ".." in pure.parts or control_group == "/":
            raise LifecycleError("invalid selected cgroup path")
        path = Path("/sys/fs/cgroup").joinpath(*pure.parts[1:])
        return os.path.lexists(path)

    def cleanup(self, unit_name: str) -> Sequence[CommandEvidence]:
        if UNIT_RE.fullmatch(unit_name) is None:
            raise LifecycleError("refusing cleanup outside cuts Gate 1 namespace")
        return (
            self._run((str(SYSTEMCTL), "--user", "stop", unit_name), timeout=30),
            self._run((str(SYSTEMCTL), "--user", "reset-failed", unit_name)),
        )

    def load_state(self, unit_name: str) -> CommandEvidence:
        if UNIT_RE.fullmatch(unit_name) is None:
            raise LifecycleError("refusing load-state query outside cuts Gate 1 namespace")
        return self._run(_load_state_argv(unit_name))


def _selection_identity_from_args(arguments: argparse.Namespace) -> dict[str, object]:
    return {
        "path": str(arguments.selection.absolute()),
        "size_bytes": arguments.selection_size,
        "sha256": arguments.selection_sha256,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    def common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--selection", required=True, type=Path)
        target.add_argument("--selection-size", required=True, type=int)
        target.add_argument("--selection-sha256", required=True)
        target.add_argument("--unit-slot", required=True, choices=UNIT_SLOTS)

    supervisor = subparsers.add_parser("supervisor")
    common(supervisor)
    supervisor.add_argument("--invocation-id")
    supervisor.add_argument("payload", nargs=argparse.REMAINDER)

    preterminal = subparsers.add_parser("preterminal")
    common(preterminal)

    terminal = subparsers.add_parser("terminal")
    common(terminal)
    terminal.add_argument("--preterminal-size", required=True, type=int)
    terminal.add_argument("--preterminal-sha256", required=True)
    terminal.add_argument("--release-size", required=True, type=int)
    terminal.add_argument("--release-sha256", required=True)

    cleanup = subparsers.add_parser("cleanup")
    common(cleanup)
    cleanup.add_argument("--terminal-size", required=True, type=int)
    cleanup.add_argument("--terminal-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    identity = _selection_identity_from_args(arguments)
    selection = load_gate1_selection(arguments.selection, expected_identity=identity)
    adapter = SystemctlUserAdapter()
    if arguments.mode == "supervisor":
        if not arguments.payload:
            raise LifecycleError("supervisor payload argv is empty")
        environment_invocation = os.environ.get("INVOCATION_ID")
        if (
            arguments.invocation_id is not None
            and environment_invocation is not None
            and arguments.invocation_id != environment_invocation
        ):
            raise LifecycleError("supervisor InvocationID argument differs from systemd environment")
        invocation_id = arguments.invocation_id or environment_invocation
        if invocation_id is None:
            raise LifecycleError("supervisor InvocationID is absent from both argument and systemd environment")
        return supervise_payload(
            selection=selection,
            unit_slot=arguments.unit_slot,
            payload_argv=arguments.payload,
            invocation_id=invocation_id,
        )
    if arguments.mode == "preterminal":
        capture_preterminal(
            selection=selection,
            unit_slot=arguments.unit_slot,
            adapter=adapter,
        )
        return 0
    paths = lifecycle_paths(selection.value, arguments.unit_slot)
    if arguments.mode == "terminal":
        capture_terminal(
            selection=selection,
            unit_slot=arguments.unit_slot,
            adapter=adapter,
            preterminal_identity={
                "path": str(paths["preterminal"]),
                "size_bytes": arguments.preterminal_size,
                "sha256": arguments.preterminal_sha256,
            },
            release_identity={
                "path": str(paths["release"]),
                "size_bytes": arguments.release_size,
                "sha256": arguments.release_sha256,
            },
        )
        return 0
    capture_cleanup(
        selection=selection,
        unit_slot=arguments.unit_slot,
        adapter=adapter,
        terminal_identity={
            "path": str(paths["terminal"]),
            "size_bytes": arguments.terminal_size,
            "sha256": arguments.terminal_sha256,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
