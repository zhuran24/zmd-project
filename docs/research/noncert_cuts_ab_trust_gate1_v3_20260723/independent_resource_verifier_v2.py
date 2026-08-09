#!/usr/bin/env python3
"""Independent Gate 1 resource and terminal-state verifier.

The verifier intentionally imports neither the recorder nor the observer.  It
reads every authority input through one O_NOFOLLOW descriptor snapshot, derives
the resource facts from the inner hash chains, joins them to outside-unit
terminal envelopes, and exact-compares the paired receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


RAW_SCHEMA = "noncert-cuts-gate1-inner-resource-chain-v2"
SUMMARY_SCHEMA = "noncert-cuts-gate1-inner-resource-summary-v2"
SELECTION_SCHEMA = "noncert-cuts-gate1-launch-selection-v3"
TERMINAL_SCHEMA = "noncert-cuts-gate1-launch-terminal-envelope-v1"
RECEIPT_SCHEMA = "noncert-cuts-gate1-paired-resource-receipt-v1"
VERIFICATION_SCHEMA = "noncert-cuts-gate1-resource-verification-v2"
ZERO_HASH = "0" * 64
CONTRACT = {
    "memory_high_bytes": 35 * 1024**3,
    "memory_max_bytes": 39 * 1024**3,
    "memory_swap_max_bytes": 16 * 1024**3,
    "oom_policy": "continue",
    "kill_mode": "control-group",
    "send_sigkill": True,
    "runtime_max_seconds": 1500,
    "internal_timeout_seconds": 1470,
}
PAIRED_PURPOSE = "paired_arm_launch"
EVENT_ORDER = (
    "GENESIS",
    "CGROUP_START",
    "CHILD_SPAWN",
    "SAMPLE",
    "CHILD_WAIT",
    "CGROUP_END",
    "SEAL",
)
KNOWN_MEMORY_EVENTS = frozenset(
    {
        "low",
        "high",
        "max",
        "oom",
        "oom_kill",
        "oom_group_kill",
    }
)


class VerificationError(ValueError):
    """An authority input failed closed."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_hex(value: object, length: int) -> bool:
    if type(value) is not str or len(value) != length or value != value.lower():
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _exact_int(value: object, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise VerificationError(f"{field} must be an exact integer >= {minimum}")
    return value


def _exact_keys(value: object, keys: set[str], field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise VerificationError(f"{field} key set drifted")
    return value


def _utc(value: object, field: str) -> str:
    if type(value) is not str:
        raise VerificationError(f"{field} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VerificationError(f"{field} is not an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise VerificationError(f"{field} must carry UTC")
    return value


def _strict_loads(raw: bytes, field: str) -> object:
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise VerificationError(f"{field} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=no_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                VerificationError(f"{field} contains invalid constant {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"{field} is not strict UTF-8 JSON") from exc


def _reject_symlink_components(path: Path) -> Path:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise VerificationError(f"authority path is unavailable: {absolute}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise VerificationError(f"authority path contains a symlink: {absolute}")
    return absolute


def _snapshot_signature(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def snapshot_file(path: Path) -> tuple[bytes, dict[str, object]]:
    """Read one stable regular-file snapshot without reopening the path."""

    absolute = _reject_symlink_components(path)
    try:
        path_before = os.stat(absolute, follow_symlinks=False)
    except OSError as exc:
        raise VerificationError(f"cannot stat authority input: {absolute}") from exc
    if not stat.S_ISREG(path_before.st_mode):
        raise VerificationError(f"authority input is not a regular file: {absolute}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(absolute, flags)
    except OSError as exc:
        raise VerificationError(f"cannot open authority input: {absolute}") from exc
    try:
        descriptor_before = os.fstat(fd)
        if _snapshot_signature(path_before) != _snapshot_signature(descriptor_before):
            raise VerificationError(f"authority path changed before read: {absolute}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        descriptor_after = os.fstat(fd)
        if _snapshot_signature(descriptor_before) != _snapshot_signature(descriptor_after):
            raise VerificationError(f"authority descriptor changed during read: {absolute}")
    finally:
        os.close(fd)
    try:
        path_after = os.stat(absolute, follow_symlinks=False)
    except OSError as exc:
        raise VerificationError(f"authority path disappeared after read: {absolute}") from exc
    if _snapshot_signature(descriptor_after) != _snapshot_signature(path_after):
        raise VerificationError(f"authority path changed after read: {absolute}")
    raw = b"".join(chunks)
    if len(raw) != descriptor_after.st_size:
        raise VerificationError(f"authority read was truncated: {absolute}")
    return raw, {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _identity(value: object, field: str) -> Mapping[str, Any]:
    record = _exact_keys(value, {"path", "size_bytes", "sha256"}, field)
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
        or not _is_hex(record["sha256"], 64)
    ):
        raise VerificationError(f"{field} is not a strict file identity")
    return record


def _identity_map(value: object, field: str) -> Mapping[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping) or not value:
        raise VerificationError(f"{field} must be a non-empty object")
    result: dict[str, Mapping[str, Any]] = {}
    for role, identity in value.items():
        if type(role) is not str or not role:
            raise VerificationError(f"{field} contains an invalid role")
        result[role] = _identity(identity, f"{field}.{role}")
    return result


def _selection_digest(value: Mapping[str, Any]) -> str:
    body = dict(value)
    body.pop("selection_id", None)
    return _digest(body)


def _validate_selection(value: object) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "schema",
            "created_at_utc",
            "purpose",
            "run_nonce",
            "package_id",
            "selection_id",
            "repository_head",
            "contract",
            "qualification_receipt_identity",
            "tools",
            "inputs",
            "arm_directories_absent_at_creation",
            "arm_launch",
            "terminal_observer_tool_role",
            "arms",
        },
        "selection",
    )
    if record["schema"] != SELECTION_SCHEMA:
        raise VerificationError("selection schema mismatch")
    _utc(record["created_at_utc"], "selection.created_at_utc")
    if (
        record["purpose"] != PAIRED_PURPOSE
        or type(record["run_nonce"]) is not str
        or not record["run_nonce"]
        or not _is_hex(record["package_id"], 64)
        or not _is_hex(record["selection_id"], 64)
        or not _is_hex(record["repository_head"], 40)
        or record["contract"] != CONTRACT
        or record["arm_directories_absent_at_creation"] is not True
        or record["arm_launch"] is not True
    ):
        raise VerificationError("selection semantics drifted")
    _identity(
        record["qualification_receipt_identity"],
        "selection.qualification_receipt_identity",
    )
    tools = _identity_map(record["tools"], "selection.tools")
    _identity_map(record["inputs"], "selection.inputs")
    observer_role = record["terminal_observer_tool_role"]
    if type(observer_role) is not str or observer_role not in tools:
        raise VerificationError("terminal observer tool role is not selection-bound")
    arms = _exact_keys(record["arms"], {"control", "treatment"}, "selection.arms")
    distinct: dict[str, set[str]] = {
        "unit_name": set(),
        "attempt_dir": set(),
        "result_path": set(),
        "raw_output_path": set(),
        "terminal_envelope_path": set(),
    }
    for label in ("control", "treatment"):
        arm = _exact_keys(
            arms[label],
            {
                "arm",
                "attempt_dir",
                "unit_name",
                "result_path",
                "raw_output_path",
                "terminal_envelope_path",
                "runner_tool_role",
                "recorder_tool_role",
            },
            f"selection.arms.{label}",
        )
        paths = {
            name: Path(str(arm[name]))
            for name in (
                "attempt_dir",
                "result_path",
                "raw_output_path",
                "terminal_envelope_path",
            )
        }
        if (
            arm["arm"] != label
            or type(arm["unit_name"]) is not str
            or not arm["unit_name"].endswith(".service")
            or any(type(arm[name]) is not str or not path.is_absolute() for name, path in paths.items())
            or any(
                not paths[name].absolute().is_relative_to(paths["attempt_dir"].absolute())
                for name in paths
                if name != "attempt_dir"
            )
            or type(arm["runner_tool_role"]) is not str
            or arm["runner_tool_role"] not in tools
            or type(arm["recorder_tool_role"]) is not str
            or arm["recorder_tool_role"] not in tools
        ):
            raise VerificationError(f"selection arm {label} semantics drifted")
        for name in distinct:
            distinct[name].add(str(arm[name]))
    if any(len(values) != 2 for values in distinct.values()):
        raise VerificationError("selection arm units and outputs must be distinct")
    if _selection_digest(record) != record["selection_id"]:
        raise VerificationError("selection digest mismatch")
    return record


def _validate_ancestors(value: object, field: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or not value:
        raise VerificationError(f"{field} must contain the ancestor chain")
    result: list[Mapping[str, Any]] = []
    for index, raw in enumerate(value):
        item = _exact_keys(
            raw,
            {"path", "memory_high", "memory_max", "memory_swap_max"},
            f"{field}[{index}]",
        )
        if type(item["path"]) is not str or not item["path"].startswith("/"):
            raise VerificationError(f"{field}[{index}].path is invalid")
        for name in ("memory_high", "memory_max", "memory_swap_max"):
            if item[name] is not None and (type(item[name]) is not int or item[name] < 0):
                raise VerificationError(f"{field}[{index}].{name} is invalid")
        result.append(item)
    return result


def _ancestor_contract_ok(ancestors: Sequence[Mapping[str, Any]]) -> bool:
    minima = {
        "memory_high": CONTRACT["memory_high_bytes"],
        "memory_max": CONTRACT["memory_max_bytes"],
        "memory_swap_max": CONTRACT["memory_swap_max_bytes"],
    }
    return all(item[name] is None or item[name] >= minimum for item in ancestors for name, minimum in minima.items())


def _validate_snapshot(value: object, field: str) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "observed_at_utc",
            "monotonic_ns",
            "unit_name",
            "invocation_id",
            "cgroup_path",
            "cgroup_dev",
            "cgroup_inode",
            "memory",
            "memory_events",
            "cgroup_procs",
            "ancestor_limits",
            "systemd",
        },
        field,
    )
    _utc(record["observed_at_utc"], f"{field}.observed_at_utc")
    _exact_int(record["monotonic_ns"], f"{field}.monotonic_ns")
    if (
        type(record["unit_name"]) is not str
        or not record["unit_name"].endswith(".service")
        or not _is_hex(record["invocation_id"], 32)
        or type(record["cgroup_path"]) is not str
        or not record["cgroup_path"].startswith("/")
    ):
        raise VerificationError(f"{field} unit/cgroup identity is invalid")
    _exact_int(record["cgroup_dev"], f"{field}.cgroup_dev")
    _exact_int(record["cgroup_inode"], f"{field}.cgroup_inode", minimum=1)
    memory = _exact_keys(
        record["memory"],
        {"high", "max", "swap_max", "current", "peak", "swap_current", "swap_peak"},
        f"{field}.memory",
    )
    for name, item in memory.items():
        _exact_int(item, f"{field}.memory.{name}")
    events = record["memory_events"]
    if (
        not isinstance(events, Mapping)
        or set(events) != KNOWN_MEMORY_EVENTS
        or not all(type(item) is int and item >= 0 for item in events.values())
    ):
        raise VerificationError(f"{field}.memory_events is invalid")
    procs = record["cgroup_procs"]
    if not isinstance(procs, list) or not all(type(pid) is int and pid > 0 for pid in procs):
        raise VerificationError(f"{field}.cgroup_procs is invalid")
    ancestors = _validate_ancestors(record["ancestor_limits"], f"{field}.ancestor_limits")
    systemd = _exact_keys(
        record["systemd"],
        {
            "memory_high_bytes",
            "memory_max_bytes",
            "memory_swap_max_bytes",
            "oom_policy",
            "kill_mode",
            "send_sigkill",
            "runtime_max_seconds",
            "invocation_id",
            "control_group",
        },
        f"{field}.systemd",
    )
    if (
        systemd["memory_high_bytes"] != CONTRACT["memory_high_bytes"]
        or systemd["memory_max_bytes"] != CONTRACT["memory_max_bytes"]
        or systemd["memory_swap_max_bytes"] != CONTRACT["memory_swap_max_bytes"]
        or systemd["oom_policy"] != CONTRACT["oom_policy"]
        or systemd["kill_mode"] != CONTRACT["kill_mode"]
        or systemd["send_sigkill"] is not True
        or systemd["runtime_max_seconds"] != CONTRACT["runtime_max_seconds"]
        or systemd["invocation_id"] != record["invocation_id"]
        or systemd["control_group"] != record["cgroup_path"]
    ):
        raise VerificationError(f"{field}.systemd contract drifted")
    if not _ancestor_contract_ok(ancestors):
        # The derived summary records this as a violation; the payload is still valid.
        pass
    return record


def _validate_payload(event: str, value: object, field: str) -> Mapping[str, Any]:
    if event == "GENESIS":
        record = _exact_keys(
            value,
            {
                "observed_at_utc",
                "monotonic_ns",
                "run_nonce",
                "package_id",
                "selection_id",
                "selection_identity",
                "arm",
                "unit_name",
                "invocation_id",
                "repository_head",
                "boot_id",
                "recorder_pid",
                "recorder_identity",
                "runner_identity",
                "result_path",
                "raw_output_path",
                "terminal_envelope_path",
                "contract",
            },
            field,
        )
        _utc(record["observed_at_utc"], f"{field}.observed_at_utc")
        _exact_int(record["monotonic_ns"], f"{field}.monotonic_ns")
        _exact_int(record["recorder_pid"], f"{field}.recorder_pid", minimum=1)
        for name, length in (
            ("selection_id", 64),
            ("invocation_id", 32),
            ("repository_head", 40),
            ("boot_id", 32),
        ):
            if not _is_hex(record[name], length):
                raise VerificationError(f"{field}.{name} is invalid")
        if (
            type(record["run_nonce"]) is not str
            or not record["run_nonce"]
            or not _is_hex(record["package_id"], 64)
            or record["arm"] not in {"control", "treatment"}
            or type(record["unit_name"]) is not str
            or not record["unit_name"].endswith(".service")
            or type(record["result_path"]) is not str
            or not Path(record["result_path"]).is_absolute()
            or type(record["raw_output_path"]) is not str
            or not Path(record["raw_output_path"]).is_absolute()
            or type(record["terminal_envelope_path"]) is not str
            or not Path(record["terminal_envelope_path"]).is_absolute()
            or record["contract"] != CONTRACT
        ):
            raise VerificationError(f"{field} genesis semantics drifted")
        _identity(record["selection_identity"], f"{field}.selection_identity")
        _identity(record["recorder_identity"], f"{field}.recorder_identity")
        _identity(record["runner_identity"], f"{field}.runner_identity")
        return record
    if event in {"CGROUP_START", "SAMPLE", "CGROUP_END"}:
        return _validate_snapshot(value, field)
    if event == "CHILD_SPAWN":
        record = _exact_keys(
            value,
            {
                "observed_at_utc",
                "monotonic_ns",
                "pid",
                "proc_start_ticks",
                "pgid",
                "sid",
                "cgroup_path",
                "argv",
            },
            field,
        )
        _utc(record["observed_at_utc"], f"{field}.observed_at_utc")
        for name in ("monotonic_ns", "pid", "proc_start_ticks", "pgid", "sid"):
            _exact_int(record[name], f"{field}.{name}", minimum=1)
        if (
            type(record["cgroup_path"]) is not str
            or not record["cgroup_path"].startswith("/")
            or not isinstance(record["argv"], list)
            or not record["argv"]
            or not all(type(item) is str and item for item in record["argv"])
        ):
            raise VerificationError(f"{field} child spawn is invalid")
        return record
    if event == "CHILD_WAIT":
        record = _exact_keys(
            value,
            {
                "observed_at_utc",
                "monotonic_ns",
                "returncode",
                "termination_reason",
                "timed_out",
                "term_sent",
                "kill_sent",
                "process_group_clean",
                "result_identity",
            },
            field,
        )
        _utc(record["observed_at_utc"], f"{field}.observed_at_utc")
        _exact_int(record["monotonic_ns"], f"{field}.monotonic_ns")
        if type(record["returncode"]) is not int:
            raise VerificationError(f"{field}.returncode must be an exact integer")
        if record["termination_reason"] is not None and (
            type(record["termination_reason"]) is not str or not record["termination_reason"]
        ):
            raise VerificationError(f"{field}.termination_reason is invalid")
        if (
            type(record["timed_out"]) is not bool
            or record["timed_out"] is not (record["termination_reason"] == "wall_timeout")
            or type(record["process_group_clean"]) is not bool
        ):
            raise VerificationError(f"{field} timeout/cleanup semantics drifted")
        _exact_int(record["term_sent"], f"{field}.term_sent")
        _exact_int(record["kill_sent"], f"{field}.kill_sent")
        _identity(record["result_identity"], f"{field}.result_identity")
        return record
    if event == "SEAL":
        record = _exact_keys(value, {"sealed_at_utc", "monotonic_ns", "sealed_event_count"}, field)
        _utc(record["sealed_at_utc"], f"{field}.sealed_at_utc")
        _exact_int(record["monotonic_ns"], f"{field}.monotonic_ns")
        _exact_int(record["sealed_event_count"], f"{field}.sealed_event_count", minimum=1)
        return record
    raise VerificationError(f"unsupported raw event: {event}")


def _parse_chain(raw: bytes) -> list[Mapping[str, Any]]:
    if not raw or not raw.endswith(b"\n"):
        raise VerificationError("raw chain must be non-empty and newline terminated")
    rows: list[Mapping[str, Any]] = []
    previous = ZERO_HASH
    for seq, line in enumerate(raw.splitlines()):
        value = _strict_loads(line, f"raw event {seq}")
        row = _exact_keys(
            value,
            {"schema_version", "seq", "event", "prev_hash", "payload", "event_hash"},
            f"raw event {seq}",
        )
        if (
            row["schema_version"] != RAW_SCHEMA
            or row["seq"] != seq
            or row["event"] not in EVENT_ORDER
            or row["prev_hash"] != previous
            or not _is_hex(row["event_hash"], 64)
        ):
            raise VerificationError(f"raw event {seq} chain metadata drifted")
        base = {key: row[key] for key in ("schema_version", "seq", "event", "prev_hash", "payload")}
        if _digest(base) != row["event_hash"]:
            raise VerificationError(f"raw event {seq} hash mismatch")
        _validate_payload(str(row["event"]), row["payload"], f"raw event {seq}.payload")
        rows.append(row)
        previous = str(row["event_hash"])
    return rows


def _derive_inner(raw: bytes) -> tuple[dict[str, object], Mapping[str, Any]]:
    rows = _parse_chain(raw)
    names = [str(row["event"]) for row in rows]
    if (
        len(rows) < 7
        or names[:3] != ["GENESIS", "CGROUP_START", "CHILD_SPAWN"]
        or names[-3:] != ["CHILD_WAIT", "CGROUP_END", "SEAL"]
        or not names[3:-3]
        or any(name != "SAMPLE" for name in names[3:-3])
    ):
        raise VerificationError("raw event sequence is incomplete")
    genesis = rows[0]["payload"]
    snapshots = [row["payload"] for row in rows if row["event"] in {"CGROUP_START", "SAMPLE", "CGROUP_END"}]
    spawn = rows[2]["payload"]
    wait = rows[-3]["payload"]
    seal = rows[-1]["payload"]
    if seal["sealed_event_count"] != len(rows) - 1:
        raise VerificationError("SEAL event count mismatch")
    ordered_times = [
        genesis["monotonic_ns"],
        snapshots[0]["monotonic_ns"],
        spawn["monotonic_ns"],
        *[snapshot["monotonic_ns"] for snapshot in snapshots[1:-1]],
        wait["monotonic_ns"],
        snapshots[-1]["monotonic_ns"],
        seal["monotonic_ns"],
    ]
    if any(left > right for left, right in zip(ordered_times, ordered_times[1:])):
        raise VerificationError("raw monotonic interval moved backwards")
    unit_identity = (genesis["unit_name"], genesis["invocation_id"])
    cgroup_identity: tuple[object, object, object] | None = None
    event_keys = set(snapshots[0]["memory_events"])
    limit_violations = 0
    for snapshot in snapshots:
        if (snapshot["unit_name"], snapshot["invocation_id"]) != unit_identity:
            raise VerificationError("unit or InvocationID drifted inside raw chain")
        current_cgroup = (
            snapshot["cgroup_path"],
            snapshot["cgroup_dev"],
            snapshot["cgroup_inode"],
        )
        cgroup_identity = current_cgroup if cgroup_identity is None else cgroup_identity
        if current_cgroup != cgroup_identity or spawn["cgroup_path"] != snapshot["cgroup_path"]:
            raise VerificationError("cgroup identity drifted inside raw chain")
        if set(snapshot["memory_events"]) != event_keys:
            raise VerificationError("memory.events key set drifted")
        memory = snapshot["memory"]
        ancestors = _validate_ancestors(snapshot["ancestor_limits"], "snapshot.ancestor_limits")
        if (
            memory["high"] != CONTRACT["memory_high_bytes"]
            or memory["max"] != CONTRACT["memory_max_bytes"]
            or memory["swap_max"] != CONTRACT["memory_swap_max_bytes"]
            or not _ancestor_contract_ok(ancestors)
        ):
            limit_violations += 1
    assert cgroup_identity is not None
    event_deltas = {
        key: snapshots[-1]["memory_events"][key] - snapshots[0]["memory_events"][key] for key in sorted(event_keys)
    }
    if any(value < 0 for value in event_deltas.values()):
        raise VerificationError("memory.events moved backwards")
    peak = max(snapshot["memory"]["peak"] for snapshot in snapshots)
    swap_peak = max(snapshot["memory"]["swap_peak"] for snapshot in snapshots)
    returncode = wait["returncode"]
    exit_code = returncode if returncode >= 0 else None
    exit_signal = -returncode if returncode < 0 else None
    kill_count = wait["term_sent"] + wait["kill_sent"] + int(exit_signal is not None)
    timeout_count = int(wait["timed_out"])
    event_violation_count = sum(value != 0 for value in event_deltas.values())
    inner_clean = bool(
        exit_code == 0
        and exit_signal is None
        and wait["termination_reason"] is None
        and wait["process_group_clean"] is True
        and kill_count == 0
        and timeout_count == 0
        and limit_violations == 0
        and event_violation_count == 0
        and peak < CONTRACT["memory_high_bytes"]
        and swap_peak == 0
        and snapshots[-1]["memory"]["swap_current"] == 0
    )
    summary: dict[str, object] = {
        "schema_version": SUMMARY_SCHEMA,
        "run_nonce": genesis["run_nonce"],
        "package_id": genesis["package_id"],
        "selection_id": genesis["selection_id"],
        "arm": genesis["arm"],
        "unit_name": genesis["unit_name"],
        "invocation_id": genesis["invocation_id"],
        "boot_id": genesis["boot_id"],
        "cgroup": {
            "path": cgroup_identity[0],
            "dev": cgroup_identity[1],
            "inode": cgroup_identity[2],
        },
        "interval": {
            "started_monotonic_ns": spawn["monotonic_ns"],
            "finished_monotonic_ns": wait["monotonic_ns"],
            "wall_nanoseconds": wait["monotonic_ns"] - spawn["monotonic_ns"],
        },
        "observation_interval": {
            "started_monotonic_ns": snapshots[0]["monotonic_ns"],
            "finished_monotonic_ns": snapshots[-1]["monotonic_ns"],
            "wall_nanoseconds": snapshots[-1]["monotonic_ns"] - snapshots[0]["monotonic_ns"],
        },
        "exit": {
            "returncode": returncode,
            "exit_code": exit_code,
            "signal": exit_signal,
            "termination_reason": wait["termination_reason"],
            "process_group_clean": wait["process_group_clean"],
        },
        "memory": {
            "peak_bytes": peak,
            "swap_peak_bytes": swap_peak,
            "swap_at_completion_bytes": snapshots[-1]["memory"]["swap_current"],
            "event_deltas": event_deltas,
        },
        "kill_count": kill_count,
        "timeout_count": timeout_count,
        "limit_violation_count": limit_violations,
        "event_violation_count": event_violation_count,
        "result_identity": dict(wait["result_identity"]),
        "sealed_monotonic_ns": seal["monotonic_ns"],
        "inner_sealed": True,
        "inner_clean": inner_clean,
    }
    return summary, genesis


def _validate_terminal(value: object) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "schema_version",
            "observed_at_utc",
            "selection_identity",
            "selection_id",
            "run_nonce",
            "package_id",
            "arm",
            "unit_name",
            "invocation_id",
            "control_group",
            "boot_id",
            "active_enter_monotonic_ns",
            "inactive_enter_monotonic_ns",
            "result",
            "exec_main_code",
            "exec_main_status",
            "cgroup_empty",
            "cgroup_path_present",
            "cgroup_events",
            "inner_raw_identity",
            "arm_result_identity",
            "observer_identity",
        },
        "terminal envelope",
    )
    if record["schema_version"] != TERMINAL_SCHEMA:
        raise VerificationError("terminal envelope schema mismatch")
    _utc(record["observed_at_utc"], "terminal.observed_at_utc")
    _identity(record["selection_identity"], "terminal.selection_identity")
    _identity(record["inner_raw_identity"], "terminal.inner_raw_identity")
    _identity(record["arm_result_identity"], "terminal.arm_result_identity")
    _identity(record["observer_identity"], "terminal.observer_identity")
    for name, length in (
        ("selection_id", 64),
        ("package_id", 64),
        ("invocation_id", 32),
        ("boot_id", 32),
    ):
        if not _is_hex(record[name], length):
            raise VerificationError(f"terminal.{name} is invalid")
    if (
        type(record["run_nonce"]) is not str
        or not record["run_nonce"]
        or record["arm"] not in {"control", "treatment"}
        or type(record["unit_name"]) is not str
        or not record["unit_name"].endswith(".service")
        or type(record["control_group"]) is not str
        or not record["control_group"].startswith("/")
        or type(record["result"]) is not str
        or not record["result"]
        or type(record["exec_main_code"]) is not str
        or not record["exec_main_code"]
        or type(record["exec_main_status"]) is not int
        or type(record["cgroup_empty"]) is not bool
        or type(record["cgroup_path_present"]) is not bool
    ):
        raise VerificationError("terminal envelope field type drifted")
    start = _exact_int(record["active_enter_monotonic_ns"], "terminal.active_enter_monotonic_ns")
    finish = _exact_int(record["inactive_enter_monotonic_ns"], "terminal.inactive_enter_monotonic_ns")
    if finish < start:
        raise VerificationError("terminal interval moved backwards")
    events = _exact_keys(record["cgroup_events"], {"populated", "frozen"}, "terminal.cgroup_events")
    _exact_int(events["populated"], "terminal.cgroup_events.populated")
    _exact_int(events["frozen"], "terminal.cgroup_events.frozen")
    if record["cgroup_empty"] is not (events["populated"] == 0):
        raise VerificationError("terminal cgroup_empty does not derive from cgroup.events")
    return record


def _require_terminal_success(terminal: Mapping[str, Any]) -> None:
    if (
        terminal["result"] != "success"
        or terminal["exec_main_code"] != "exited"
        or terminal["exec_main_status"] != 0
        or terminal["cgroup_empty"] is not True
        or terminal["cgroup_events"] != {"populated": 0, "frozen": 0}
    ):
        raise VerificationError(
            "inner SEAL is insufficient: final systemd success/exited/0 and empty cgroup are required"
        )


def _combine_arm(
    *,
    label: str,
    selection: Mapping[str, Any],
    selection_identity: Mapping[str, object],
    raw: bytes,
    raw_identity: Mapping[str, object],
    terminal: Mapping[str, Any],
    terminal_identity: Mapping[str, object],
    result_identity: Mapping[str, object],
) -> dict[str, object]:
    summary, genesis = _derive_inner(raw)
    selected = selection["arms"][label]
    tools = selection["tools"]
    observer_role = selection["terminal_observer_tool_role"]
    bindings = (
        (genesis["selection_identity"], selection_identity, "raw selection identity"),
        (genesis["selection_id"], selection["selection_id"], "raw selection id"),
        (genesis["run_nonce"], selection["run_nonce"], "raw run nonce"),
        (genesis["package_id"], selection["package_id"], "raw package id"),
        (genesis["repository_head"], selection["repository_head"], "raw repository head"),
        (genesis["arm"], label, "raw arm"),
        (genesis["unit_name"], selected["unit_name"], "raw unit"),
        (
            genesis["runner_identity"],
            tools[selected["runner_tool_role"]],
            "raw runner identity",
        ),
        (
            genesis["recorder_identity"],
            tools[selected["recorder_tool_role"]],
            "raw recorder identity",
        ),
        (genesis["result_path"], selected["result_path"], "raw result path"),
        (genesis["raw_output_path"], selected["raw_output_path"], "raw output path"),
        (
            genesis["terminal_envelope_path"],
            selected["terminal_envelope_path"],
            "raw terminal path",
        ),
        (genesis["contract"], CONTRACT, "raw contract"),
        (summary["result_identity"], result_identity, "raw result identity"),
        (terminal["selection_identity"], selection_identity, "terminal selection identity"),
        (terminal["selection_id"], selection["selection_id"], "terminal selection id"),
        (terminal["run_nonce"], selection["run_nonce"], "terminal run nonce"),
        (terminal["package_id"], selection["package_id"], "terminal package id"),
        (terminal["arm"], label, "terminal arm"),
        (terminal["unit_name"], summary["unit_name"], "terminal unit"),
        (terminal["invocation_id"], summary["invocation_id"], "terminal InvocationID"),
        (terminal["boot_id"], summary["boot_id"], "terminal boot id"),
        (terminal["control_group"], summary["cgroup"]["path"], "terminal cgroup"),
        (terminal["inner_raw_identity"], raw_identity, "terminal raw identity"),
        (terminal["arm_result_identity"], result_identity, "terminal result identity"),
        (terminal["observer_identity"], tools[observer_role], "terminal observer identity"),
    )
    for actual, expected, field in bindings:
        if actual != expected:
            raise VerificationError(f"{field} drifted for {label}")
    _require_terminal_success(terminal)
    observation = summary["observation_interval"]
    if (
        terminal["active_enter_monotonic_ns"] > observation["started_monotonic_ns"]
        or terminal["inactive_enter_monotonic_ns"] < observation["finished_monotonic_ns"]
        or terminal["inactive_enter_monotonic_ns"] < summary["sealed_monotonic_ns"]
    ):
        raise VerificationError(f"outer unit interval does not cover inner observations and SEAL for {label}")
    if summary["inner_clean"] is not True:
        raise VerificationError(f"inner resource summary is not clean for {label}")
    derived = {
        **summary,
        "unit_interval": {
            "started_monotonic_ns": terminal["active_enter_monotonic_ns"],
            "finished_monotonic_ns": terminal["inactive_enter_monotonic_ns"],
            "wall_nanoseconds": (terminal["inactive_enter_monotonic_ns"] - terminal["active_enter_monotonic_ns"]),
        },
        "terminal": {
            "result": terminal["result"],
            "exec_main_code": terminal["exec_main_code"],
            "exec_main_status": terminal["exec_main_status"],
            "cgroup_empty": terminal["cgroup_empty"],
            "cgroup_path_present": terminal["cgroup_path_present"],
            "cgroup_events": dict(terminal["cgroup_events"]),
        },
        "resource_and_terminal_clean": True,
    }
    return {
        "raw_chain_identity": dict(raw_identity),
        "terminal_envelope_identity": dict(terminal_identity),
        "result_identity": dict(result_identity),
        "derived": derived,
    }


def derive_pair_inputs(
    *,
    selection_path: Path,
    control_raw_path: Path,
    control_terminal_path: Path,
    treatment_raw_path: Path,
    treatment_terminal_path: Path,
) -> dict[str, object]:
    """Snapshot and derive all inputs except the paired receipt."""

    selection_raw, selection_identity = snapshot_file(selection_path)
    selection = _validate_selection(_strict_loads(selection_raw, "selection"))
    arms: dict[str, object] = {}
    input_paths = {
        "control": (control_raw_path, control_terminal_path),
        "treatment": (treatment_raw_path, treatment_terminal_path),
    }
    for label in ("control", "treatment"):
        raw_bytes, raw_identity = snapshot_file(input_paths[label][0])
        terminal_raw, terminal_identity = snapshot_file(input_paths[label][1])
        terminal = _validate_terminal(_strict_loads(terminal_raw, f"{label} terminal"))
        selected_result = Path(selection["arms"][label]["result_path"])
        _, result_identity = snapshot_file(selected_result)
        if str(input_paths[label][0].absolute()) != selection["arms"][label]["raw_output_path"]:
            raise VerificationError(f"selected raw path drifted for {label}")
        if str(input_paths[label][1].absolute()) != selection["arms"][label]["terminal_envelope_path"]:
            raise VerificationError(f"selected terminal envelope path drifted for {label}")
        arms[label] = _combine_arm(
            label=label,
            selection=selection,
            selection_identity=selection_identity,
            raw=raw_bytes,
            raw_identity=raw_identity,
            terminal=terminal,
            terminal_identity=terminal_identity,
            result_identity=result_identity,
        )
    control_derived = arms["control"]["derived"]
    treatment_derived = arms["treatment"]["derived"]
    if control_derived["boot_id"] != treatment_derived["boot_id"]:
        raise VerificationError("paired arms were not observed under one boot identity")
    if control_derived["invocation_id"] == treatment_derived["invocation_id"]:
        raise VerificationError("paired arms reused one InvocationID")
    control_interval = control_derived["unit_interval"]
    treatment_interval = treatment_derived["unit_interval"]
    disjoint = (
        control_interval["finished_monotonic_ns"] <= treatment_interval["started_monotonic_ns"]
        or treatment_interval["finished_monotonic_ns"] <= control_interval["started_monotonic_ns"]
    )
    if not disjoint:
        raise VerificationError("paired selected unit intervals overlap")
    return {
        "selection": selection,
        "selection_identity": selection_identity,
        "arms": arms,
    }


def _validate_receipt(
    value: object,
    *,
    selection: Mapping[str, Any],
    selection_identity: Mapping[str, object],
    arms: Mapping[str, object],
) -> Mapping[str, Any]:
    record = _exact_keys(
        value,
        {
            "schema_version",
            "created_at_utc",
            "selection_identity",
            "run_nonce",
            "selection_id",
            "contract",
            "arms",
            "claim",
            "receipt_id",
        },
        "paired resource receipt",
    )
    if record["schema_version"] != RECEIPT_SCHEMA:
        raise VerificationError("receipt schema mismatch")
    _utc(record["created_at_utc"], "receipt.created_at_utc")
    _identity(record["selection_identity"], "receipt.selection_identity")
    if (
        record["selection_identity"] != selection_identity
        or record["run_nonce"] != selection["run_nonce"]
        or record["selection_id"] != selection["selection_id"]
        or record["contract"] != CONTRACT
        or record["claim"] != "resource_evidence_only"
        or not _is_hex(record["receipt_id"], 64)
    ):
        raise VerificationError("receipt top-level binding drifted")
    receipt_arms = _exact_keys(record["arms"], {"control", "treatment"}, "receipt.arms")
    for label in ("control", "treatment"):
        arm = _exact_keys(
            receipt_arms[label],
            {
                "raw_chain_identity",
                "terminal_envelope_identity",
                "result_identity",
                "derived",
            },
            f"receipt.arms.{label}",
        )
        for name in ("raw_chain_identity", "terminal_envelope_identity", "result_identity"):
            _identity(arm[name], f"receipt.arms.{label}.{name}")
        if arm != arms[label]:
            raise VerificationError(f"receipt arm {label} is not the independently derived authority")
    body = dict(record)
    receipt_id = body.pop("receipt_id")
    if _digest(body) != receipt_id:
        raise VerificationError("receipt digest mismatch")
    return record


def verify_resource_pair(
    *,
    selection_path: Path,
    receipt_path: Path,
    control_raw_path: Path,
    control_terminal_path: Path,
    treatment_raw_path: Path,
    treatment_terminal_path: Path,
) -> dict[str, object]:
    derived = derive_pair_inputs(
        selection_path=selection_path,
        control_raw_path=control_raw_path,
        control_terminal_path=control_terminal_path,
        treatment_raw_path=treatment_raw_path,
        treatment_terminal_path=treatment_terminal_path,
    )
    receipt_raw, receipt_identity = snapshot_file(receipt_path)
    receipt = _validate_receipt(
        _strict_loads(receipt_raw, "paired resource receipt"),
        selection=derived["selection"],
        selection_identity=derived["selection_identity"],
        arms=derived["arms"],
    )
    return {
        "schema_version": VERIFICATION_SCHEMA,
        "status": "PASS",
        "selection_identity": dict(derived["selection_identity"]),
        "receipt_identity": receipt_identity,
        "receipt_id": receipt["receipt_id"],
        "run_nonce": receipt["run_nonce"],
        "contract": dict(CONTRACT),
        "arms": {
            label: {
                "unit_name": derived["arms"][label]["derived"]["unit_name"],
                "invocation_id": derived["arms"][label]["derived"]["invocation_id"],
                "raw_chain_identity": dict(derived["arms"][label]["raw_chain_identity"]),
                "terminal_envelope_identity": dict(derived["arms"][label]["terminal_envelope_identity"]),
                "result_identity": dict(derived["arms"][label]["result_identity"]),
                "unit_interval": dict(derived["arms"][label]["derived"]["unit_interval"]),
                "peak_bytes": derived["arms"][label]["derived"]["memory"]["peak_bytes"],
                "swap_peak_bytes": derived["arms"][label]["derived"]["memory"]["swap_peak_bytes"],
                "event_deltas": dict(derived["arms"][label]["derived"]["memory"]["event_deltas"]),
                "exit": dict(derived["arms"][label]["derived"]["exit"]),
                "kill_count": derived["arms"][label]["derived"]["kill_count"],
                "timeout_count": derived["arms"][label]["derived"]["timeout_count"],
                "limit_violation_count": derived["arms"][label]["derived"]["limit_violation_count"],
                "resource_and_terminal_clean": True,
            }
            for label in ("control", "treatment")
        },
        "claim": "resource_evidence_only",
    }


def _write_exclusive(path: Path, raw: bytes) -> None:
    absolute = path.absolute()
    if absolute.exists() or absolute.is_symlink():
        raise VerificationError(f"refusing to overwrite output: {absolute}")
    if not absolute.parent.is_dir():
        raise VerificationError(f"output parent is missing: {absolute.parent}")
    _reject_symlink_components(absolute.parent)
    fd = os.open(
        absolute,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        view = memoryview(raw)
        while view:
            count = os.write(fd, view)
            if count <= 0:
                raise VerificationError(f"short write for {absolute}")
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--control-raw", type=Path, required=True)
    parser.add_argument("--control-terminal", type=Path, required=True)
    parser.add_argument("--treatment-raw", type=Path, required=True)
    parser.add_argument("--treatment-terminal", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = verify_resource_pair(
            selection_path=args.selection,
            receipt_path=args.receipt,
            control_raw_path=args.control_raw,
            control_terminal_path=args.control_terminal,
            treatment_raw_path=args.treatment_raw,
            treatment_terminal_path=args.treatment_terminal,
        )
    except VerificationError as exc:
        report = {
            "schema_version": VERIFICATION_SCHEMA,
            "status": "FAIL",
            "error": str(exc),
            "claim": "none",
        }
        exit_code = 2
    else:
        exit_code = 0
    raw = json.dumps(report, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
    if args.output is not None:
        _write_exclusive(args.output, raw)
    print(raw.decode("utf-8"), end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
