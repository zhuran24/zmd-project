#!/usr/bin/env python3
"""Outside-unit Gate 1 launch selection and terminal-state observer.

The observer consumes the exact no-overwrite direct launch-selection bytes,
waits outside the selected systemd unit until it is terminal, joins the unit's
InvocationID to the sealed inner resource chain, and freezes one terminal
envelope with O_EXCL.  Tests inject a fake adapter; the production adapter is
available but this closeout never invokes it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence


SELECTION_SCHEMA = "noncert-cuts-gate1-launch-selection-v3"
TERMINAL_SCHEMA = "noncert-cuts-gate1-launch-terminal-envelope-v1"
RECEIPT_SCHEMA = "noncert-cuts-gate1-paired-resource-receipt-v1"
RAW_SCHEMA = "noncert-cuts-gate1-inner-resource-chain-v2"
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
SYSTEMD_PROPERTIES = (
    "ActiveState",
    "SubState",
    "Result",
    "ExecMainCode",
    "ExecMainStatus",
    "InvocationID",
    "ControlGroup",
    "ActiveEnterTimestampMonotonic",
    "InactiveEnterTimestampMonotonic",
    "MemoryHigh",
    "MemoryMax",
    "MemorySwapMax",
    "OOMPolicy",
    "KillMode",
    "SendSIGKILL",
    "RuntimeMaxUSec",
)


class ObserverError(ValueError):
    """A direct authority or terminal observation failed closed."""


class TerminalQuery(Protocol):
    """Unit-external query surface used by :func:`observe_terminal_unit`."""

    def show(self, unit_name: str) -> Mapping[str, str]: ...

    def cgroup_events(self, control_group: str) -> tuple[bool, Mapping[str, int]]: ...


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
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
        raise ObserverError(f"{field} must be an exact integer >= {minimum}")
    return value


def _exact_keys(value: object, keys: set[str], field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ObserverError(f"{field} key set drifted")
    return value


def _utc(value: object, field: str) -> str:
    if type(value) is not str:
        raise ObserverError(f"{field} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ObserverError(f"{field} is not an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ObserverError(f"{field} must carry UTC")
    return value


def _identity(value: object, field: str) -> Mapping[str, Any]:
    record = _exact_keys(value, {"path", "size_bytes", "sha256"}, field)
    if (
        type(record["path"]) is not str
        or not Path(record["path"]).is_absolute()
        or type(record["size_bytes"]) is not int
        or record["size_bytes"] < 0
        or not _is_hex(record["sha256"], 64)
    ):
        raise ObserverError(f"{field} is not a strict file identity")
    return record


def _strict_loads(raw: bytes, field: str) -> object:
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ObserverError(f"{field} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=no_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ObserverError(f"{field} contains invalid constant {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ObserverError(f"{field} is not strict UTF-8 JSON") from exc


def _reject_symlink_components(path: Path) -> Path:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise ObserverError(f"input path is unavailable: {absolute}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ObserverError(f"input path contains a symlink: {absolute}")
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
    """Read, hash, and identify one O_NOFOLLOW descriptor snapshot."""

    absolute = _reject_symlink_components(path)
    before_path = os.stat(absolute, follow_symlinks=False)
    if not stat.S_ISREG(before_path.st_mode):
        raise ObserverError(f"input is not a regular file: {absolute}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise ObserverError(f"cannot open input: {absolute}") from exc
    try:
        before = os.fstat(descriptor)
        if _snapshot_signature(before_path) != _snapshot_signature(before):
            raise ObserverError(f"input path changed before read: {absolute}")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                raise ObserverError(f"input was truncated: {absolute}")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise ObserverError(f"input grew during read: {absolute}")
        after = os.fstat(descriptor)
        named = os.stat(absolute, follow_symlinks=False)
        if _snapshot_signature(before) != _snapshot_signature(after):
            raise ObserverError(f"input descriptor changed during read: {absolute}")
        if (
            stat.S_ISLNK(named.st_mode)
            or not stat.S_ISREG(named.st_mode)
            or named.st_dev != after.st_dev
            or named.st_ino != after.st_ino
        ):
            raise ObserverError(f"input path changed after read: {absolute}")
    finally:
        os.close(descriptor)
    raw = b"".join(chunks)
    return raw, {
        "path": str(absolute),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def file_identity(path: Path) -> dict[str, object]:
    _, identity = snapshot_file(path)
    return identity


def _identity_map(value: object, field: str) -> Mapping[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping) or not value:
        raise ObserverError(f"{field} must be a non-empty object")
    result: dict[str, Mapping[str, Any]] = {}
    for role, raw_identity in value.items():
        if type(role) is not str or not role:
            raise ObserverError(f"{field} contains an invalid role")
        result[role] = _identity(raw_identity, f"{field}.{role}")
    return result


def _selection_digest(selection: Mapping[str, Any]) -> str:
    body = dict(selection)
    body.pop("selection_id", None)
    return _digest(body)


def validate_selection(selection: object) -> Mapping[str, Any]:
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
        "direct launch selection",
    )
    if record["schema"] != SELECTION_SCHEMA:
        raise ObserverError("direct launch selection schema mismatch")
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
        raise ObserverError("direct launch selection semantics drifted")
    _identity(record["qualification_receipt_identity"], "selection.qualification_receipt_identity")
    tools = _identity_map(record["tools"], "selection.tools")
    _identity_map(record["inputs"], "selection.inputs")
    observer_role = record["terminal_observer_tool_role"]
    if type(observer_role) is not str or observer_role not in tools:
        raise ObserverError("terminal observer tool role is not selection-bound")
    arms = _exact_keys(record["arms"], {"control", "treatment"}, "selection.arms")
    units: set[str] = set()
    attempts: set[str] = set()
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
            for name in ("attempt_dir", "result_path", "raw_output_path", "terminal_envelope_path")
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
            raise ObserverError(f"direct selection arm {label} semantics drifted")
        units.add(arm["unit_name"])
        attempts.add(str(paths["attempt_dir"]))
    if len(units) != 2 or len(attempts) != 2:
        raise ObserverError("paired selection units and attempts must be distinct")
    if _selection_digest(record) != record["selection_id"]:
        raise ObserverError("direct launch selection digest mismatch")
    return record


def load_selection(
    path: Path,
    *,
    expected_identity: Mapping[str, object],
) -> tuple[Mapping[str, Any], Mapping[str, object]]:
    raw, identity = snapshot_file(path)
    if identity != _identity(expected_identity, "expected selection identity"):
        raise ObserverError("direct launch selection detached identity drifted")
    selection = validate_selection(_strict_loads(raw, "direct launch selection"))
    role = selection["terminal_observer_tool_role"]
    if selection["tools"][role] != file_identity(Path(__file__)):
        raise ObserverError("selected terminal observer tool identity drifted")
    return selection, identity


def _parse_inner_binding(raw: bytes) -> Mapping[str, Any]:
    if not raw or not raw.endswith(b"\n"):
        raise ObserverError("inner raw chain is absent or unsealed")
    rows = raw.splitlines()
    first = _strict_loads(rows[0], "inner GENESIS")
    last = _strict_loads(rows[-1], "inner SEAL")
    if not isinstance(first, Mapping) or not isinstance(last, Mapping):
        raise ObserverError("inner chain endpoints are malformed")
    if (
        first.get("schema_version") != RAW_SCHEMA
        or first.get("seq") != 0
        or first.get("event") != "GENESIS"
        or last.get("schema_version") != RAW_SCHEMA
        or last.get("seq") != len(rows) - 1
        or last.get("event") != "SEAL"
    ):
        raise ObserverError("inner raw chain lacks GENESIS/SEAL endpoints")
    genesis = first.get("payload")
    seal = last.get("payload")
    if not isinstance(genesis, Mapping) or not isinstance(seal, Mapping):
        raise ObserverError("inner chain endpoint payload is malformed")
    return {"genesis": genesis, "seal": seal}


def _systemd_int(value: object, field: str) -> int:
    if type(value) is not str or not value.isdigit():
        raise ObserverError(f"systemd {field} is not a canonical unsigned integer")
    return int(value)


def _systemd_bool(value: object, field: str) -> bool:
    if value == "yes":
        return True
    if value == "no":
        return False
    raise ObserverError(f"systemd {field} is not yes/no")


def _validate_systemd_contract(properties: Mapping[str, str]) -> None:
    expected = {
        "MemoryHigh": CONTRACT["memory_high_bytes"],
        "MemoryMax": CONTRACT["memory_max_bytes"],
        "MemorySwapMax": CONTRACT["memory_swap_max_bytes"],
        "RuntimeMaxUSec": CONTRACT["runtime_max_seconds"] * 1_000_000,
    }
    if any(_systemd_int(properties[name], name) != value for name, value in expected.items()):
        raise ObserverError("terminal systemd resource contract drifted")
    if (
        properties["OOMPolicy"] != CONTRACT["oom_policy"]
        or properties["KillMode"] != CONTRACT["kill_mode"]
        or _systemd_bool(properties["SendSIGKILL"], "SendSIGKILL") is not True
    ):
        raise ObserverError("terminal systemd kill/OOM contract drifted")


def validate_terminal_envelope(value: object) -> Mapping[str, Any]:
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
        raise ObserverError("terminal envelope schema mismatch")
    _utc(record["observed_at_utc"], "terminal.observed_at_utc")
    for name in (
        "selection_identity",
        "inner_raw_identity",
        "arm_result_identity",
        "observer_identity",
    ):
        _identity(record[name], f"terminal.{name}")
    for field, length in (
        ("selection_id", 64),
        ("package_id", 64),
        ("invocation_id", 32),
        ("boot_id", 32),
    ):
        if not _is_hex(record[field], length):
            raise ObserverError(f"terminal.{field} is invalid")
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
        raise ObserverError("terminal envelope fields are invalid")
    start = _exact_int(record["active_enter_monotonic_ns"], "terminal.active_enter_monotonic_ns")
    finish = _exact_int(record["inactive_enter_monotonic_ns"], "terminal.inactive_enter_monotonic_ns")
    if finish < start:
        raise ObserverError("terminal interval moved backwards")
    events = _exact_keys(record["cgroup_events"], {"populated", "frozen"}, "terminal.cgroup_events")
    for name, item in events.items():
        _exact_int(item, f"terminal.cgroup_events.{name}")
    if record["cgroup_empty"] is not (events["populated"] == 0):
        raise ObserverError("terminal cgroup_empty does not derive from cgroup.events")
    return record


def build_terminal_envelope(**fields: object) -> dict[str, object]:
    record = {"schema_version": TERMINAL_SCHEMA, **fields}
    validate_terminal_envelope(record)
    return record


class SystemctlShowAdapter:
    """Production unit-external adapter; never instantiated by closeout tests."""

    def show(self, unit_name: str) -> Mapping[str, str]:
        command = ["systemctl", "show", "--no-pager"]
        command.extend(f"--property={name}" for name in SYSTEMD_PROPERTIES)
        command.append(unit_name)
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if completed.returncode != 0:
            raise ObserverError(f"systemctl show failed for {unit_name}: {completed.stderr.strip()}")
        result: dict[str, str] = {}
        for line in completed.stdout.splitlines():
            if "=" not in line:
                raise ObserverError("systemctl show emitted a malformed property")
            key, value = line.split("=", 1)
            if key in result:
                raise ObserverError(f"systemctl show duplicated {key}")
            result[key] = value
        if set(result) != set(SYSTEMD_PROPERTIES):
            raise ObserverError("systemctl show property set drifted")
        return result

    def cgroup_events(self, control_group: str) -> tuple[bool, Mapping[str, int]]:
        relative = control_group.removeprefix("/")
        path = Path("/sys/fs/cgroup") / relative / "cgroup.events"
        try:
            absolute = _reject_symlink_components(path)
            descriptor = os.open(
                absolute,
                os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
            )
        except (ObserverError, FileNotFoundError):
            if not os.path.lexists(path):
                return False, {"populated": 0, "frozen": 0}
            raise
        try:
            before = os.fstat(descriptor)
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 4096)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(descriptor)
            named = os.lstat(absolute)
            if (
                before.st_dev != after.st_dev
                or before.st_ino != after.st_ino
                or named.st_dev != after.st_dev
                or named.st_ino != after.st_ino
            ):
                raise ObserverError("cgroup.events identity drifted during read")
        finally:
            os.close(descriptor)
        raw = b"".join(chunks)
        values: dict[str, int] = {}
        try:
            for line in raw.decode("ascii").splitlines():
                key, raw_value = line.split()
                if key in values or not raw_value.isdigit():
                    raise ValueError
                values[key] = int(raw_value)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ObserverError("cgroup.events is malformed") from exc
        if not {"populated", "frozen"} <= set(values):
            raise ObserverError("cgroup.events lacks populated/frozen")
        return True, {"populated": values["populated"], "frozen": values["frozen"]}


def observe_terminal_unit(
    *,
    selection_path: Path,
    expected_selection_identity: Mapping[str, object],
    arm: str,
    adapter: TerminalQuery,
    timeout_seconds: float = 30.0,
    poll_seconds: float = 0.05,
    sleep: Any = time.sleep,
    monotonic: Any = time.monotonic,
    now_utc: Any = lambda: datetime.now(timezone.utc),
) -> dict[str, object]:
    """Wait outside one selected unit and O_EXCL-freeze its terminal envelope."""

    selection, selection_identity = load_selection(
        selection_path,
        expected_identity=expected_selection_identity,
    )
    if arm not in {"control", "treatment"}:
        raise ObserverError("arm must be control or treatment")
    selected = selection["arms"][arm]
    deadline = monotonic() + timeout_seconds
    invocation_id: str | None = None
    control_group: str | None = None
    final: Mapping[str, str] | None = None
    while monotonic() <= deadline:
        properties = adapter.show(selected["unit_name"])
        if set(properties) != set(SYSTEMD_PROPERTIES):
            raise ObserverError("terminal query property set drifted")
        current_invocation = properties["InvocationID"]
        current_group = properties["ControlGroup"]
        if not _is_hex(current_invocation, 32) or not current_group.startswith("/"):
            raise ObserverError("terminal query unit/cgroup identity is invalid")
        invocation_id = invocation_id or current_invocation
        control_group = control_group or current_group
        if current_invocation != invocation_id or current_group != control_group:
            raise ObserverError("unit InvocationID or ControlGroup changed while observed")
        if properties["ActiveState"] in {"inactive", "failed"}:
            final = properties
            break
        sleep(poll_seconds)
    if final is None or invocation_id is None or control_group is None:
        raise ObserverError("selected unit did not reach a terminal state before timeout")
    _validate_systemd_contract(final)
    raw_path = Path(selected["raw_output_path"])
    raw, raw_identity = snapshot_file(raw_path)
    endpoints = _parse_inner_binding(raw)
    genesis = endpoints["genesis"]
    seal = endpoints["seal"]
    expected_bindings = {
        "selection_identity": selection_identity,
        "selection_id": selection["selection_id"],
        "run_nonce": selection["run_nonce"],
        "package_id": selection["package_id"],
        "arm": arm,
        "unit_name": selected["unit_name"],
        "invocation_id": invocation_id,
    }
    if any(genesis.get(name) != expected for name, expected in expected_bindings.items()):
        raise ObserverError("inner GENESIS does not join the selected terminal unit")
    inactive_usec = _systemd_int(
        final["InactiveEnterTimestampMonotonic"],
        "InactiveEnterTimestampMonotonic",
    )
    active_usec = _systemd_int(
        final["ActiveEnterTimestampMonotonic"],
        "ActiveEnterTimestampMonotonic",
    )
    active = active_usec * 1_000
    inactive = inactive_usec * 1_000
    sealed = _exact_int(seal.get("monotonic_ns"), "inner SEAL monotonic_ns")
    if inactive < sealed:
        raise ObserverError("unit terminal timestamp precedes the inner SEAL")
    result_path = Path(selected["result_path"])
    _, result_identity = snapshot_file(result_path)
    path_present = False
    events: Mapping[str, int] | None = None
    while monotonic() <= deadline:
        path_present, current_events = adapter.cgroup_events(control_group)
        if set(current_events) != {"populated", "frozen"}:
            raise ObserverError("terminal cgroup.events key set drifted")
        if current_events["populated"] == 0:
            events = current_events
            break
        sleep(poll_seconds)
    if events is None:
        raise ObserverError("selected unit cgroup did not become empty before timeout")
    stable_final = adapter.show(selected["unit_name"])
    for name in SYSTEMD_PROPERTIES:
        if stable_final.get(name) != final[name]:
            raise ObserverError(f"terminal systemd property changed after inner SEAL: {name}")
    observer_role = selection["terminal_observer_tool_role"]
    envelope = build_terminal_envelope(
        observed_at_utc=now_utc().isoformat().replace("+00:00", "Z"),
        selection_identity=selection_identity,
        selection_id=selection["selection_id"],
        run_nonce=selection["run_nonce"],
        package_id=selection["package_id"],
        arm=arm,
        unit_name=selected["unit_name"],
        invocation_id=invocation_id,
        control_group=control_group,
        boot_id=genesis.get("boot_id"),
        active_enter_monotonic_ns=active,
        inactive_enter_monotonic_ns=inactive,
        result=final["Result"],
        exec_main_code=final["ExecMainCode"],
        exec_main_status=int(final["ExecMainStatus"]),
        cgroup_empty=events["populated"] == 0,
        cgroup_path_present=path_present,
        cgroup_events=dict(events),
        inner_raw_identity=raw_identity,
        arm_result_identity=result_identity,
        observer_identity=selection["tools"][observer_role],
    )
    output = Path(selected["terminal_envelope_path"])
    _write_exclusive(
        output,
        json.dumps(envelope, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n",
    )
    return envelope


def build_paired_resource_receipt(
    *,
    created_at_utc: str,
    selection_identity: Mapping[str, object],
    selection: Mapping[str, object],
    arms: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    _utc(created_at_utc, "receipt.created_at_utc")
    _identity(selection_identity, "receipt.selection_identity")
    validated = validate_selection(selection)
    exact_arms = _exact_keys(arms, {"control", "treatment"}, "receipt.arms")
    normalized: dict[str, object] = {}
    for label in ("control", "treatment"):
        arm = _exact_keys(
            exact_arms[label],
            {"raw_chain_identity", "terminal_envelope_identity", "result_identity", "derived"},
            f"receipt.arms.{label}",
        )
        for name in ("raw_chain_identity", "terminal_envelope_identity", "result_identity"):
            _identity(arm[name], f"receipt.arms.{label}.{name}")
        if not isinstance(arm["derived"], Mapping):
            raise ObserverError(f"receipt.arms.{label}.derived must be an object")
        normalized[label] = {
            "raw_chain_identity": dict(arm["raw_chain_identity"]),
            "terminal_envelope_identity": dict(arm["terminal_envelope_identity"]),
            "result_identity": dict(arm["result_identity"]),
            "derived": dict(arm["derived"]),
        }
    body: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "created_at_utc": created_at_utc,
        "selection_identity": dict(selection_identity),
        "run_nonce": validated["run_nonce"],
        "selection_id": validated["selection_id"],
        "contract": dict(CONTRACT),
        "arms": normalized,
        "claim": "resource_evidence_only",
    }
    return {**body, "receipt_id": _digest(body)}


def _write_exclusive(path: Path, raw: bytes) -> None:
    absolute = path.absolute()
    if absolute.exists() or absolute.is_symlink() or not absolute.parent.is_dir():
        raise ObserverError(f"refusing non-exclusive output: {absolute}")
    _reject_symlink_components(absolute.parent)
    descriptor = os.open(
        absolute,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        view = memoryview(raw)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise ObserverError(f"short write for {absolute}")
            view = view[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("kind", choices=("selection", "terminal"))
    validate.add_argument("--input", type=Path, required=True)
    observe = subparsers.add_parser("observe")
    observe.add_argument("--selection", type=Path, required=True)
    observe.add_argument("--expected-selection-size", type=int, required=True)
    observe.add_argument("--expected-selection-sha256", required=True)
    observe.add_argument("--arm", choices=("control", "treatment"), required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "observe":
        observe_terminal_unit(
            selection_path=args.selection,
            expected_selection_identity={
                "path": str(args.selection.absolute()),
                "size_bytes": args.expected_selection_size,
                "sha256": args.expected_selection_sha256,
            },
            arm=args.arm,
            adapter=SystemctlShowAdapter(),
        )
        return 0
    raw, identity = snapshot_file(args.input)
    value = _strict_loads(raw, str(identity["path"]))
    validated = validate_selection(value) if args.kind == "selection" else validate_terminal_envelope(value)
    print(
        json.dumps(
            {
                "status": "PASS",
                "kind": args.kind,
                "input_identity": identity,
                "schema_version": validated.get("schema_version", validated.get("schema")),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ObserverError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, sort_keys=True))
        raise SystemExit(2) from exc
