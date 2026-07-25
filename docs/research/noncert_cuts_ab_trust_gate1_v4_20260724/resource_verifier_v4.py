#!/usr/bin/env python3
"""Independent verifier for the cuts Gate 1 v4 two-stage lifecycle.

The verifier does not import the lifecycle recorder/observer.  It consumes
already-detached selection bytes and immutable raw envelopes, independently
derives the cgroup contract, keeper state, payload result, systemd terminal
state, and cleanup result, then emits either a pre-terminal release authority
or a detached PASS receipt.
"""

from __future__ import annotations

import argparse
import base64
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from typing import Any


SELECTION_SCHEMA = "noncert-cuts-gate1-v4-child-selection-v1"
INNER_SCHEMA = "noncert-cuts-gate1-v4-inner-lifecycle-v1"
PRETERMINAL_SCHEMA = "noncert-cuts-gate1-v4-preterminal-resource-v1"
RESOURCE_SCHEMA = "noncert-cuts-gate1-v4-resource-verification-v1"
RELEASE_SCHEMA = "noncert-cuts-gate1-v4-release-token-v1"
TERMINAL_SCHEMA = "noncert-cuts-gate1-v4-terminal-envelope-v1"
CLEANUP_SCHEMA = "noncert-cuts-gate1-v4-cleanup-v1"
DETACHED_SCHEMA = "noncert-cuts-gate1-v4-detached-lifecycle-v1"

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
EXPECTED_TERMINAL_CLASS = {
    "q-success": "success",
    "q-postseal-fail": "postseal-failure",
    "forced-control": "success",
    "forced-treatment": "success",
}
HEX32_RE = re.compile(r"[0-9a-f]{32}\Z")
HEX64_RE = re.compile(r"[0-9a-f]{64}\Z")
UNIT_RE = re.compile(
    r"cuts-g1v4-[0-9a-f]{12}-"
    r"(q-success|q-postseal-fail|forced-control|forced-treatment)\.service\Z"
)

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
MEMORY_EVENT_REQUIRED_KEYS = frozenset(
    {
        "low",
        "high",
        "max",
        "oom",
        "oom_kill",
        "oom_group_kill",
    }
)
MEMORY_EVENT_OPTIONAL_ZERO_KEYS = frozenset({"sock_throttled"})
SYSTEMCTL = "/usr/bin/systemctl"
MAX_JSON_BYTES = 64 * 1024 * 1024


class VerificationError(RuntimeError):
    """The immutable lifecycle evidence does not establish its claim."""


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


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _strict_json(raw: bytes, label: str) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise VerificationError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> object:
        raise VerificationError(f"{label}: non-integer JSON number {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"{label}: malformed strict JSON") from exc


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise VerificationError(f"{label}: expected object")
    return value


def _keys(value: object, keys: set[str], label: str) -> Mapping[str, Any]:
    record = _mapping(value, label)
    if set(record) != keys:
        raise VerificationError(f"{label}: key set drifted")
    return record


def _integer(value: object, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise VerificationError(f"{label}: expected integer >= {minimum}")
    return value


def _utc(value: object, label: str) -> str:
    if type(value) is not str:
        raise VerificationError(f"{label}: expected UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VerificationError(f"{label}: invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise VerificationError(f"{label}: timestamp is not UTC")
    return value


def _identity(value: object, label: str) -> Mapping[str, Any]:
    record = _keys(value, {"path", "size_bytes", "sha256"}, label)
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
        or type(record["sha256"]) is not str
        or HEX64_RE.fullmatch(record["sha256"]) is None
    ):
        raise VerificationError(f"{label}: invalid byte identity")
    return record


def _same_identity(left: object, right: object, label: str) -> None:
    if dict(_identity(left, f"{label} left")) != dict(_identity(right, f"{label} right")):
        raise VerificationError(f"{label}: byte identity mismatch")


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


def snapshot_regular(
    path: Path,
    *,
    expected_identity: Mapping[str, object] | None = None,
    limit: int = MAX_JSON_BYTES,
) -> tuple[bytes, dict[str, object]]:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise VerificationError(f"input path is unavailable: {absolute}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise VerificationError(f"input path contains a symlink: {absolute}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise VerificationError(f"cannot open input: {absolute}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise VerificationError(f"input is not a bounded regular file: {absolute}")
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, min(1 << 20, limit - total + 1))
            if not block:
                break
            total += len(block)
            if total > limit:
                raise VerificationError(f"input exceeds fixed cap: {absolute}")
            chunks.append(block)
        after = os.fstat(descriptor)
        if _snapshot_signature(before) != _snapshot_signature(after):
            raise VerificationError(f"input descriptor drifted: {absolute}")
    finally:
        os.close(descriptor)
    try:
        named = os.stat(absolute, follow_symlinks=False)
    except OSError as exc:
        raise VerificationError(f"input path disappeared: {absolute}") from exc
    if _snapshot_signature(after) != _snapshot_signature(named):
        raise VerificationError(f"input path drifted after read: {absolute}")
    raw = b"".join(chunks)
    identity: dict[str, object] = {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if expected_identity is not None:
        _same_identity(identity, expected_identity, f"snapshot {absolute}")
    return raw, identity


def _write_exclusive(path: Path, raw: bytes) -> dict[str, object]:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parent.parts[1:]:
        current /= part
        metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode):
            raise VerificationError(f"output parent is a symlink: {absolute}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags, 0o600)
    except OSError as exc:
        raise VerificationError(f"cannot create output exclusively: {absolute}") from exc
    try:
        view = memoryview(raw)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise VerificationError(f"short output write: {absolute}")
            view = view[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _, identity = snapshot_regular(absolute)
    return identity


def _loads_bound(
    raw: bytes,
    identity: Mapping[str, object],
    label: str,
) -> Mapping[str, Any]:
    checked = _identity(identity, f"{label} identity")
    if len(raw) != checked["size_bytes"] or hashlib.sha256(raw).hexdigest() != checked["sha256"]:
        raise VerificationError(f"{label}: raw bytes do not match detached identity")
    return _mapping(_strict_json(raw, label), label)


def _validate_selection(
    raw: bytes,
    identity: Mapping[str, object],
) -> Mapping[str, Any]:
    record = _keys(
        _loads_bound(raw, identity, "selection"),
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
        "selection",
    )
    if (
        record["schema_version"] != SELECTION_SCHEMA
        or record["purpose"] != "gate1_v4_child_suite"
        or type(record["campaign_id"]) is not str
        or HEX64_RE.fullmatch(record["campaign_id"]) is None
        or type(record["package_id"]) is not str
        or HEX64_RE.fullmatch(record["package_id"]) is None
        or type(record["repository_head"]) is not str
        or re.fullmatch(r"[0-9a-f]{40}", record["repository_head"]) is None
        or type(record["selection_id"]) is not str
        or HEX64_RE.fullmatch(record["selection_id"]) is None
        or type(record["run_nonce"]) is not str
        or not record["run_nonce"]
    ):
        raise VerificationError("selection scalar authority drifted")
    _utc(record["created_at_utc"], "selection created_at_utc")
    _identity(record["campaign_root_identity"], "campaign root identity")
    manager_epoch = _mapping(record["manager_epoch"], "manager epoch")
    if not manager_epoch:
        raise VerificationError("selection manager epoch is empty")
    if record["resource_contract"] != RESOURCE_CONTRACT:
        raise VerificationError("selection resource contract drifted")
    for group in ("tools", "inputs"):
        values = _mapping(record[group], f"selection {group}")
        if not values:
            raise VerificationError(f"selection {group} is empty")
        for role, item in values.items():
            if type(role) is not str or not role:
                raise VerificationError(f"selection {group} role is invalid")
            _identity(item, f"selection {group}.{role}")
    units = _keys(record["units"], set(UNIT_SLOTS), "selection units")
    token = record["campaign_id"][:12]
    seen_paths: set[str] = set()
    for slot in UNIT_SLOTS:
        unit = _keys(
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
            f"selection unit {slot}",
        )
        profile = "synthetic" if slot in SYNTHETIC_SLOTS else "formal"
        if (
            unit["slot"] != slot
            or unit["unit_name"] != f"cuts-g1v4-{token}-{slot}.service"
            or UNIT_RE.fullmatch(str(unit["unit_name"])) is None
            or unit["contract_profile"] != profile
        ):
            raise VerificationError(f"selection unit {slot} drifted")
        attempt = Path(str(unit["attempt_dir"]))
        raw_dir = Path(str(unit["raw_dir"]))
        terminal_dir = Path(str(unit["terminal_dir"]))
        result = Path(str(unit["result_path"]))
        checkpoints = _keys(
            unit["epoch_checkpoint_paths"],
            {
                "cleanup",
                "detached-replay",
                "prelaunch",
                "preterminal",
                "terminal",
            },
            f"selection unit {slot} manager epoch checkpoints",
        )
        if not all(item.is_absolute() for item in (attempt, raw_dir, terminal_dir, result)):
            raise VerificationError(f"selection unit {slot} path is not absolute")
        if (
            raw_dir.parent != attempt
            or terminal_dir.parent != attempt
            or result.parent != attempt
            or raw_dir.name != "raw"
            or terminal_dir.name != "terminal"
        ):
            raise VerificationError(f"selection unit {slot} path topology drifted")
        for phase, checkpoint_path in checkpoints.items():
            if Path(str(checkpoint_path)) != (attempt / "authority" / f"manager-epoch-{phase}.json"):
                raise VerificationError(f"selection unit {slot} manager epoch path drifted: {phase}")
        for item in (attempt, raw_dir, terminal_dir, result):
            text = str(item)
            if text in seen_paths:
                raise VerificationError("selection unit paths overlap")
            seen_paths.add(text)
    body = dict(record)
    body.pop("selection_id")
    if _digest(body) != record["selection_id"]:
        raise VerificationError("selection_id reseal failed")
    return record


def _unit(selection: Mapping[str, Any], slot: str) -> Mapping[str, Any]:
    if slot not in UNIT_SLOTS:
        raise VerificationError("unit slot is not pre-registered")
    return _mapping(selection["units"][slot], f"selection unit {slot}")


def _selection_join(
    record: Mapping[str, Any],
    selection: Mapping[str, Any],
    selection_identity: Mapping[str, object],
    slot: str,
    label: str,
) -> None:
    unit = _unit(selection, slot)
    _same_identity(record.get("selection_identity"), selection_identity, f"{label} selection")
    expected = {
        "campaign_id": selection["campaign_id"],
        "run_nonce": selection["run_nonce"],
        "selection_id": selection["selection_id"],
        "manager_epoch_digest": _digest(selection["manager_epoch"]),
        "unit_slot": slot,
        "unit_name": unit["unit_name"],
    }
    for name, value in expected.items():
        if record.get(name) != value:
            raise VerificationError(f"{label}: {name} join drifted")


def _decode_command(
    value: object,
    expected_argv: Sequence[str],
    label: str,
) -> tuple[bytes, bytes]:
    record = _keys(
        value,
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
    if record["argv"] != list(expected_argv) or type(record["exit_code"]) is not int:
        raise VerificationError(f"{label}: argv/exit drifted")
    try:
        stdout = base64.b64decode(record["stdout_base64"], validate=True)
        stderr = base64.b64decode(record["stderr_base64"], validate=True)
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"{label}: invalid raw bytes") from exc
    if (
        hashlib.sha256(stdout).hexdigest() != record["stdout_sha256"]
        or hashlib.sha256(stderr).hexdigest() != record["stderr_sha256"]
    ):
        raise VerificationError(f"{label}: raw command hash drifted")
    return stdout, stderr


def _show_argv(unit_name: str, fields: Sequence[str]) -> tuple[str, ...]:
    return (
        SYSTEMCTL,
        "--user",
        "show",
        "--no-pager",
        *(f"--property={field}" for field in fields),
        unit_name,
    )


def _load_state_argv(unit_name: str) -> tuple[str, ...]:
    return (
        SYSTEMCTL,
        "--user",
        "show",
        unit_name,
        "--property=LoadState",
        "--value",
    )


def _parse_show(
    command: object,
    raw_fields: object,
    *,
    unit_name: str,
    fields: Sequence[str],
    label: str,
) -> Mapping[str, str]:
    stdout, stderr = _decode_command(command, _show_argv(unit_name, fields), f"{label} command")
    raw = _keys(raw_fields, set(fields), f"{label} raw")
    if stderr:
        raise VerificationError(f"{label}: systemctl show wrote stderr")
    try:
        lines = stdout.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise VerificationError(f"{label}: systemctl show output is not UTF-8") from exc
    parsed: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            raise VerificationError(f"{label}: malformed raw systemctl line")
        name, item = line.split("=", 1)
        if name in parsed:
            raise VerificationError(f"{label}: duplicate raw systemctl field")
        parsed[name] = item
    if parsed != dict(raw):
        raise VerificationError(f"{label}: parsed fields do not reproduce raw stdout")
    command_record = _mapping(command, f"{label} command")
    if command_record["exit_code"] != 0:
        raise VerificationError(f"{label}: systemctl show failed")
    if any(type(value) is not str for value in raw.values()):
        raise VerificationError(f"{label}: non-string systemd property")
    return raw


def _decode_cgroup(value: object) -> dict[str, bytes]:
    record = _keys(value, set(CGROUP_RAW_FIELDS), "preterminal cgroup_raw")
    result: dict[str, bytes] = {}
    for field in CGROUP_RAW_FIELDS:
        item = _keys(record[field], {"base64", "sha256"}, f"cgroup {field}")
        try:
            raw = base64.b64decode(item["base64"], validate=True)
        except (TypeError, ValueError) as exc:
            raise VerificationError(f"cgroup {field}: invalid base64") from exc
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise VerificationError(f"cgroup {field}: raw hash drifted")
        result[field] = raw
    return result


def _decimal_raw(raw: bytes, label: str) -> int:
    text = raw.decode("ascii").strip()
    if not text.isdigit():
        raise VerificationError(f"{label}: expected decimal integer")
    return int(text)


def _systemd_duration_usec(value: str, label: str) -> int:
    if value.isdigit():
        return int(value)
    units = {
        "us": Decimal(1),
        "ms": Decimal(1_000),
        "s": Decimal(1_000_000),
        "min": Decimal(60_000_000),
        "h": Decimal(3_600_000_000),
        "d": Decimal(86_400_000_000),
    }
    total = Decimal(0)
    for token in value.split():
        match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(us|ms|s|min|h|d)", token)
        if match is None:
            raise VerificationError(f"{label}: unsupported systemd duration")
        try:
            total += Decimal(match.group(1)) * units[match.group(2)]
        except InvalidOperation as exc:
            raise VerificationError(f"{label}: invalid systemd duration") from exc
    if total != total.to_integral_value() or total < 0:
        raise VerificationError(f"{label}: non-integral systemd duration")
    return int(total)


def _systemd_integer(value: str, label: str, *, minimum: int = 0) -> int:
    if not value.isdigit():
        raise VerificationError(f"{label}: expected decimal integer")
    return _integer(int(value), label, minimum)


def _kv_ints(raw: bytes, label: str) -> dict[str, int]:
    result: dict[str, int] = {}
    try:
        for line in raw.decode("ascii").splitlines():
            name, value = line.split()
            if name in result or not value.isdigit():
                raise ValueError
            result[name] = int(value)
    except (UnicodeDecodeError, ValueError) as exc:
        raise VerificationError(f"{label}: malformed key/value integer data") from exc
    return result


def _pid_lines(raw: bytes) -> list[int]:
    result: list[int] = []
    try:
        for line in raw.decode("ascii").splitlines():
            if not line.isdigit():
                raise ValueError
            result.append(int(line))
    except (UnicodeDecodeError, ValueError) as exc:
        raise VerificationError("cgroup.procs is malformed") from exc
    return result


def _validate_inner(
    value: object,
    selection: Mapping[str, Any],
    selection_identity: Mapping[str, object],
    slot: str,
) -> Mapping[str, Any]:
    inner = _keys(
        value,
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
            "contract_profile",
            "payload_argv",
            "supervisor_pid",
            "supervisor_starttime",
            "payload_pid",
            "payload_starttime",
            "payload_spawned_monotonic_ns",
            "payload_reaped_monotonic_ns",
            "payload_reaped",
            "payload_timed_out",
            "payload_returncode",
            "waitid",
            "payload_seal_identity",
            "payload_result_identity",
            "keeper_pid",
            "keeper_starttime",
            "keeper_ready_monotonic_ns",
        },
        "inner lifecycle",
    )
    if inner["schema_version"] != INNER_SCHEMA:
        raise VerificationError("inner lifecycle schema drifted")
    _utc(inner["created_at_utc"], "inner created_at_utc")
    _selection_join(inner, selection, selection_identity, slot, "inner lifecycle")
    unit = _unit(selection, slot)
    if (
        inner["contract_profile"] != unit["contract_profile"]
        or type(inner["payload_argv"]) is not list
        or not inner["payload_argv"]
        or any(type(item) is not str or not item for item in inner["payload_argv"])
        or type(inner["invocation_id"]) is not str
        or HEX32_RE.fullmatch(inner["invocation_id"]) is None
        or inner["payload_reaped"] is not True
        or inner["payload_timed_out"] is not False
        or inner["payload_returncode"] != EXPECTED_RETURNCODE[slot]
    ):
        raise VerificationError("inner payload terminal semantics failed")
    for name in (
        "supervisor_pid",
        "supervisor_starttime",
        "payload_pid",
        "payload_starttime",
        "payload_spawned_monotonic_ns",
        "payload_reaped_monotonic_ns",
        "keeper_pid",
        "keeper_starttime",
        "keeper_ready_monotonic_ns",
    ):
        _integer(inner[name], f"inner {name}", 1)
    if (
        inner["keeper_pid"] != inner["supervisor_pid"]
        or inner["keeper_starttime"] != inner["supervisor_starttime"]
        or not (
            inner["payload_spawned_monotonic_ns"]
            <= inner["payload_reaped_monotonic_ns"]
            <= inner["keeper_ready_monotonic_ns"]
        )
    ):
        raise VerificationError("inner supervisor/keeper timeline failed")
    waitid = _keys(
        inner["waitid"],
        {"si_pid", "si_uid", "si_signo", "si_status", "si_code"},
        "inner waitid",
    )
    if waitid["si_pid"] != inner["payload_pid"] or waitid["si_status"] != abs(inner["payload_returncode"]):
        raise VerificationError("inner waitid does not join payload")
    _identity(inner["payload_seal_identity"], "payload seal identity")
    _identity(inner["payload_result_identity"], "payload result identity")
    return inner


def _validate_preterminal(
    value: object,
    selection: Mapping[str, Any],
    selection_identity: Mapping[str, object],
    slot: str,
    inner: Mapping[str, Any],
    inner_identity: Mapping[str, object],
) -> tuple[Mapping[str, Any], dict[str, object]]:
    pre = _keys(
        value,
        {
            "schema_version",
            "captured_at_utc",
            "captured_monotonic_ns",
            "selection_identity",
            "campaign_id",
            "run_nonce",
            "selection_id",
            "manager_epoch_digest",
            "unit_slot",
            "unit_name",
            "invocation_id",
            "inner_identity",
            "supervisor_pid",
            "supervisor_starttime",
            "payload_pid",
            "payload_starttime",
            "payload_reaped",
            "payload_returncode",
            "keeper_pid",
            "keeper_starttime",
            "keeper_current_starttime",
            "payload_current_starttime",
            "control_group",
            "systemd_command",
            "systemd_raw",
            "cgroup_raw",
            "release_created",
        },
        "preterminal",
    )
    if pre["schema_version"] != PRETERMINAL_SCHEMA:
        raise VerificationError("preterminal schema drifted")
    _utc(pre["captured_at_utc"], "preterminal captured_at_utc")
    _selection_join(pre, selection, selection_identity, slot, "preterminal")
    _same_identity(pre["inner_identity"], inner_identity, "preterminal inner")
    if (
        pre["invocation_id"] != inner["invocation_id"]
        or pre["supervisor_pid"] != inner["supervisor_pid"]
        or pre["supervisor_starttime"] != inner["supervisor_starttime"]
        or pre["payload_pid"] != inner["payload_pid"]
        or pre["payload_starttime"] != inner["payload_starttime"]
        or pre["payload_reaped"] is not True
        or pre["payload_returncode"] != inner["payload_returncode"]
        or pre["keeper_pid"] != inner["keeper_pid"]
        or pre["keeper_starttime"] != inner["keeper_starttime"]
        or pre["keeper_current_starttime"] != inner["keeper_starttime"]
        or pre["payload_current_starttime"] is not None
        or pre["release_created"] is not False
    ):
        raise VerificationError("preterminal payload/keeper join failed")
    captured = _integer(pre["captured_monotonic_ns"], "preterminal monotonic", 1)
    if captured < inner["keeper_ready_monotonic_ns"]:
        raise VerificationError("preterminal capture precedes keeper readiness")
    unit = _unit(selection, slot)
    systemd = _parse_show(
        pre["systemd_command"],
        pre["systemd_raw"],
        unit_name=unit["unit_name"],
        fields=SYSTEMD_PRETERMINAL_FIELDS,
        label="preterminal systemd",
    )
    profile = RESOURCE_CONTRACT["profiles"][unit["contract_profile"]]
    expected_systemd = {
        "ActiveState": "active",
        "SubState": "running",
        "MainPID": str(inner["keeper_pid"]),
        "InvocationID": inner["invocation_id"],
        "ControlGroup": pre["control_group"],
        "MemoryHigh": str(MEMORY_HIGH),
        "MemoryMax": str(MEMORY_MAX),
        "MemorySwapMax": str(MEMORY_SWAP_MAX),
        "OOMPolicy": "continue",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
    }
    if any(systemd[name] != expected for name, expected in expected_systemd.items()):
        raise VerificationError("preterminal systemd contract drifted")
    if (
        _systemd_duration_usec(
            systemd["RuntimeMaxUSec"],
            "preterminal RuntimeMaxUSec",
        )
        != profile["runtime_max_seconds"] * 1_000_000
    ):
        raise VerificationError("preterminal RuntimeMaxUSec drifted")
    start_usec = _systemd_integer(
        systemd["ExecMainStartTimestampMonotonic"],
        "preterminal ExecMainStartTimestampMonotonic",
        minimum=1,
    )
    if not str(pre["control_group"]).startswith("/"):
        raise VerificationError("preterminal cgroup path is invalid")
    cgroup = _decode_cgroup(pre["cgroup_raw"])
    if (
        _decimal_raw(cgroup["memory.high"], "memory.high") != MEMORY_HIGH
        or _decimal_raw(cgroup["memory.max"], "memory.max") != MEMORY_MAX
        or _decimal_raw(cgroup["memory.swap.max"], "memory.swap.max") != MEMORY_SWAP_MAX
    ):
        raise VerificationError("preterminal cgroup limits drifted")
    current = _decimal_raw(cgroup["memory.current"], "memory.current")
    peak = _decimal_raw(cgroup["memory.peak"], "memory.peak")
    swap_current = _decimal_raw(cgroup["memory.swap.current"], "memory.swap.current")
    swap_peak = _decimal_raw(cgroup["memory.swap.peak"], "memory.swap.peak")
    if current > peak or peak > MEMORY_MAX or swap_current > swap_peak or swap_peak > MEMORY_SWAP_MAX:
        raise VerificationError("preterminal current/peak accounting is impossible")
    memory_events = _kv_ints(cgroup["memory.events"], "memory.events")
    local_events = _kv_ints(cgroup["memory.events.local"], "memory.events.local")
    memory_event_keys = set(memory_events)
    local_event_keys = set(local_events)
    supported_event_keys = {
        MEMORY_EVENT_REQUIRED_KEYS,
        MEMORY_EVENT_REQUIRED_KEYS | MEMORY_EVENT_OPTIONAL_ZERO_KEYS,
    }
    if (
        frozenset(memory_event_keys) not in supported_event_keys
        or frozenset(local_event_keys) not in supported_event_keys
        or memory_event_keys != local_event_keys
    ):
        raise VerificationError("memory event field set drifted")
    for values in (memory_events, local_events):
        if any(values[name] != 0 for name in ("max", "oom", "oom_kill", "oom_group_kill")):
            raise VerificationError("OOM or hard memory limit event observed")
        if any(values[name] != 0 for name in MEMORY_EVENT_OPTIONAL_ZERO_KEYS if name in values):
            raise VerificationError("unsupported nonzero optional memory event observed")
    procs = _pid_lines(cgroup["cgroup.procs"])
    if procs != [inner["keeper_pid"]]:
        raise VerificationError("preterminal cgroup does not contain exactly the keeper")
    cgroup_events = _kv_ints(cgroup["cgroup.events"], "cgroup.events")
    if set(cgroup_events) != {"populated", "frozen"} or cgroup_events != {"populated": 1, "frozen": 0}:
        raise VerificationError("preterminal cgroup.events semantics failed")
    derived = {
        "contract_profile": unit["contract_profile"],
        "payload_returncode": inner["payload_returncode"],
        "payload_timed_out": False,
        "payload_duration_ns": inner["payload_reaped_monotonic_ns"] - inner["payload_spawned_monotonic_ns"],
        "keeper_only": True,
        "memory_current_bytes": current,
        "memory_peak_bytes": peak,
        "swap_current_bytes": swap_current,
        "swap_peak_bytes": swap_peak,
        "memory_events": memory_events,
        "memory_events_local": local_events,
        "cgroup_events": cgroup_events,
        "resource_limits": {
            "memory_high_bytes": MEMORY_HIGH,
            "memory_max_bytes": MEMORY_MAX,
            "memory_swap_max_bytes": MEMORY_SWAP_MAX,
        },
        "systemd_contract": expected_systemd,
        "systemd_runtime_max_usec": profile["runtime_max_seconds"] * 1_000_000,
        "systemd_exec_start_monotonic_usec": start_usec,
        "invocation_id": inner["invocation_id"],
        "control_group": pre["control_group"],
        "preterminal_monotonic_ns": captured,
    }
    return pre, derived


def verify_preterminal_bytes(
    *,
    selection_raw: bytes,
    selection_identity: Mapping[str, object],
    unit_slot: str,
    inner_raw: bytes,
    inner_identity: Mapping[str, object],
    preterminal_raw: bytes,
    preterminal_identity: Mapping[str, object],
    verifier_identity: Mapping[str, object],
    created_at_utc: str,
) -> dict[str, object]:
    selection = _validate_selection(selection_raw, selection_identity)
    _utc(created_at_utc, "resource verification created_at_utc")
    inner = _validate_inner(
        _loads_bound(inner_raw, inner_identity, "inner lifecycle"),
        selection,
        selection_identity,
        unit_slot,
    )
    _, derived = _validate_preterminal(
        _loads_bound(preterminal_raw, preterminal_identity, "preterminal"),
        selection,
        selection_identity,
        unit_slot,
        inner,
        inner_identity,
    )
    _identity(verifier_identity, "resource verifier identity")
    _same_identity(
        verifier_identity,
        selection["tools"].get("resource_verifier_v4"),
        "selected resource verifier tool",
    )
    return {
        "schema_version": RESOURCE_SCHEMA,
        "status": "PASS",
        "verdict": "RESOURCE_PRETERMINAL_PASS",
        "created_at_utc": created_at_utc,
        "selection_identity": dict(selection_identity),
        "campaign_id": selection["campaign_id"],
        "run_nonce": selection["run_nonce"],
        "selection_id": selection["selection_id"],
        "manager_epoch_digest": _digest(selection["manager_epoch"]),
        "unit_slot": unit_slot,
        "unit_name": selection["units"][unit_slot]["unit_name"],
        "invocation_id": inner["invocation_id"],
        "inner_identity": dict(inner_identity),
        "preterminal_identity": dict(preterminal_identity),
        "verifier_identity": dict(verifier_identity),
        "derived": derived,
        "release_authorized": True,
        "global_claim_authorized": False,
    }


def build_release_token(
    receipt: Mapping[str, Any],
    receipt_identity: Mapping[str, object],
    *,
    released_monotonic_ns: int,
    created_at_utc: str,
) -> dict[str, object]:
    if (
        receipt.get("schema_version") != RESOURCE_SCHEMA
        or receipt.get("status") != "PASS"
        or receipt.get("verdict") != "RESOURCE_PRETERMINAL_PASS"
        or receipt.get("release_authorized") is not True
    ):
        raise VerificationError("resource receipt cannot authorize release")
    _utc(created_at_utc, "release created_at_utc")
    _identity(receipt_identity, "resource receipt identity")
    _integer(released_monotonic_ns, "release monotonic", 1)
    return {
        "schema_version": RELEASE_SCHEMA,
        "created_at_utc": created_at_utc,
        "selection_identity": dict(receipt["selection_identity"]),
        "campaign_id": receipt["campaign_id"],
        "run_nonce": receipt["run_nonce"],
        "selection_id": receipt["selection_id"],
        "manager_epoch_digest": receipt["manager_epoch_digest"],
        "unit_slot": receipt["unit_slot"],
        "unit_name": receipt["unit_name"],
        "invocation_id": receipt["invocation_id"],
        "inner_identity": dict(receipt["inner_identity"]),
        "preterminal_identity": dict(receipt["preterminal_identity"]),
        "resource_verification_identity": dict(receipt_identity),
        "verdict": "RESOURCE_PRETERMINAL_PASS",
        "released_monotonic_ns": released_monotonic_ns,
    }


def _validate_resource_receipt(
    value: object,
    expected: Mapping[str, Any],
    identity: Mapping[str, object],
) -> Mapping[str, Any]:
    receipt = _keys(
        value,
        {
            "schema_version",
            "status",
            "verdict",
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
            "verifier_identity",
            "derived",
            "release_authorized",
            "global_claim_authorized",
        },
        "resource receipt",
    )
    replay = dict(expected)
    _utc(receipt["created_at_utc"], "resource receipt created_at_utc")
    replay["created_at_utc"] = receipt["created_at_utc"]
    if receipt != replay:
        raise VerificationError("resource receipt semantic replay drifted")
    _identity(identity, "resource receipt identity")
    return receipt


def _validate_release(
    value: object,
    receipt: Mapping[str, Any],
    receipt_identity: Mapping[str, object],
) -> Mapping[str, Any]:
    release = _keys(
        value,
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
    expected = build_release_token(
        receipt,
        receipt_identity,
        released_monotonic_ns=_integer(
            release["released_monotonic_ns"],
            "release monotonic",
            1,
        ),
        created_at_utc=str(release["created_at_utc"]),
    )
    if release != expected:
        raise VerificationError("release token semantic replay drifted")
    if release["released_monotonic_ns"] <= receipt["derived"]["preterminal_monotonic_ns"]:
        raise VerificationError("release does not follow preterminal capture")
    return release


def _validate_terminal(
    value: object,
    selection: Mapping[str, Any],
    selection_identity: Mapping[str, object],
    slot: str,
    inner: Mapping[str, Any],
    inner_identity: Mapping[str, object],
    preterminal_identity: Mapping[str, object],
    resource_receipt: Mapping[str, Any],
    release: Mapping[str, Any],
    release_identity: Mapping[str, object],
) -> tuple[Mapping[str, Any], int]:
    terminal = _keys(
        value,
        {
            "schema_version",
            "captured_at_utc",
            "captured_monotonic_ns",
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
            "release_identity",
            "preterminal_control_group",
            "terminal_control_group_used_as_cleanup_evidence",
            "systemd_command",
            "systemd_raw",
        },
        "terminal",
    )
    if terminal["schema_version"] != TERMINAL_SCHEMA:
        raise VerificationError("terminal schema drifted")
    _utc(terminal["captured_at_utc"], "terminal captured_at_utc")
    _selection_join(terminal, selection, selection_identity, slot, "terminal")
    _same_identity(terminal["inner_identity"], inner_identity, "terminal inner")
    _same_identity(
        terminal["preterminal_identity"],
        preterminal_identity,
        "terminal preterminal",
    )
    _same_identity(terminal["release_identity"], release_identity, "terminal release")
    if (
        terminal["invocation_id"] != inner["invocation_id"]
        or terminal["terminal_control_group_used_as_cleanup_evidence"] is not False
    ):
        raise VerificationError("terminal invocation/cleanup boundary drifted")
    unit = _unit(selection, slot)
    systemd = _parse_show(
        terminal["systemd_command"],
        terminal["systemd_raw"],
        unit_name=unit["unit_name"],
        fields=SYSTEMD_TERMINAL_FIELDS,
        label="terminal systemd",
    )
    profile = RESOURCE_CONTRACT["profiles"][unit["contract_profile"]]
    contract = {
        "MemoryHigh": str(MEMORY_HIGH),
        "MemoryMax": str(MEMORY_MAX),
        "MemorySwapMax": str(MEMORY_SWAP_MAX),
        "OOMPolicy": "continue",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
        "InvocationID": inner["invocation_id"],
    }
    if any(systemd[name] != expected for name, expected in contract.items()):
        raise VerificationError("terminal systemd contract drifted")
    if (
        _systemd_duration_usec(
            systemd["RuntimeMaxUSec"],
            "terminal RuntimeMaxUSec",
        )
        != profile["runtime_max_seconds"] * 1_000_000
    ):
        raise VerificationError("terminal RuntimeMaxUSec drifted")
    terminal_start_usec = _systemd_integer(
        systemd["ExecMainStartTimestampMonotonic"],
        "terminal ExecMainStartTimestampMonotonic",
        minimum=1,
    )
    terminal_exit_usec = _systemd_integer(
        systemd["ExecMainExitTimestampMonotonic"],
        "terminal ExecMainExitTimestampMonotonic",
        minimum=1,
    )
    if (
        terminal_start_usec != resource_receipt["derived"]["systemd_exec_start_monotonic_usec"]
        or terminal_exit_usec < terminal_start_usec
    ):
        raise VerificationError("terminal systemd monotonic interval is invalid")
    if slot == "q-postseal-fail":
        expected_terminal = {
            "ActiveState": "failed",
            "SubState": "failed",
            "Result": "exit-code",
            "ExecMainCode": "1",
            "ExecMainStatus": "7",
            "MainPID": "0",
        }
    else:
        expected_terminal = {
            "ActiveState": "active",
            "SubState": "exited",
            "Result": "success",
            "ExecMainCode": "1",
            "ExecMainStatus": "0",
            "MainPID": "0",
        }
    if any(systemd[name] != expected for name, expected in expected_terminal.items()):
        raise VerificationError("terminal payload status was not preserved")
    captured = _integer(terminal["captured_monotonic_ns"], "terminal monotonic", 1)
    if captured <= release["released_monotonic_ns"]:
        raise VerificationError("terminal capture does not follow release")
    return terminal, captured


def _validate_cleanup(
    value: object,
    selection: Mapping[str, Any],
    selection_identity: Mapping[str, object],
    slot: str,
    inner: Mapping[str, Any],
    inner_identity: Mapping[str, object],
    terminal: Mapping[str, Any],
    terminal_identity: Mapping[str, object],
    terminal_monotonic_ns: int,
) -> tuple[Mapping[str, Any], int]:
    cleanup = _keys(
        value,
        {
            "schema_version",
            "captured_at_utc",
            "captured_monotonic_ns",
            "selection_identity",
            "campaign_id",
            "run_nonce",
            "selection_id",
            "manager_epoch_digest",
            "unit_slot",
            "unit_name",
            "invocation_id",
            "inner_identity",
            "terminal_identity",
            "cleanup_commands",
            "load_state_command",
            "unit_absent",
            "payload_pid",
            "payload_current_starttime",
            "keeper_pid",
            "keeper_current_starttime",
            "preterminal_control_group",
            "cgroup_exists",
            "terminal_control_group_used_as_cleanup_evidence",
        },
        "cleanup",
    )
    if cleanup["schema_version"] != CLEANUP_SCHEMA:
        raise VerificationError("cleanup schema drifted")
    _utc(cleanup["captured_at_utc"], "cleanup captured_at_utc")
    _selection_join(cleanup, selection, selection_identity, slot, "cleanup")
    _same_identity(cleanup["inner_identity"], inner_identity, "cleanup inner")
    _same_identity(cleanup["terminal_identity"], terminal_identity, "cleanup terminal")
    for name in ("payload_current_starttime", "keeper_current_starttime"):
        if cleanup[name] is not None:
            _integer(cleanup[name], f"cleanup {name}", 1)
    if (
        cleanup["invocation_id"] != inner["invocation_id"]
        or cleanup["payload_pid"] != inner["payload_pid"]
        or cleanup["keeper_pid"] != inner["keeper_pid"]
        or cleanup["payload_current_starttime"] == inner["payload_starttime"]
        or cleanup["keeper_current_starttime"] == inner["keeper_starttime"]
        or cleanup["preterminal_control_group"] != terminal["preterminal_control_group"]
        or cleanup["cgroup_exists"] is not False
        or cleanup["unit_absent"] is not True
        or cleanup["terminal_control_group_used_as_cleanup_evidence"] is not False
    ):
        raise VerificationError("cleanup process/cgroup absence failed")
    unit_name = _unit(selection, slot)["unit_name"]
    commands = cleanup["cleanup_commands"]
    if type(commands) is not list or len(commands) != 2:
        raise VerificationError("cleanup command list drifted")
    expected_commands = (
        (SYSTEMCTL, "--user", "stop", unit_name),
        (SYSTEMCTL, "--user", "reset-failed", unit_name),
    )
    for index, argv in enumerate(expected_commands):
        stdout, stderr = _decode_command(commands[index], argv, f"cleanup command {index}")
        if index == 0:
            if commands[index]["exit_code"] != 0 or stdout or stderr:
                raise VerificationError("cleanup stop command failed")
        else:
            expected_not_loaded = (
                f"Failed to reset failed state of unit {unit_name}: Unit {unit_name} not loaded.\n"
            ).encode()
            reset_ok = (commands[index]["exit_code"] == 0 and stdout == b"" and stderr == b"") or (
                commands[index]["exit_code"] == 1 and stdout == b"" and stderr == expected_not_loaded
            )
            if not reset_ok:
                raise VerificationError("cleanup reset-failed command failed")
    load_stdout, load_stderr = _decode_command(
        cleanup["load_state_command"],
        _load_state_argv(unit_name),
        "cleanup load-state command",
    )
    if cleanup["load_state_command"]["exit_code"] != 0 or load_stdout != b"not-found\n" or load_stderr:
        raise VerificationError("cleanup unit absence was not established")
    captured = _integer(cleanup["captured_monotonic_ns"], "cleanup monotonic", 1)
    if captured <= terminal_monotonic_ns:
        raise VerificationError("cleanup capture does not follow terminal")
    return cleanup, captured


def verify_detached_bytes(
    *,
    selection_raw: bytes,
    selection_identity: Mapping[str, object],
    unit_slot: str,
    inner_raw: bytes,
    inner_identity: Mapping[str, object],
    preterminal_raw: bytes,
    preterminal_identity: Mapping[str, object],
    resource_raw: bytes,
    resource_identity: Mapping[str, object],
    release_raw: bytes,
    release_identity: Mapping[str, object],
    terminal_raw: bytes,
    terminal_identity: Mapping[str, object],
    cleanup_raw: bytes,
    cleanup_identity: Mapping[str, object],
    verifier_identity: Mapping[str, object],
    created_at_utc: str,
) -> dict[str, object]:
    selection = _validate_selection(selection_raw, selection_identity)
    _utc(created_at_utc, "detached created_at_utc")
    inner_value = _validate_inner(
        _loads_bound(inner_raw, inner_identity, "inner lifecycle"),
        selection,
        selection_identity,
        unit_slot,
    )
    _, derived = _validate_preterminal(
        _loads_bound(preterminal_raw, preterminal_identity, "preterminal"),
        selection,
        selection_identity,
        unit_slot,
        inner_value,
        inner_identity,
    )
    resource_value = _loads_bound(resource_raw, resource_identity, "resource receipt")
    resource_created_at = _utc(
        resource_value.get("created_at_utc"),
        "resource receipt created_at_utc",
    )
    expected_receipt = verify_preterminal_bytes(
        selection_raw=selection_raw,
        selection_identity=selection_identity,
        unit_slot=unit_slot,
        inner_raw=inner_raw,
        inner_identity=inner_identity,
        preterminal_raw=preterminal_raw,
        preterminal_identity=preterminal_identity,
        verifier_identity=verifier_identity,
        created_at_utc=resource_created_at,
    )
    receipt = _validate_resource_receipt(
        resource_value,
        expected_receipt,
        resource_identity,
    )
    release = _validate_release(
        _loads_bound(release_raw, release_identity, "release token"),
        receipt,
        resource_identity,
    )
    terminal, terminal_ns = _validate_terminal(
        _loads_bound(terminal_raw, terminal_identity, "terminal"),
        selection,
        selection_identity,
        unit_slot,
        inner_value,
        inner_identity,
        preterminal_identity,
        receipt,
        release,
        release_identity,
    )
    _, cleanup_ns = _validate_cleanup(
        _loads_bound(cleanup_raw, cleanup_identity, "cleanup"),
        selection,
        selection_identity,
        unit_slot,
        inner_value,
        inner_identity,
        terminal,
        terminal_identity,
        terminal_ns,
    )
    _identity(verifier_identity, "verifier identity")
    return {
        "schema_version": DETACHED_SCHEMA,
        "status": "PASS",
        "verdict": "LIFECYCLE_DETACHED_PASS",
        "terminal_class": EXPECTED_TERMINAL_CLASS[unit_slot],
        "created_at_utc": created_at_utc,
        "selection_identity": dict(selection_identity),
        "campaign_id": selection["campaign_id"],
        "run_nonce": selection["run_nonce"],
        "selection_id": selection["selection_id"],
        "manager_epoch_digest": _digest(selection["manager_epoch"]),
        "unit_slot": unit_slot,
        "unit_name": selection["units"][unit_slot]["unit_name"],
        "inputs": {
            "inner": dict(inner_identity),
            "preterminal": dict(preterminal_identity),
            "resource_verification": dict(resource_identity),
            "release": dict(release_identity),
            "terminal": dict(terminal_identity),
            "cleanup": dict(cleanup_identity),
        },
        "verifier_identity": dict(verifier_identity),
        "derived": {
            **derived,
            "released_monotonic_ns": release["released_monotonic_ns"],
            "terminal_monotonic_ns": terminal_ns,
            "cleanup_monotonic_ns": cleanup_ns,
            "payload_status_preserved": True,
            "unit_absent": True,
            "cgroup_absent": True,
            "remaining_pids": [],
        },
        "mechanism_credible_authorized": False,
        "organic_arm_launch_authorized": False,
        "global_claim_authorized": False,
    }


def _identity_for(path: Path, size: int, digest: str) -> dict[str, object]:
    return {"path": str(path.absolute()), "size_bytes": size, "sha256": digest}


def _load(path: Path, size: int, digest: str, label: str) -> tuple[bytes, dict[str, object]]:
    identity = _identity_for(path, size, digest)
    return snapshot_regular(path, expected_identity=identity)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    def byte_input(target: argparse.ArgumentParser, name: str) -> None:
        target.add_argument(f"--{name}", required=True, type=Path)
        target.add_argument(f"--{name}-size", required=True, type=int)
        target.add_argument(f"--{name}-sha256", required=True)

    def common(target: argparse.ArgumentParser) -> None:
        byte_input(target, "selection")
        byte_input(target, "inner")
        byte_input(target, "preterminal")
        byte_input(target, "verifier-tool")
        target.add_argument("--unit-slot", required=True, choices=UNIT_SLOTS)

    preterminal = subparsers.add_parser("preterminal")
    common(preterminal)
    preterminal.add_argument("--resource-output", required=True, type=Path)
    preterminal.add_argument("--release-output", required=True, type=Path)

    detached = subparsers.add_parser("detached")
    common(detached)
    for name in ("resource", "release", "terminal", "cleanup"):
        byte_input(detached, name)
    detached.add_argument("--output", required=True, type=Path)
    return parser


def _get(arguments: argparse.Namespace, name: str) -> tuple[bytes, dict[str, object]]:
    key = name.replace("-", "_")
    return _load(
        getattr(arguments, key),
        getattr(arguments, f"{key}_size"),
        getattr(arguments, f"{key}_sha256"),
        name,
    )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    selection_raw, selection_identity = _get(arguments, "selection")
    inner_raw, inner_identity = _get(arguments, "inner")
    preterminal_raw, preterminal_identity = _get(arguments, "preterminal")
    _, verifier_identity = _get(arguments, "verifier-tool")
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if arguments.mode == "preterminal":
        receipt = verify_preterminal_bytes(
            selection_raw=selection_raw,
            selection_identity=selection_identity,
            unit_slot=arguments.unit_slot,
            inner_raw=inner_raw,
            inner_identity=inner_identity,
            preterminal_raw=preterminal_raw,
            preterminal_identity=preterminal_identity,
            verifier_identity=verifier_identity,
            created_at_utc=now,
        )
        receipt_identity = _write_exclusive(
            arguments.resource_output,
            canonical_json_bytes(receipt),
        )
        release = build_release_token(
            receipt,
            receipt_identity,
            released_monotonic_ns=time.monotonic_ns(),
            created_at_utc=now,
        )
        _write_exclusive(arguments.release_output, canonical_json_bytes(release))
        return 0
    resources: dict[str, tuple[bytes, dict[str, object]]] = {
        name: _get(arguments, name) for name in ("resource", "release", "terminal", "cleanup")
    }
    detached = verify_detached_bytes(
        selection_raw=selection_raw,
        selection_identity=selection_identity,
        unit_slot=arguments.unit_slot,
        inner_raw=inner_raw,
        inner_identity=inner_identity,
        preterminal_raw=preterminal_raw,
        preterminal_identity=preterminal_identity,
        resource_raw=resources["resource"][0],
        resource_identity=resources["resource"][1],
        release_raw=resources["release"][0],
        release_identity=resources["release"][1],
        terminal_raw=resources["terminal"][0],
        terminal_identity=resources["terminal"][1],
        cleanup_raw=resources["cleanup"][0],
        cleanup_identity=resources["cleanup"][1],
        verifier_identity=verifier_identity,
        created_at_utc=now,
    )
    _write_exclusive(arguments.output, canonical_json_bytes(detached))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
