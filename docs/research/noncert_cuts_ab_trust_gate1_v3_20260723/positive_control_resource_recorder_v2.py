#!/usr/bin/env python3
"""Gate 1 v3 inner resource ledger primitives.

The live arm entry point is deliberately selection-gated and disabled in this
closeout.  The module nevertheless fixes the byte-level ledger, validation,
and derivation contract that a future separately authorized launcher must use.
No systemd or solver command is executed by this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


RAW_SCHEMA = "noncert-cuts-gate1-inner-resource-chain-v2"
SELECTION_SCHEMA = "noncert-cuts-gate1-launch-selection-v3"
PAIRED_PURPOSE = "paired_arm_launch"
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
ZERO_HASH = "0" * 64
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
EVENT_ORDER = (
    "GENESIS",
    "CGROUP_START",
    "CHILD_SPAWN",
    "SAMPLE",
    "CHILD_WAIT",
    "CGROUP_END",
    "SEAL",
)


class RecorderError(ValueError):
    """The raw authority is malformed or live execution is not authorized."""


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


def _is_sha256(value: object) -> bool:
    return _is_hex(value, 64)


def _exact_int(value: object, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise RecorderError(f"{field} must be an exact integer >= {minimum}")
    return value


def _exact_keys(value: object, keys: set[str], field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise RecorderError(f"{field} key set drifted")
    return value


def _utc(value: object, field: str) -> str:
    if type(value) is not str:
        raise RecorderError(f"{field} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecorderError(f"{field} is not an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise RecorderError(f"{field} must carry UTC")
    return value


def _identity(value: object, field: str) -> Mapping[str, Any]:
    record = _exact_keys(value, {"path", "size_bytes", "sha256"}, field)
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
        or not _is_sha256(record["sha256"])
    ):
        raise RecorderError(f"{field} is not a file identity")
    return record


def _reject_symlink_components(path: Path) -> Path:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise RecorderError(f"input path is unavailable: {absolute}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise RecorderError(f"input path contains a symlink: {absolute}")
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
    """Read and identify one stable O_NOFOLLOW descriptor snapshot."""

    absolute = _reject_symlink_components(path)
    try:
        path_before = os.stat(absolute, follow_symlinks=False)
    except OSError as exc:
        raise RecorderError(f"cannot stat input: {absolute}") from exc
    if not stat.S_ISREG(path_before.st_mode):
        raise RecorderError(f"input is not a regular file: {absolute}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(absolute, flags)
    except OSError as exc:
        raise RecorderError(f"cannot open input: {absolute}") from exc
    try:
        descriptor_before = os.fstat(fd)
        if _snapshot_signature(path_before) != _snapshot_signature(descriptor_before):
            raise RecorderError(f"input path changed before read: {absolute}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        descriptor_after = os.fstat(fd)
        if _snapshot_signature(descriptor_before) != _snapshot_signature(descriptor_after):
            raise RecorderError(f"input descriptor changed during read: {absolute}")
    finally:
        os.close(fd)
    try:
        path_after = os.stat(absolute, follow_symlinks=False)
    except OSError as exc:
        raise RecorderError(f"input path disappeared after read: {absolute}") from exc
    if _snapshot_signature(descriptor_after) != _snapshot_signature(path_after):
        raise RecorderError(f"input path changed after read: {absolute}")
    raw = b"".join(chunks)
    if len(raw) != descriptor_after.st_size:
        raise RecorderError(f"input read was truncated: {absolute}")
    return raw, {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def file_identity(path: Path) -> dict[str, object]:
    _, identity = snapshot_file(path)
    return identity


def _strict_loads(raw: bytes, field: str) -> object:
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise RecorderError(f"{field} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=no_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(RecorderError(f"invalid constant {token}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecorderError(f"{field} is not strict UTF-8 JSON") from exc


def _validate_identity_map(value: object, field: str) -> Mapping[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping) or not value:
        raise RecorderError(f"{field} must be a non-empty object")
    result: dict[str, Mapping[str, Any]] = {}
    for role, raw_identity in value.items():
        if type(role) is not str or not role:
            raise RecorderError(f"{field} contains an invalid role")
        result[role] = _identity(raw_identity, f"{field}.{role}")
    return result


def _selection_digest(selection: Mapping[str, Any]) -> str:
    body = dict(selection)
    body.pop("selection_id", None)
    return _digest(body)


def _validate_selection(selection: object) -> Mapping[str, Any]:
    record = _exact_keys(
        selection,
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
        "direct paired launch selection",
    )
    if record["schema"] != SELECTION_SCHEMA:
        raise RecorderError("direct launch selection schema mismatch")
    _utc(record["created_at_utc"], "selection.created_at_utc")
    if (
        record["purpose"] != PAIRED_PURPOSE
        or type(record["run_nonce"]) is not str
        or not record["run_nonce"]
        or not _is_sha256(record["package_id"])
        or not _is_sha256(record["selection_id"])
        or not _is_hex(record["repository_head"], 40)
        or record["contract"] != CONTRACT
        or record["arm_directories_absent_at_creation"] is not True
        or record["arm_launch"] is not True
    ):
        raise RecorderError("direct launch selection semantics drifted")
    _identity(
        record["qualification_receipt_identity"],
        "selection.qualification_receipt_identity",
    )
    tools = _validate_identity_map(record["tools"], "selection.tools")
    _validate_identity_map(record["inputs"], "selection.inputs")
    observer_role = record["terminal_observer_tool_role"]
    if type(observer_role) is not str or observer_role not in tools:
        raise RecorderError("terminal observer tool role is not selection-bound")
    arms = _exact_keys(record["arms"], {"control", "treatment"}, "selection.arms")
    unit_names: set[str] = set()
    attempt_dirs: set[str] = set()
    output_paths: dict[str, set[str]] = {
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
        absolute_paths = {
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
            or any(type(arm[name]) is not str or not absolute_paths[name].is_absolute() for name in absolute_paths)
            or type(arm["runner_tool_role"]) is not str
            or arm["runner_tool_role"] not in tools
            or type(arm["recorder_tool_role"]) is not str
            or arm["recorder_tool_role"] not in tools
        ):
            raise RecorderError(f"direct selection arm {label} semantics drifted")
        attempt = absolute_paths["attempt_dir"]
        if any(
            not path.absolute().is_relative_to(attempt.absolute())
            for name, path in absolute_paths.items()
            if name != "attempt_dir"
        ):
            raise RecorderError(f"selection arm {label} output escapes its attempt")
        unit_names.add(arm["unit_name"])
        attempt_dirs.add(str(attempt))
        for name in output_paths:
            output_paths[name].add(str(absolute_paths[name]))
    if len(unit_names) != 2 or len(attempt_dirs) != 2 or any(len(paths) != 2 for paths in output_paths.values()):
        raise RecorderError("paired selection must use distinct units, attempts, and outputs")
    if _selection_digest(record) != record["selection_id"]:
        raise RecorderError("direct launch selection digest mismatch")
    return record


def load_paired_launch_selection(
    selection_path: Path,
    *,
    expected_identity: Mapping[str, object],
    arm: str,
    unit_name: str,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, object]]:
    raw, identity = snapshot_file(selection_path)
    if identity != _identity(expected_identity, "expected selection identity"):
        raise RecorderError("direct launch selection detached identity drifted")
    record = _validate_selection(_strict_loads(raw, "direct launch selection"))
    if arm not in {"control", "treatment"}:
        raise RecorderError("arm must be control or treatment")
    selected_arm = record["arms"][arm]
    if selected_arm["unit_name"] != unit_name:
        raise RecorderError("future arm unit is not the selected paired unit")
    tools = record["tools"]
    recorder_role = selected_arm["recorder_tool_role"]
    current_recorder = file_identity(Path(__file__))
    if tools[recorder_role] != current_recorder:
        raise RecorderError("selected recorder tool identity drifted")
    return record, selected_arm, identity


def make_event(
    *,
    seq: int,
    event: str,
    prev_hash: str,
    payload: Mapping[str, Any],
) -> dict[str, object]:
    _exact_int(seq, "event.seq")
    if event not in EVENT_ORDER or not _is_sha256(prev_hash):
        raise RecorderError("event kind or predecessor hash is invalid")
    base: dict[str, object] = {
        "schema_version": RAW_SCHEMA,
        "seq": seq,
        "event": event,
        "prev_hash": prev_hash,
        "payload": dict(payload),
    }
    return {**base, "event_hash": _digest(base)}


def build_chain(events: Iterable[tuple[str, Mapping[str, Any]]]) -> bytes:
    rows: list[bytes] = []
    previous = ZERO_HASH
    for seq, (event, payload) in enumerate(events):
        row = make_event(seq=seq, event=event, prev_hash=previous, payload=payload)
        rows.append(_canonical_bytes(row))
        previous = str(row["event_hash"])
    return b"\n".join(rows) + (b"\n" if rows else b"")


def _validate_contract(value: object, field: str) -> None:
    if value != CONTRACT:
        raise RecorderError(f"{field} does not match the 35/39/16-GiB contract")


def _validate_ancestors(value: object, field: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list) or not value:
        raise RecorderError(f"{field} must contain the cgroup ancestor chain")
    result: list[Mapping[str, Any]] = []
    for index, raw in enumerate(value):
        item = _exact_keys(raw, {"path", "memory_high", "memory_max", "memory_swap_max"}, f"{field}[{index}]")
        if type(item["path"]) is not str or not item["path"].startswith("/"):
            raise RecorderError(f"{field}[{index}].path is invalid")
        for name in ("memory_high", "memory_max", "memory_swap_max"):
            if item[name] is not None and (type(item[name]) is not int or item[name] < 0):
                raise RecorderError(f"{field}[{index}].{name} is invalid")
        result.append(item)
    return result


def _ancestor_contract_ok(ancestors: Sequence[Mapping[str, Any]]) -> bool:
    required = {
        "memory_high": CONTRACT["memory_high_bytes"],
        "memory_max": CONTRACT["memory_max_bytes"],
        "memory_swap_max": CONTRACT["memory_swap_max_bytes"],
    }
    return all(item[name] is None or item[name] >= minimum for item in ancestors for name, minimum in required.items())


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
        raise RecorderError(f"{field} unit/cgroup identity is invalid")
    _exact_int(record["cgroup_dev"], f"{field}.cgroup_dev")
    _exact_int(record["cgroup_inode"], f"{field}.cgroup_inode", minimum=1)
    memory = _exact_keys(
        record["memory"],
        {
            "high",
            "max",
            "swap_max",
            "current",
            "peak",
            "swap_current",
            "swap_peak",
        },
        f"{field}.memory",
    )
    for name, item in memory.items():
        _exact_int(item, f"{field}.memory.{name}")
    events = record["memory_events"]
    if (
        not isinstance(events, Mapping)
        or not KNOWN_MEMORY_EVENTS <= set(events)
        or not all(type(key) is str and key and type(item) is int and item >= 0 for key, item in events.items())
    ):
        raise RecorderError(f"{field}.memory_events is invalid")
    procs = record["cgroup_procs"]
    if not isinstance(procs, list) or not all(type(pid) is int and pid > 0 for pid in procs):
        raise RecorderError(f"{field}.cgroup_procs is invalid")
    _validate_ancestors(record["ancestor_limits"], f"{field}.ancestor_limits")
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
        raise RecorderError(f"{field}.systemd contract drifted")
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
        if not _is_sha256(record["selection_id"]):
            raise RecorderError(f"{field}.selection_id is invalid")
        if not _is_hex(record["invocation_id"], 32):
            raise RecorderError(f"{field}.invocation_id is invalid")
        if not _is_hex(record["repository_head"], 40):
            raise RecorderError(f"{field}.repository_head is invalid")
        if not _is_hex(record["boot_id"], 32):
            raise RecorderError(f"{field}.boot_id is invalid")
        if (
            type(record["run_nonce"]) is not str
            or not record["run_nonce"]
            or not _is_sha256(record["package_id"])
            or record["arm"] not in {"control", "treatment"}
            or type(record["unit_name"]) is not str
            or not record["unit_name"].endswith(".service")
            or type(record["result_path"]) is not str
            or not Path(record["result_path"]).is_absolute()
            or type(record["raw_output_path"]) is not str
            or not Path(record["raw_output_path"]).is_absolute()
            or type(record["terminal_envelope_path"]) is not str
            or not Path(record["terminal_envelope_path"]).is_absolute()
        ):
            raise RecorderError(f"{field} genesis identity is invalid")
        _identity(record["selection_identity"], f"{field}.selection_identity")
        _identity(record["recorder_identity"], f"{field}.recorder_identity")
        _identity(record["runner_identity"], f"{field}.runner_identity")
        _validate_contract(record["contract"], f"{field}.contract")
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
            raise RecorderError(f"{field} child spawn is invalid")
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
            raise RecorderError(f"{field}.returncode must be an exact integer")
        if record["termination_reason"] is not None and (
            type(record["termination_reason"]) is not str or not record["termination_reason"]
        ):
            raise RecorderError(f"{field}.termination_reason is invalid")
        if (
            type(record["timed_out"]) is not bool
            or record["timed_out"] is not (record["termination_reason"] == "wall_timeout")
            or type(record["process_group_clean"]) is not bool
        ):
            raise RecorderError(f"{field} timeout/cleanup semantics drifted")
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
    raise RecorderError(f"unsupported raw event: {event}")


def parse_chain(raw: bytes) -> list[Mapping[str, Any]]:
    if not raw or not raw.endswith(b"\n"):
        raise RecorderError("raw chain must be non-empty and newline terminated")
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
            or not _is_sha256(row["event_hash"])
        ):
            raise RecorderError(f"raw event {seq} chain metadata drifted")
        base = {key: row[key] for key in ("schema_version", "seq", "event", "prev_hash", "payload")}
        if _digest(base) != row["event_hash"]:
            raise RecorderError(f"raw event {seq} hash mismatch")
        _validate_payload(str(row["event"]), row["payload"], f"raw event {seq}.payload")
        rows.append(row)
        previous = str(row["event_hash"])
    return rows


def derive_inner_summary(raw: bytes) -> dict[str, object]:
    rows = parse_chain(raw)
    names = [str(row["event"]) for row in rows]
    if (
        len(rows) < 7
        or names[:3] != ["GENESIS", "CGROUP_START", "CHILD_SPAWN"]
        or names[-3:] != ["CHILD_WAIT", "CGROUP_END", "SEAL"]
        or any(name != "SAMPLE" for name in names[3:-3])
        or not names[3:-3]
    ):
        raise RecorderError("raw event sequence is incomplete")
    genesis = rows[0]["payload"]
    snapshots = [row["payload"] for row in rows if row["event"] in {"CGROUP_START", "SAMPLE", "CGROUP_END"}]
    spawn = rows[2]["payload"]
    wait = rows[-3]["payload"]
    seal = rows[-1]["payload"]
    if seal["sealed_event_count"] != len(rows) - 1:
        raise RecorderError("SEAL event count mismatch")
    times = [
        genesis["monotonic_ns"],
        *[snapshot["monotonic_ns"] for snapshot in snapshots],
        spawn["monotonic_ns"],
        wait["monotonic_ns"],
        seal["monotonic_ns"],
    ]
    ordered_times = [
        genesis["monotonic_ns"],
        snapshots[0]["monotonic_ns"],
        spawn["monotonic_ns"],
        *[snapshot["monotonic_ns"] for snapshot in snapshots[1:-1]],
        wait["monotonic_ns"],
        snapshots[-1]["monotonic_ns"],
        seal["monotonic_ns"],
    ]
    if any(left > right for left, right in zip(ordered_times, ordered_times[1:])) or any(
        type(item) is not int for item in times
    ):
        raise RecorderError("raw monotonic interval moved backwards")
    identity_tuple = (
        genesis["unit_name"],
        genesis["invocation_id"],
    )
    cgroup_tuple = None
    event_keys = set(snapshots[0]["memory_events"])
    limit_violations = 0
    for snapshot in snapshots:
        if (snapshot["unit_name"], snapshot["invocation_id"]) != identity_tuple:
            raise RecorderError("unit or InvocationID drifted inside raw chain")
        current_cgroup = (
            snapshot["cgroup_path"],
            snapshot["cgroup_dev"],
            snapshot["cgroup_inode"],
        )
        cgroup_tuple = current_cgroup if cgroup_tuple is None else cgroup_tuple
        if current_cgroup != cgroup_tuple or spawn["cgroup_path"] != snapshot["cgroup_path"]:
            raise RecorderError("cgroup identity drifted inside raw chain")
        if set(snapshot["memory_events"]) != event_keys:
            raise RecorderError("memory.events key set drifted")
        memory = snapshot["memory"]
        ancestors = _validate_ancestors(snapshot["ancestor_limits"], "snapshot.ancestor_limits")
        if (
            memory["high"] != CONTRACT["memory_high_bytes"]
            or memory["max"] != CONTRACT["memory_max_bytes"]
            or memory["swap_max"] != CONTRACT["memory_swap_max_bytes"]
            or not _ancestor_contract_ok(ancestors)
        ):
            limit_violations += 1
    deltas = {
        key: snapshots[-1]["memory_events"][key] - snapshots[0]["memory_events"][key] for key in sorted(event_keys)
    }
    if any(value < 0 for value in deltas.values()):
        raise RecorderError("memory.events moved backwards")
    peak = max(snapshot["memory"]["peak"] for snapshot in snapshots)
    swap_peak = max(snapshot["memory"]["swap_peak"] for snapshot in snapshots)
    returncode = wait["returncode"]
    exit_code = returncode if returncode >= 0 else None
    exit_signal = -returncode if returncode < 0 else None
    kill_count = wait["term_sent"] + wait["kill_sent"] + (1 if exit_signal is not None else 0)
    timeout_count = 1 if wait["timed_out"] else 0
    event_violation_count = sum(1 for value in deltas.values() if value != 0)
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
    return {
        "schema_version": "noncert-cuts-gate1-inner-resource-summary-v2",
        "run_nonce": genesis["run_nonce"],
        "package_id": genesis["package_id"],
        "selection_id": genesis["selection_id"],
        "arm": genesis["arm"],
        "unit_name": genesis["unit_name"],
        "invocation_id": genesis["invocation_id"],
        "boot_id": genesis["boot_id"],
        "cgroup": {
            "path": cgroup_tuple[0],
            "dev": cgroup_tuple[1],
            "inode": cgroup_tuple[2],
        },
        "interval": {
            "started_monotonic_ns": spawn["monotonic_ns"],
            "finished_monotonic_ns": wait["monotonic_ns"],
            "wall_nanoseconds": wait["monotonic_ns"] - spawn["monotonic_ns"],
        },
        "observation_interval": {
            "started_monotonic_ns": snapshots[0]["monotonic_ns"],
            "finished_monotonic_ns": snapshots[-1]["monotonic_ns"],
            "wall_nanoseconds": (snapshots[-1]["monotonic_ns"] - snapshots[0]["monotonic_ns"]),
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
            "event_deltas": deltas,
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


def _read_json_once(path: Path) -> object:
    raw, identity = snapshot_file(path)
    return _strict_loads(raw, str(identity["path"]))


def _write_exclusive(path: Path, raw: bytes) -> None:
    absolute = path.absolute()
    if absolute.exists() or absolute.is_symlink() or not absolute.parent.is_dir() or absolute.parent.is_symlink():
        raise RecorderError(f"refusing non-exclusive output: {absolute}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(absolute, flags, 0o600)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise RecorderError(f"short write for {absolute}")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify-chain")
    verify.add_argument("--input", type=Path, required=True)
    verify.add_argument("--output", type=Path)
    future = subparsers.add_parser("future-run-arm")
    future.add_argument("--launch-selection", type=Path, required=True)
    future.add_argument("--expected-selection-size", type=int, required=True)
    future.add_argument("--expected-selection-sha256", required=True)
    future.add_argument("--arm", choices=("control", "treatment"), required=True)
    future.add_argument("--unit-name", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "verify-chain":
        raw, _ = snapshot_file(args.input)
        result = derive_inner_summary(raw)
        encoded = json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
        if args.output is not None:
            _write_exclusive(args.output, encoded)
        print(encoded.decode("utf-8"), end="")
        return 0
    load_paired_launch_selection(
        args.launch_selection,
        expected_identity={
            "path": str(args.launch_selection.absolute()),
            "size_bytes": args.expected_selection_size,
            "sha256": args.expected_selection_sha256,
        },
        arm=args.arm,
        unit_name=args.unit_name,
    )
    raise RecorderError(
        "live arm execution is disabled in v2; a separately authorized launcher must supply the recorder loop"
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RecorderError as exc:
        print(json.dumps({"status": "REFUSED", "error": str(exc)}, sort_keys=True))
        raise SystemExit(2) from exc
