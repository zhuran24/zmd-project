#!/usr/bin/env python3
"""Independently verify SMM3 two-stage resource and terminal authority.

This verifier deliberately does not import the SMM3 orchestrator.  It consumes
strict JSON receipts through stable O_NOFOLLOW descriptors, independently
parses raw systemd/cgroup observations, and loads the byte-pinned manager epoch
authority tool only to capture the live user-manager/boot epoch.

The ``resource`` mode closes the launch-to-keeper pre-terminal stage.  The
``detached`` mode repeats that validation, closes terminal/cleanup authority,
and, for a formal a002 closeout, independently re-runs VeriPB from a pinned
executable descriptor.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
from types import ModuleType
from typing import Any


AUTHORITY_SCHEMA = "b1_sidewise_smm3_pre_run_authority_v1"
SELECTION_SCHEMA = "b1_sidewise_smm3_attempt_selection_v1"
SYNTHETIC_SELECTION_SCHEMA = "b1_sidewise_smm3_synthetic_selection_v1"
LAUNCH_SCHEMA = "b1_sidewise_smm3_launch_receipt_v1"
PAYLOAD_SPEC_SCHEMA = "b1_sidewise_smm3_payload_spec_v1"
START_TOKEN_SCHEMA = "b1_sidewise_smm3_payload_start_token_v1"
SUPERVISOR_START_SCHEMA = "b1_sidewise_smm3_supervisor_state_v1"
SYNTHETIC_SEAL_SCHEMA = "b1_sidewise_smm3_synthetic_payload_seal_v1"
PAYLOAD_TERMINAL_SCHEMA = "b1_sidewise_smm3_payload_terminal_v1"
PRETERMINAL_SCHEMA = "b1_sidewise_smm3_preterminal_resource_v1"
RELEASE_TOKEN_SCHEMA = "b1_sidewise_smm3_release_token_v1"
TERMINAL_SCHEMA = "b1_sidewise_smm3_terminal_envelope_v1"
CLEANUP_SCHEMA = "b1_sidewise_smm3_cleanup_v1"
RESOURCE_RECEIPT_SCHEMA = "b1_sidewise_smm3_resource_verification_v1"
DETACHED_RECEIPT_SCHEMA = "b1_sidewise_smm3_detached_closeout_v1"
INTERNAL_FORMAL_SCHEMA = "b1_sidewise_smm3_internal_formal_receipt_v1"
MANAGER_EPOCH_SCHEMA = "systemd-user-manager-boot-epoch-v1"

ATTEMPT = "a002"
MEMORY_HIGH = 35 * 1024**3
MEMORY_MAX = 39 * 1024**3
MEMORY_SWAP_MAX = 16 * 1024**3
FORMULA_SIZE = 283
FORMULA_SHA256 = "d4b79cd76c80d23e509ad09b1d2e7fa02fa337049f40459ab803f0fc55a4d865"
PROOF_LIMIT = 5_000_000_000
FORMAL_RUNTIME_MAX_SECONDS = 9000
FORMAL_PAYLOAD_WAIT_SECONDS = 8000
FORMAL_KEEPER_TIMEOUT_SECONDS = 8700
FORMAL_ROUNDINGSAT_TIME_LIMIT_SECONDS = 3600
FORMAL_ROUNDINGSAT_MONITOR_LIMIT_SECONDS = 3900
FORMAL_VERIPB_TIME_LIMIT_SECONDS = 3600
SYNTHETIC_RUNTIME_MAX_SECONDS = 120
SYNTHETIC_PAYLOAD_WAIT_SECONDS = 30
SYNTHETIC_KEEPER_TIMEOUT_SECONDS = 90

JSON_LIMIT = 64 * 1024 * 1024
TEXT_LIMIT = 64 * 1024 * 1024
MANAGER_TOOL_LIMIT = 8 * 1024 * 1024
DEFAULT_VERIPB_TIMEOUT_SECONDS = FORMAL_VERIPB_TIME_LIMIT_SECONDS

STABLE_STAT_FIELDS = (
    "st_dev",
    "st_ino",
    "st_mode",
    "st_nlink",
    "st_uid",
    "st_gid",
    "st_size",
    "st_mtime_ns",
    "st_ctime_ns",
)
IDENTITY_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
    "mode_octal",
)
OPTIONAL_IDENTITY_FIELDS = (
    "device",
    "inode",
    "link_count",
)
RESOURCE_CONTRACT = {
    "MemoryHigh": MEMORY_HIGH,
    "MemoryMax": MEMORY_MAX,
    "MemorySwapMax": MEMORY_SWAP_MAX,
    "OOMPolicy": "continue",
    "KillMode": "control-group",
    "SendSIGKILL": "yes",
}
AUTHORITY_RESOURCE_KEYS = {
    "memory_high_bytes": MEMORY_HIGH,
    "memory_max_bytes": MEMORY_MAX,
    "memory_swap_max_bytes": MEMORY_SWAP_MAX,
    "oom_policy": "continue",
    "kill_mode": "control-group",
    "send_sigkill": "yes",
    "formal_runtime_max_seconds": FORMAL_RUNTIME_MAX_SECONDS,
    "formal_payload_wait_seconds": FORMAL_PAYLOAD_WAIT_SECONDS,
    "formal_keeper_timeout_seconds": FORMAL_KEEPER_TIMEOUT_SECONDS,
    "formal_roundingsat_time_limit_seconds": FORMAL_ROUNDINGSAT_TIME_LIMIT_SECONDS,
    "formal_roundingsat_monitor_limit_seconds": FORMAL_ROUNDINGSAT_MONITOR_LIMIT_SECONDS,
    "formal_veripb_time_limit_seconds": FORMAL_VERIPB_TIME_LIMIT_SECONDS,
}
TIMING_CONTRACT_FIELDS = (
    "runtime_max_seconds",
    "payload_wait_seconds",
    "keeper_timeout_seconds",
    "roundingsat_time_limit_seconds",
    "roundingsat_monitor_limit_seconds",
    "veripb_time_limit_seconds",
)
SYSTEMD_RESOURCE_FIELDS = (
    "MemoryHigh",
    "MemoryMax",
    "MemorySwapMax",
    "OOMPolicy",
    "KillMode",
    "SendSIGKILL",
    "RuntimeMaxUSec",
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
ZERO_EVENT_FIELDS = (
    "high",
    "max",
    "oom",
    "oom_kill",
    "oom_group_kill",
)
VERIPB_SUCCESS = re.compile(r"^s VERIFIED UNSATISFIABLE$")
VERIPB_ERROR_MARKERS = (
    "Error:",
    "Checking error",
    "panic",
    "failed",
    "unsupported",
)
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
BOOT_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
OWNER_RE = re.compile(r":[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\Z")
INVOCATION_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
RUN_NONCE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}\Z")
UNIT_RE = re.compile(r"[A-Za-z0-9_.@:-]+\.service\Z")

# Independently duplicated from the authority runner.  The immutable payload
# specification carries this exact program in argv; accepting an arbitrary
# ``python -c`` loader would make a worker digest merely decorative.
PINNED_SOURCE_LOADER = (
    "import hashlib,os,sys,stat;"
    "p=sys.argv[1];e=sys.argv[2];a=sys.argv[3:];"
    "f=os.open(p,os.O_RDONLY|getattr(os,'O_CLOEXEC',0)|"
    "getattr(os,'O_NOFOLLOW',0));"
    "s=os.fstat(f);"
    "r=b'';"
    "\nwhile True:\n"
    " b=os.read(f,1048576)\n"
    " if not b: break\n"
    " r+=b\n"
    "t=os.fstat(f);os.close(f);"
    "\nif (not stat.S_ISREG(s.st_mode) or "
    "(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)!="
    "(t.st_dev,t.st_ino,t.st_mode,t.st_size,t.st_mtime_ns,t.st_ctime_ns) or "
    "len(r)!=s.st_size or hashlib.sha256(r).hexdigest()!=e): raise SystemExit(125)\n"
    "sys.argv=[p]+a;"
    "g={'__name__':'__main__','__file__':p,'__package__':None,"
    "'__cached__':None};"
    "exec(compile(r,p,'exec',dont_inherit=True),g)"
)


class VerificationError(RuntimeError):
    """Raised whenever an authority or detached-replay check fails closed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise VerificationError(f"{label}: expected an object")
    return value


def _strict_json(raw: bytes, label: str) -> Any:
    def reject_constant(value: str) -> Any:
        raise VerificationError(f"{label}: non-finite JSON number {value!r}")

    def reject_float(value: str) -> Any:
        raise VerificationError(f"{label}: floating-point JSON number {value!r}")

    def unique_object(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise VerificationError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
            parse_float=reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"{label}: invalid strict JSON: {exc}") from exc


def _stable(
    before: os.stat_result,
    after: os.stat_result,
) -> bool:
    return all(getattr(before, field) == getattr(after, field) for field in STABLE_STAT_FIELDS)


def _snapshot_regular(
    path: Path,
    label: str,
    *,
    collect: bool,
    max_bytes: int | None,
) -> tuple[bytes | None, dict[str, Any]]:
    absolute = path.absolute()
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise VerificationError(f"{label}: cannot open: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise VerificationError(f"{label}: not a regular file")
        if before.st_size < 0:
            raise VerificationError(f"{label}: invalid negative size")
        if max_bytes is not None and before.st_size > max_bytes:
            raise VerificationError(f"{label}: size exceeds fixed cap {max_bytes}")
        digest = hashlib.sha256()
        chunks: list[bytes] | None = [] if collect else None
        total = 0
        while True:
            block = os.read(descriptor, 1 << 20)
            if not block:
                break
            total += len(block)
            if max_bytes is not None and total > max_bytes:
                raise VerificationError(f"{label}: read exceeds fixed cap {max_bytes}")
            digest.update(block)
            if chunks is not None:
                chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if not _stable(before, after):
        raise VerificationError(f"{label}: changed during same-FD read")
    if total != before.st_size:
        raise VerificationError(f"{label}: short or extended read")
    identity = {
        "path": str(absolute),
        "size_bytes": total,
        "sha256": digest.hexdigest(),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
        "device": before.st_dev,
        "inode": before.st_ino,
        "link_count": before.st_nlink,
    }
    return (
        None if chunks is None else b"".join(chunks),
        identity,
    )


def _load_json(
    path: Path,
    label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, identity = _snapshot_regular(
        path,
        label,
        collect=True,
        max_bytes=JSON_LIMIT,
    )
    if raw is None:
        raise VerificationError(f"{label}: bytes were not collected")
    payload = _strict_json(raw, label)
    if not isinstance(payload, dict):
        raise VerificationError(f"{label}: root is not an object")
    return payload, identity


def _identity_matches(
    expected: Any,
    actual: Mapping[str, Any],
    label: str,
) -> None:
    record = _mapping(expected, f"{label} expected identity")
    for field in IDENTITY_FIELDS:
        _require(
            record.get(field) == actual.get(field),
            f"{label}: {field} identity mismatch",
        )
    for field in OPTIONAL_IDENTITY_FIELDS:
        if field in record:
            _require(
                record.get(field) == actual.get(field),
                f"{label}: {field} identity mismatch",
            )


def _epoch_tuple(value: Any, label: str) -> tuple[Any, ...]:
    epoch = _mapping(value, label)
    _require(
        epoch.get("schema") == MANAGER_EPOCH_SCHEMA,
        f"{label}: manager epoch schema mismatch",
    )
    boot_id = epoch.get("boot_id")
    owner = epoch.get("dbus_unique_owner")
    pid = epoch.get("manager_pid")
    starttime = epoch.get("manager_pid_starttime")
    executable = _mapping(
        epoch.get("manager_executable"),
        f"{label} executable",
    )
    version = epoch.get("manager_version")
    features = epoch.get("manager_features")
    toolchain = _mapping(
        epoch.get("attestation_toolchain"),
        f"{label} attestation toolchain",
    )
    observation_toolchain = _mapping(
        epoch.get("observation_toolchain"),
        f"{label} observation toolchain",
    )
    observation_busctl = _mapping(
        observation_toolchain.get("busctl"),
        f"{label} observation busctl identity",
    )
    busctl_path = observation_busctl.get("path")
    busctl_size = observation_busctl.get("size_bytes")
    busctl_mode = observation_busctl.get("mode_octal")
    busctl_digest = observation_busctl.get("sha256")
    busctl_device = observation_busctl.get("device")
    busctl_inode = observation_busctl.get("inode")
    _require(
        isinstance(busctl_path, str) and os.path.isabs(busctl_path),
        f"{label}: invalid observation busctl path",
    )
    _require(
        type(busctl_size) is int and busctl_size > 0,
        f"{label}: invalid observation busctl size",
    )
    _require(
        isinstance(busctl_mode, str) and re.fullmatch(r"[0-7]{4}", busctl_mode) is not None,
        f"{label}: invalid observation busctl mode",
    )
    _require(
        isinstance(busctl_digest, str) and SHA256_RE.fullmatch(busctl_digest) is not None,
        f"{label}: invalid observation busctl SHA-256",
    )
    _require(
        type(busctl_device) is int and busctl_device >= 0 and type(busctl_inode) is int and busctl_inode > 0,
        f"{label}: invalid observation busctl device/inode",
    )
    tool_values: list[Any] = []
    for tool_name in ("attestor", "sudo", "python"):
        tool = _mapping(
            toolchain.get(tool_name),
            f"{label} {tool_name} identity",
        )
        tool_path = tool.get("path")
        tool_size = tool.get("size_bytes")
        tool_mode = tool.get("mode_octal")
        tool_digest = tool.get("sha256")
        tool_device = tool.get("device")
        tool_inode = tool.get("inode")
        _require(
            isinstance(tool_path, str) and os.path.isabs(tool_path),
            f"{label}: invalid {tool_name} path",
        )
        _require(
            type(tool_size) is int and tool_size > 0,
            f"{label}: invalid {tool_name} size",
        )
        _require(
            isinstance(tool_mode, str) and re.fullmatch(r"[0-7]{4}", tool_mode) is not None,
            f"{label}: invalid {tool_name} mode",
        )
        _require(
            isinstance(tool_digest, str) and SHA256_RE.fullmatch(tool_digest) is not None,
            f"{label}: invalid {tool_name} SHA-256",
        )
        _require(
            type(tool_device) is int and type(tool_inode) is int,
            f"{label}: invalid {tool_name} device/inode",
        )
        tool_values.extend(
            (
                tool_path,
                tool_size,
                tool_mode,
                tool_digest,
                tool_device,
                tool_inode,
            )
        )
    path = executable.get("path")
    size_bytes = executable.get("size_bytes")
    mode = executable.get("mode")
    digest = executable.get("sha256")
    executable_device = executable.get("device")
    executable_inode = executable.get("inode")
    _require(
        isinstance(boot_id, str) and BOOT_ID_RE.fullmatch(boot_id) is not None,
        f"{label}: invalid boot_id",
    )
    _require(
        isinstance(owner, str) and OWNER_RE.fullmatch(owner) is not None,
        f"{label}: invalid D-Bus unique owner",
    )
    _require(
        type(pid) is int and pid > 0,
        f"{label}: invalid manager PID",
    )
    _require(
        type(starttime) is int and starttime > 0,
        f"{label}: invalid manager PID starttime",
    )
    _require(
        isinstance(path, str) and os.path.isabs(path),
        f"{label}: invalid manager executable path",
    )
    _require(
        type(size_bytes) is int and size_bytes > 0,
        f"{label}: invalid manager executable size",
    )
    _require(
        type(mode) is int and 0 <= mode <= 0o7777,
        f"{label}: invalid manager executable mode",
    )
    _require(
        isinstance(digest, str) and SHA256_RE.fullmatch(digest) is not None,
        f"{label}: invalid manager executable SHA-256",
    )
    _require(
        type(executable_device) is int and type(executable_inode) is int,
        f"{label}: invalid manager executable device/inode",
    )
    _require(
        isinstance(version, str) and bool(version),
        f"{label}: invalid manager Version",
    )
    _require(
        isinstance(features, str) and bool(features),
        f"{label}: invalid manager Features",
    )
    return (
        boot_id,
        owner,
        pid,
        starttime,
        path,
        size_bytes,
        mode,
        digest,
        executable_device,
        executable_inode,
        version,
        features,
        busctl_path,
        busctl_size,
        busctl_mode,
        busctl_digest,
        busctl_device,
        busctl_inode,
        *tool_values,
    )


def _same_epoch(left: Any, right: Any) -> bool:
    try:
        return _epoch_tuple(left, "left manager epoch") == _epoch_tuple(right, "right manager epoch")
    except VerificationError:
        return False


def _capture_current_epoch(
    authority: Mapping[str, Any],
    tool_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    tools = _mapping(authority.get("tools"), "authority tools")
    expected = tools.get("manager_epoch")
    raw, tool_identity = _snapshot_regular(
        tool_path,
        "manager epoch authority tool",
        collect=True,
        max_bytes=MANAGER_TOOL_LIMIT,
    )
    if raw is None:
        raise VerificationError("manager epoch tool bytes not collected")
    _identity_matches(
        expected,
        tool_identity,
        "manager epoch authority tool",
    )
    module_name = "_smm3_pinned_manager_epoch_authority_v1"
    module = ModuleType(module_name)
    module.__file__ = str(tool_path.absolute())
    module.__package__ = None
    sys.modules[module_name] = module
    try:
        code = compile(
            raw,
            str(tool_path.absolute()),
            "exec",
            dont_inherit=True,
        )
        exec(code, module.__dict__)
        capture = getattr(module, "capture_manager_epoch", None)
        _require(
            callable(capture),
            "pinned manager epoch tool has no capture_manager_epoch",
        )
        current = capture()
    except VerificationError:
        raise
    except Exception as exc:
        raise VerificationError(f"pinned manager epoch capture failed: {exc}") from exc
    finally:
        sys.modules.pop(module_name, None)
    _epoch_tuple(current, "captured current manager epoch")
    _, replay_identity = _snapshot_regular(
        tool_path,
        "manager epoch authority tool replay",
        collect=False,
        max_bytes=MANAGER_TOOL_LIMIT,
    )
    _require(
        replay_identity == tool_identity,
        "manager epoch authority tool drifted during capture",
    )
    return dict(current), tool_identity


def _schema(
    record: Mapping[str, Any],
    expected: str | tuple[str, ...],
    label: str,
) -> None:
    accepted = (expected,) if isinstance(expected, str) else expected
    _require(
        record.get("schema_version") in accepted,
        f"{label}: schema mismatch",
    )


def _run_nonce(record: Mapping[str, Any], label: str) -> str:
    value = record.get("run_nonce")
    _require(
        isinstance(value, str) and RUN_NONCE_RE.fullmatch(value) is not None,
        f"{label}: invalid run_nonce",
    )
    return value


def _unit(record: Mapping[str, Any], label: str) -> str:
    value = record.get("unit")
    _require(
        isinstance(value, str) and UNIT_RE.fullmatch(value) is not None,
        f"{label}: invalid unit",
    )
    return value


def _invocation_id(record: Mapping[str, Any], label: str) -> str:
    value = record.get("invocation_id")
    _require(
        isinstance(value, str) and INVOCATION_ID_RE.fullmatch(value) is not None,
        f"{label}: invalid InvocationID",
    )
    return value


def _positive_pid(value: Any, label: str) -> int:
    _require(
        type(value) is int and value > 0,
        f"{label}: invalid PID",
    )
    return value


def _positive_monotonic(value: Any, label: str) -> int:
    _require(
        type(value) is int and value > 0,
        f"{label}: invalid monotonic timestamp",
    )
    return value


def _purpose(record: Mapping[str, Any], label: str) -> str:
    value = record.get("purpose")
    accepted = {
        "synthetic_success",
        "synthetic_postseal_failure",
        "formal",
    }
    _require(
        isinstance(value, str) and value in accepted,
        f"{label}: invalid purpose",
    )
    return value


def _identity_content_matches(
    expected: Any,
    actual: Mapping[str, Any],
    label: str,
) -> None:
    record = _mapping(expected, f"{label} expected identity")
    for field in ("size_bytes", "sha256", "mode_octal"):
        _require(
            record.get(field) == actual.get(field),
            f"{label}: {field} content identity mismatch",
        )


def _identity_record(value: Any, label: str) -> Mapping[str, Any]:
    record = _mapping(value, label)
    path = record.get("path")
    size_bytes = record.get("size_bytes")
    sha256 = record.get("sha256")
    mode = record.get("mode_octal")
    _require(
        isinstance(path, str) and os.path.isabs(path),
        f"{label}: invalid absolute path",
    )
    _require(
        type(size_bytes) is int and size_bytes >= 0,
        f"{label}: invalid size",
    )
    _require(
        isinstance(sha256, str) and SHA256_RE.fullmatch(sha256) is not None,
        f"{label}: invalid SHA-256",
    )
    _require(
        isinstance(mode, str) and re.fullmatch(r"[0-7]{4}", mode) is not None,
        f"{label}: invalid mode",
    )
    return record


def _normalize_contract(
    value: Any,
    label: str,
) -> dict[str, int | str]:
    contract = _mapping(value, label)
    normalized: dict[str, int | str] = {}
    uses_authority_names = all(key in contract for key in AUTHORITY_RESOURCE_KEYS)
    _require(
        uses_authority_names,
        f"{label}: authority-rooted formal budget fields are incomplete",
    )
    source = AUTHORITY_RESOURCE_KEYS
    for source_key, expected in source.items():
        actual = contract.get(source_key)
        if isinstance(expected, int):
            if isinstance(actual, str) and actual.isdecimal():
                actual = int(actual, 10)
            _require(
                type(actual) is int and actual == expected,
                f"{label}: {source_key} mismatch",
            )
        else:
            _require(
                actual == expected,
                f"{label}: {source_key} mismatch",
            )
    for normalized_key, expected in RESOURCE_CONTRACT.items():
        normalized[normalized_key] = expected
    for formal_key in (
        "formal_runtime_max_seconds",
        "formal_payload_wait_seconds",
        "formal_keeper_timeout_seconds",
        "formal_roundingsat_time_limit_seconds",
        "formal_roundingsat_monitor_limit_seconds",
        "formal_veripb_time_limit_seconds",
    ):
        normalized[formal_key] = AUTHORITY_RESOURCE_KEYS[formal_key]
    return normalized


def _expected_timing_contract(purpose: str) -> dict[str, int]:
    formal = purpose == "formal"
    return {
        "runtime_max_seconds": (FORMAL_RUNTIME_MAX_SECONDS if formal else SYNTHETIC_RUNTIME_MAX_SECONDS),
        "payload_wait_seconds": (FORMAL_PAYLOAD_WAIT_SECONDS if formal else SYNTHETIC_PAYLOAD_WAIT_SECONDS),
        "keeper_timeout_seconds": (FORMAL_KEEPER_TIMEOUT_SECONDS if formal else SYNTHETIC_KEEPER_TIMEOUT_SECONDS),
        "roundingsat_time_limit_seconds": FORMAL_ROUNDINGSAT_TIME_LIMIT_SECONDS,
        "roundingsat_monitor_limit_seconds": FORMAL_ROUNDINGSAT_MONITOR_LIMIT_SECONDS,
        "veripb_time_limit_seconds": FORMAL_VERIPB_TIME_LIMIT_SECONDS,
    }


def _normalize_timing_contract(
    value: Any,
    purpose: str,
    authority_contract: Mapping[str, int | str],
    label: str,
) -> dict[str, int]:
    contract = _mapping(value, label)
    expected = _expected_timing_contract(purpose)
    _require(
        set(TIMING_CONTRACT_FIELDS).issubset(contract),
        f"{label}: incomplete timing contract",
    )
    for key, expected_value in expected.items():
        _require(
            type(contract.get(key)) is int and contract.get(key) == expected_value,
            f"{label}: {key} mismatch",
        )
    authority_joins = {
        "runtime_max_seconds": "formal_runtime_max_seconds",
        "payload_wait_seconds": "formal_payload_wait_seconds",
        "keeper_timeout_seconds": "formal_keeper_timeout_seconds",
        "roundingsat_time_limit_seconds": "formal_roundingsat_time_limit_seconds",
        "roundingsat_monitor_limit_seconds": "formal_roundingsat_monitor_limit_seconds",
        "veripb_time_limit_seconds": "formal_veripb_time_limit_seconds",
    }
    for timing_key, authority_key in authority_joins.items():
        if purpose == "formal" or timing_key.startswith(("roundingsat_", "veripb_")):
            _require(
                contract[timing_key] == authority_contract[authority_key],
                f"{label}: {timing_key} is detached from authority resource contract",
            )
    return expected


def _raw_mapping(
    record: Mapping[str, Any],
    field: str,
    required: tuple[str, ...],
    label: str,
) -> Mapping[str, Any]:
    raw = _mapping(record.get(field), f"{label} {field}")
    missing = [name for name in required if name not in raw]
    _require(
        not missing,
        f"{label} {field}: missing {', '.join(missing)}",
    )
    for name in required:
        value = raw[name]
        _require(
            isinstance(value, str) and value.endswith("\n") and "\x00" not in value,
            f"{label} {field}.{name}: not preserved raw text",
        )
    return raw


def _raw_scalar(raw: Mapping[str, Any], name: str, label: str) -> str:
    value = raw[name]
    _require(
        isinstance(value, str) and value.endswith("\n") and value.count("\n") == 1,
        f"{label}.{name}: not a one-line raw scalar",
    )
    return value[:-1]


def _raw_nonnegative_int(
    raw: Mapping[str, Any],
    name: str,
    label: str,
) -> int:
    value = _raw_scalar(raw, name, label)
    _require(
        value.isdecimal(),
        f"{label}.{name}: not a nonnegative integer",
    )
    return int(value, 10)


def _raw_duration_usec(
    raw: Mapping[str, Any],
    name: str,
    label: str,
) -> int:
    value = _raw_scalar(raw, name, label)
    if value.isdecimal():
        return int(value, 10)
    units = {
        "h": 60 * 60 * 1_000_000,
        "min": 60 * 1_000_000,
        "s": 1_000_000,
        "ms": 1_000,
        "us": 1,
    }
    cursor = 0
    total = 0
    token = re.compile(r"(?:^| )([0-9]+)(h|min|s|ms|us)")
    for match in token.finditer(value):
        _require(
            match.start() == cursor,
            f"{label}.{name}: malformed duration",
        )
        total += int(match.group(1), 10) * units[match.group(2)]
        cursor = match.end()
    _require(
        cursor == len(value) and total > 0,
        f"{label}.{name}: unsupported duration",
    )
    return total


def _parse_kv_ints(raw: str, label: str) -> dict[str, int]:
    _require(raw.endswith("\n"), f"{label}: missing final newline")
    result: dict[str, int] = {}
    for line in raw.splitlines():
        parts = line.split()
        _require(len(parts) == 2, f"{label}: malformed line {line!r}")
        key, value = parts
        _require(key not in result, f"{label}: duplicate key {key!r}")
        _require(value.isdecimal(), f"{label}: non-integer value")
        result[key] = int(value, 10)
    _require(bool(result), f"{label}: empty mapping")
    return result


def _parse_pid_lines(raw: str, label: str) -> list[int]:
    _require(raw.endswith("\n"), f"{label}: missing final newline")
    values: list[int] = []
    for line in raw.splitlines():
        _require(line.isdecimal(), f"{label}: malformed PID {line!r}")
        pid = int(line, 10)
        _require(pid > 0, f"{label}: non-positive PID")
        values.append(pid)
    _require(
        len(values) == len(set(values)),
        f"{label}: duplicate PID",
    )
    return values


def _validate_common_artifacts(
    payloads: Mapping[str, Mapping[str, Any]],
    identities: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    authority = payloads["authority"]
    selection = payloads["selection"]
    launch = payloads["launch"]
    payload_spec = payloads["payload_spec"]
    start_token = payloads["start_token"]
    supervisor_start = payloads["supervisor_start"]
    payload_terminal = payloads["payload_terminal"]
    completion_seal = payloads["completion_seal"]

    _schema(payload_spec, PAYLOAD_SPEC_SCHEMA, "payload spec")
    _schema(start_token, START_TOKEN_SCHEMA, "start token")
    _schema(supervisor_start, SUPERVISOR_START_SCHEMA, "supervisor start")
    _require(
        selection.get("status") == "SELECTED_CONSUMED",
        "selection: status is not SELECTED_CONSUMED",
    )
    _require(
        launch.get("status") == "LAUNCHED",
        "launch: status is not LAUNCHED",
    )
    _require(
        start_token.get("status") == "PAYLOAD_START_AUTHORIZED",
        "start token: status is not PAYLOAD_START_AUTHORIZED",
    )
    _require(
        payload_terminal.get("payload_reaped") is True and payload_terminal.get("supervisor_role") == "keeper",
        "payload terminal: not a reaped keeper state",
    )

    nonce = _run_nonce(authority, "authority")
    attempt = selection.get("attempt")
    _require(
        isinstance(attempt, str) and bool(attempt),
        "selection: invalid attempt",
    )
    unit = _unit(selection, "selection")
    purpose = _purpose(selection, "selection")
    for label, record in (
        ("payload spec", payload_spec),
        ("supervisor start", supervisor_start),
        ("launch", launch),
        ("start token", start_token),
        ("payload terminal", payload_terminal),
    ):
        _require(_run_nonce(record, label) == nonce, f"{label}: run_nonce mismatch")
        _require(record.get("attempt") == attempt, f"{label}: attempt mismatch")
        _require(_unit(record, label) == unit, f"{label}: unit mismatch")
    for label, record in (
        ("payload spec", payload_spec),
        ("supervisor start", supervisor_start),
        ("launch", launch),
        ("start token", start_token),
        ("payload terminal", payload_terminal),
    ):
        _require(_purpose(record, label) == purpose, f"{label}: purpose mismatch")

    for label, record in (
        ("payload spec", payload_spec),
        ("supervisor start", supervisor_start),
    ):
        _identity_matches(
            record.get("authority"),
            identities["authority"],
            f"{label} authority",
        )
    _identity_matches(
        selection.get("payload_spec"),
        identities["payload_spec"],
        "selection payload spec",
    )
    _identity_matches(
        supervisor_start.get("payload_spec"),
        identities["payload_spec"],
        "supervisor-start payload spec",
    )
    for reference in ("payload_spec", "supervisor_start"):
        _identity_matches(
            launch.get(reference),
            identities[reference],
            f"launch {reference}",
        )
    for reference in (
        "authority",
        "selection",
        "launch",
        "payload_spec",
        "supervisor_start",
    ):
        _identity_matches(
            start_token.get(reference),
            identities[reference],
            f"start token {reference}",
        )
    for reference in (
        "authority",
        "selection",
        "launch",
        "payload_spec",
        "start_token",
    ):
        _identity_matches(
            payload_terminal.get(reference),
            identities[reference],
            f"payload terminal {reference}",
        )
    _identity_matches(
        payload_terminal.get("completion_seal"),
        identities["completion_seal"],
        "payload terminal completion seal",
    )

    completion_path = payload_spec.get("completion_seal")
    _require(
        isinstance(completion_path, str)
        and os.path.isabs(completion_path)
        and completion_path == identities["completion_seal"]["path"]
        and start_token.get("completion_seal") == completion_path,
        "completion seal path is not fixed consistently",
    )

    executed_argv = payload_spec.get("argv")
    logical_argv = payload_spec.get("logical_worker_argv")
    _require(
        isinstance(executed_argv, list)
        and len(executed_argv) >= 6
        and all(isinstance(value, str) and bool(value) for value in executed_argv),
        "payload spec: executed worker argv is malformed",
    )
    _require(
        isinstance(logical_argv, list)
        and bool(logical_argv)
        and all(isinstance(value, str) and bool(value) for value in logical_argv),
        "payload spec: logical worker argv is malformed",
    )
    _require(
        selection.get("worker_argv") == logical_argv,
        "selection: worker argv differs from immutable payload spec",
    )
    binaries = _mapping(authority.get("binaries"), "authority binaries")
    fixed_python = _mapping(
        _mapping(binaries.get("fixed_python"), "authority fixed Python").get("target"),
        "authority fixed Python target",
    )
    _require(
        executed_argv[0] == fixed_python.get("path") and executed_argv[1:4] == ["-I", "-c", PINNED_SOURCE_LOADER],
        "payload spec: pinned source loader argv mismatch",
    )
    worker_identity = identities["worker_source"]
    _require(
        executed_argv[4] == worker_identity["path"]
        and executed_argv[5] == worker_identity["sha256"]
        and logical_argv[0] == worker_identity["path"]
        and executed_argv[6:] == logical_argv[1:],
        "payload spec: worker source or logical/executed argv mismatch",
    )
    tools = _mapping(authority.get("tools"), "authority tools")
    expected_worker = tools.get("formal_payload") if purpose == "formal" else tools.get("orchestrator")
    _identity_matches(
        expected_worker,
        worker_identity,
        "payload worker source authority",
    )

    authority_contract = _normalize_contract(
        authority.get("resource_contract"),
        "authority resource contract",
    )
    for label, record in (
        ("payload spec", payload_spec),
        ("supervisor start", supervisor_start),
        ("start token", start_token),
        ("payload terminal", payload_terminal),
    ):
        _require(
            _same_epoch(record.get("manager_epoch"), authority.get("manager_epoch")),
            f"{label}: manager/boot epoch mismatch",
        )
        _require(
            _normalize_contract(
                record.get("resource_contract"),
                f"{label} resource contract",
            )
            == authority_contract,
            f"{label}: resource contract mismatch",
        )
        _require(
            _normalize_timing_contract(
                record.get("timing_contract"),
                purpose,
                authority_contract,
                f"{label} timing contract",
            )
            == _expected_timing_contract(purpose),
            f"{label}: timing contract mismatch",
        )
    timing_contract = _normalize_timing_contract(
        launch.get("timing_contract"),
        purpose,
        authority_contract,
        "launch timing contract",
    )
    systemd_argv = launch.get("systemd_argv")
    _require(
        isinstance(systemd_argv, list) and all(isinstance(value, str) and bool(value) for value in systemd_argv),
        "launch: systemd argv is malformed",
    )
    systemd_run = _mapping(
        _mapping(authority.get("binaries"), "authority binaries").get("systemd_run"),
        "authority systemd-run",
    )
    fixed_python_path = fixed_python.get("path")
    _require(
        systemd_argv[:4]
        == [
            systemd_run.get("path"),
            "--user",
            "--no-block",
            f"--unit={unit}",
        ]
        and isinstance(fixed_python_path, str)
        and systemd_argv.count(fixed_python_path) == 1,
        "launch: systemd-run/client argv prefix mismatch",
    )
    python_index = systemd_argv.index(fixed_python_path)
    expected_properties = {
        "--property=Type=exec",
        "--property=RemainAfterExit=yes",
        f"--property=MemoryHigh={MEMORY_HIGH}",
        f"--property=MemoryMax={MEMORY_MAX}",
        f"--property=MemorySwapMax={MEMORY_SWAP_MAX}",
        "--property=OOMPolicy=continue",
        "--property=KillMode=control-group",
        "--property=SendSIGKILL=yes",
        f"--property=RuntimeMaxSec={timing_contract['runtime_max_seconds']}",
    }
    _require(
        set(systemd_argv[4:python_index]) == expected_properties
        and len(systemd_argv[4:python_index]) == len(expected_properties),
        "launch: systemd-run resource property argv mismatch",
    )
    orchestrator_identity = identities["authority_tool_orchestrator"]
    supervisor_argv = systemd_argv[python_index:]
    _require(
        supervisor_argv[:6]
        == [
            fixed_python_path,
            "-I",
            "-c",
            PINNED_SOURCE_LOADER,
            orchestrator_identity["path"],
            orchestrator_identity["sha256"],
        ],
        "launch: supervisor pinned source-loader argv mismatch",
    )
    supervisor_arguments = supervisor_argv[6:]
    _require(
        bool(supervisor_arguments) and supervisor_arguments[0] == "--supervisor",
        "launch: supervisor arguments are malformed",
    )
    # ``--supervisor`` is a flag; all following arguments are key/value pairs.
    supervisor_arguments = supervisor_arguments[1:]
    _require(
        len(supervisor_arguments) % 2 == 0,
        "launch: supervisor key/value arguments are malformed",
    )
    supervisor_options = {
        supervisor_arguments[index]: supervisor_arguments[index + 1] for index in range(0, len(supervisor_arguments), 2)
    }
    _require(
        len(supervisor_options) * 2 == len(supervisor_arguments),
        "launch: duplicate supervisor option",
    )
    expected_option_values = {
        "--payload-spec": identities["payload_spec"]["path"],
        "--payload-spec-sha256": identities["payload_spec"]["sha256"],
        "--unit": unit,
        "--attempt": attempt,
        "--run-nonce": nonce,
        "--start-token": identities["start_token"]["path"],
        "--keeper-timeout": str(timing_contract["keeper_timeout_seconds"]),
    }
    _require(
        all(supervisor_options.get(key) == value for key, value in expected_option_values.items())
        and isinstance(supervisor_options.get("--state-dir"), str)
        and os.path.isabs(supervisor_options["--state-dir"])
        and isinstance(supervisor_options.get("--release-token"), str)
        and os.path.isabs(supervisor_options["--release-token"])
        and set(supervisor_options) == {*expected_option_values, "--state-dir", "--release-token"},
        "launch: supervisor lifecycle argv mismatch",
    )

    if purpose == "formal":
        _require(attempt == ATTEMPT, "formal selection is not attempt a002")
        admission_identity = identities.get("formal_admission")
        _require(
            admission_identity is not None,
            "formal selection lacks a same-FD formal admission replay",
        )
        _identity_matches(
            selection.get("formal_admission"),
            admission_identity,
            "selection formal admission",
        )
        admission = payloads["formal_admission"]
        _require(
            admission.get("schema_version") == "b1_sidewise_smm3_formal_admission_v1"
            and admission.get("status") == "FORMAL_ADMISSION_PASS"
            and admission.get("run_nonce") == nonce
            and admission.get("formal_attempt") == ATTEMPT
            and admission.get("formal_attempt_selected") is False
            and admission.get("upper_bound_update_authorized") is False,
            "formal admission semantics failed",
        )
        _require(
            _same_epoch(
                admission.get("manager_epoch"),
                authority.get("manager_epoch"),
            )
            and _normalize_contract(
                admission.get("resource_contract"),
                "formal admission resource contract",
            )
            == _normalize_contract(
                authority.get("resource_contract"),
                "authority resource contract",
            ),
            "formal admission authority epoch/resource mismatch",
        )
        _identity_matches(
            admission.get("authority"),
            identities["authority"],
            "formal admission authority",
        )
        for field in (
            "synthetic_success",
            "synthetic_postseal_failure",
        ):
            _identity_record(
                admission.get(field),
                f"formal admission {field}",
            )
        replay = _mapping(
            admission.get("independent_detached_replays"),
            "formal admission detached replays",
        )
        for field in ("success", "postseal_failure"):
            _identity_record(
                replay.get(field),
                f"formal admission detached replay {field}",
            )
        disk_gate = _mapping(
            admission.get("disk_gate"),
            "formal admission disk gate",
        )
        _require(
            disk_gate.get("pass") is True,
            "formal admission disk gate did not pass",
        )
        process_gate = _mapping(
            admission.get("process_gate"),
            "formal admission process gate",
        )
        _require(
            process_gate.get("status") == "PASS"
            and process_gate.get("single_worker_contract") is True
            and process_gate.get("matches") == [],
            "formal admission process gate did not pass",
        )
    else:
        _require(
            selection.get("formal_admission") is None and "formal_admission" not in identities,
            "synthetic selection unexpectedly carries formal admission",
        )

    supervisor_pid = _positive_pid(
        supervisor_start.get("supervisor_pid"),
        "supervisor-start supervisor",
    )
    payload_pid = _positive_pid(
        supervisor_start.get("payload_pid"),
        "supervisor-start payload",
    )
    _require(
        supervisor_pid != payload_pid
        and launch.get("supervisor_pid") == supervisor_pid
        and launch.get("payload_pid") == payload_pid,
        "supervisor-start and launch PID pair mismatch",
    )
    invocation_id = _invocation_id(supervisor_start, "supervisor start")
    _require(
        _invocation_id(launch, "launch") == invocation_id
        and _invocation_id(start_token, "start token") == invocation_id
        and _invocation_id(payload_terminal, "payload terminal") == invocation_id,
        "common artifacts: InvocationID mismatch",
    )

    started = _positive_monotonic(
        supervisor_start.get("started_monotonic_ns"),
        "supervisor start",
    )
    launch_requested = _positive_monotonic(
        launch.get("launch_requested_monotonic_ns"),
        "launch requested",
    )
    launch_observed = _positive_monotonic(
        launch.get("launch_observed_monotonic_ns"),
        "launch observed",
    )
    authorized = _positive_monotonic(
        start_token.get("authorized_monotonic_ns"),
        "start token authorized",
    )
    reaped = _positive_monotonic(
        payload_terminal.get("reaped_monotonic_ns"),
        "payload terminal reaped",
    )
    _require(
        launch_requested <= started <= launch_observed <= authorized <= reaped,
        "common artifacts: lifecycle monotonic order is impossible",
    )

    if purpose == "formal":
        _schema(completion_seal, INTERNAL_FORMAL_SCHEMA, "formal completion seal")
        _require(
            completion_seal.get("status") == "VERIFIED"
            and completion_seal.get("attempt") == ATTEMPT
            and completion_seal.get("run_nonce") == nonce
            and completion_seal.get("expected_systemd_unit") == unit
            and completion_seal.get("proof_status") == "VERIFIED UNSATISFIABLE"
            and completion_seal.get("upper_bound_update_authorized") is False
            and completion_seal.get("awaiting_terminal_envelope") is True,
            "formal completion seal semantics failed",
        )
        sealed = _positive_monotonic(
            completion_seal.get("completed_monotonic_ns"),
            "formal completion seal",
        )
    else:
        _schema(completion_seal, SYNTHETIC_SEAL_SCHEMA, "synthetic completion seal")
        expected_exit = 0 if purpose == "synthetic_success" else 7
        _require(
            completion_seal.get("run_nonce") == nonce
            and completion_seal.get("attempt") == attempt
            and completion_seal.get("purpose") == purpose
            and completion_seal.get("unit") == unit
            and completion_seal.get("exit_after_seal") == expected_exit,
            "synthetic completion seal semantics failed",
        )
        sealed = _positive_monotonic(
            completion_seal.get("sealed_monotonic_ns"),
            "synthetic completion seal",
        )
    _require(
        authorized <= sealed <= reaped,
        "completion seal monotonic order is impossible",
    )
    return {
        "purpose": purpose,
        "payload_spec": dict(identities["payload_spec"]),
        "start_token": dict(identities["start_token"]),
        "supervisor_start": dict(identities["supervisor_start"]),
        "completion_seal": dict(identities["completion_seal"]),
        "worker_source": dict(worker_identity),
        "started_monotonic_ns": started,
        "launch_observed_monotonic_ns": launch_observed,
        "authorized_monotonic_ns": authorized,
        "sealed_monotonic_ns": sealed,
        "reaped_monotonic_ns": reaped,
    }


def validate_launch_and_preterminal(
    authority: Mapping[str, Any],
    selection: Mapping[str, Any],
    launch: Mapping[str, Any],
    payload_terminal: Mapping[str, Any],
    preterminal: Mapping[str, Any],
    current_epoch: Mapping[str, Any],
) -> dict[str, Any]:
    """Pure validation of the launch-to-keeper resource envelope."""

    _schema(authority, AUTHORITY_SCHEMA, "authority")
    _schema(
        selection,
        (SELECTION_SCHEMA, SYNTHETIC_SELECTION_SCHEMA),
        "selection",
    )
    _schema(launch, LAUNCH_SCHEMA, "launch")
    _schema(payload_terminal, PAYLOAD_TERMINAL_SCHEMA, "payload terminal")
    _schema(preterminal, PRETERMINAL_SCHEMA, "pre-terminal")
    _require(
        selection.get("status") == "SELECTED_CONSUMED" and selection.get("upper_bound_update_authorized") is False,
        "selection: not a consumed non-authorizing selection",
    )
    purpose = _purpose(selection, "selection")
    if purpose == "formal":
        _require(
            selection.get("attempt") == ATTEMPT and isinstance(selection.get("formal_admission"), Mapping),
            "selection: formal a002 admission is missing",
        )
    else:
        _require(
            selection.get("formal_admission") is None,
            "selection: synthetic attempt carries formal admission",
        )

    nonce = _run_nonce(authority, "authority")
    for label, record in (
        ("selection", selection),
        ("launch", launch),
        ("payload terminal", payload_terminal),
        ("pre-terminal", preterminal),
    ):
        _require(
            _run_nonce(record, label) == nonce,
            f"{label}: run_nonce mismatch",
        )

    unit = _unit(selection, "selection")
    if "unit" in authority:
        _require(
            _unit(authority, "authority") == unit,
            "authority: unit mismatch",
        )
    for label, record in (
        ("launch", launch),
        ("payload terminal", payload_terminal),
        ("pre-terminal", preterminal),
    ):
        _require(_unit(record, label) == unit, f"{label}: unit mismatch")

    attempt = selection.get("attempt")
    _require(
        isinstance(attempt, str) and bool(attempt),
        "selection: invalid attempt",
    )
    for label, record in (
        ("launch", launch),
        ("payload terminal", payload_terminal),
        ("pre-terminal", preterminal),
    ):
        _require(
            record.get("attempt") == attempt,
            f"{label}: attempt mismatch",
        )
        _require(
            _purpose(record, label) == purpose,
            f"{label}: purpose mismatch",
        )

    invocation_id = _invocation_id(launch, "launch")
    for label, record in (
        ("payload terminal", payload_terminal),
        ("pre-terminal", preterminal),
    ):
        _require(
            _invocation_id(record, label) == invocation_id,
            f"{label}: InvocationID mismatch",
        )

    authority_epoch = authority.get("manager_epoch")
    _epoch_tuple(authority_epoch, "authority manager epoch")
    _require(
        _same_epoch(authority_epoch, current_epoch),
        "current manager/boot epoch differs from authority",
    )
    for label, record in (
        ("selection", selection),
        ("launch", launch),
        ("payload terminal", payload_terminal),
        ("pre-terminal", preterminal),
    ):
        _require(
            _same_epoch(record.get("manager_epoch"), authority_epoch),
            f"{label}: manager/boot epoch mismatch",
        )

    normalized_contract = _normalize_contract(
        authority.get("resource_contract"),
        "authority resource contract",
    )
    for label, record in (
        ("selection", selection),
        ("launch", launch),
        ("payload terminal", payload_terminal),
        ("pre-terminal", preterminal),
    ):
        _require(
            _normalize_contract(
                record.get("resource_contract"),
                f"{label} resource contract",
            )
            == normalized_contract,
            f"{label}: resource contract mismatch",
        )
    expected_timing = _expected_timing_contract(purpose)
    for label, record in (
        ("selection", selection),
        ("launch", launch),
        ("payload terminal", payload_terminal),
        ("pre-terminal", preterminal),
    ):
        _require(
            _normalize_timing_contract(
                record.get("timing_contract"),
                purpose,
                normalized_contract,
                f"{label} timing contract",
            )
            == expected_timing,
            f"{label}: timing contract mismatch",
        )

    supervisor_pid = _positive_pid(
        launch.get("supervisor_pid"),
        "launch supervisor",
    )
    payload_pid = _positive_pid(
        launch.get("payload_pid"),
        "launch payload",
    )
    _require(
        supervisor_pid != payload_pid,
        "launch: supervisor and payload PID are equal",
    )
    launch_pid_starttimes = _mapping(
        launch.get("pid_starttimes"),
        "launch PID starttimes",
    )
    _require(
        set(launch_pid_starttimes) == {str(supervisor_pid), str(payload_pid)}
        and all(type(value) is int and value > 0 for value in launch_pid_starttimes.values()),
        "launch: PID starttime anchors are incomplete",
    )
    _require(
        launch.get("upper_bound_update_authorized") is False,
        "launch: unexpectedly authorizes an upper-bound update",
    )
    initial_systemd = _raw_mapping(
        launch,
        "initial_systemd_raw",
        (
            "ActiveState",
            "SubState",
            "MainPID",
            "InvocationID",
            "ControlGroup",
            *SYSTEMD_RESOURCE_FIELDS,
        ),
        "launch",
    )
    _require(
        _raw_scalar(initial_systemd, "ActiveState", "launch systemd") == "active"
        and _raw_scalar(initial_systemd, "SubState", "launch systemd") == "running"
        and _raw_nonnegative_int(initial_systemd, "MainPID", "launch systemd") == supervisor_pid
        and _raw_scalar(initial_systemd, "InvocationID", "launch systemd") == invocation_id,
        "launch: initial systemd state does not anchor the supervisor",
    )
    initial_control_group = _raw_scalar(
        initial_systemd,
        "ControlGroup",
        "launch systemd",
    )
    _require(
        initial_control_group.startswith("/") and ".." not in initial_control_group.split("/"),
        "launch: invalid initial ControlGroup",
    )
    expected_runtime_usec = expected_timing["runtime_max_seconds"] * 1_000_000
    expected_systemd = {
        "MemoryHigh": str(MEMORY_HIGH),
        "MemoryMax": str(MEMORY_MAX),
        "MemorySwapMax": str(MEMORY_SWAP_MAX),
        "OOMPolicy": "continue",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
    }
    for name, expected in expected_systemd.items():
        _require(
            _raw_scalar(initial_systemd, name, "launch systemd") == expected,
            f"launch: raw {name} mismatch",
        )
    _require(
        _raw_duration_usec(
            initial_systemd,
            "RuntimeMaxUSec",
            "launch systemd",
        )
        == expected_runtime_usec,
        "launch: raw RuntimeMaxUSec mismatch",
    )
    initial_cgroup_path = launch.get("initial_cgroup_path")
    _require(
        isinstance(initial_cgroup_path, str)
        and initial_cgroup_path == str(Path("/sys/fs/cgroup") / initial_control_group.lstrip("/")),
        "launch: initial cgroup path does not match ControlGroup",
    )
    initial_cgroup = _raw_mapping(
        launch,
        "initial_cgroup_raw",
        CGROUP_RAW_FIELDS,
        "launch",
    )
    for name, expected in (
        ("memory.high", str(MEMORY_HIGH)),
        ("memory.max", str(MEMORY_MAX)),
        ("memory.swap.max", str(MEMORY_SWAP_MAX)),
    ):
        _require(
            _raw_scalar(initial_cgroup, name, "launch cgroup") == expected,
            f"launch: {name} mismatch",
        )
    initial_procs = _parse_pid_lines(
        initial_cgroup["cgroup.procs"],
        "launch cgroup.procs",
    )
    _require(
        sorted(initial_procs) == sorted([supervisor_pid, payload_pid]),
        "launch: initial cgroup does not contain exactly supervisor and payload",
    )
    initial_events = _parse_kv_ints(
        initial_cgroup["cgroup.events"],
        "launch cgroup.events",
    )
    _require(
        initial_events.get("populated") == 1 and initial_events.get("frozen", 0) == 0,
        "launch: initial cgroup is not populated and unfrozen",
    )
    _require(
        payload_terminal.get("supervisor_pid") == supervisor_pid and payload_terminal.get("payload_pid") == payload_pid,
        "payload terminal: launch PID mismatch",
    )
    keeper_value = payload_terminal.get("keeper_pid", supervisor_pid)
    keeper_pid = _positive_pid(keeper_value, "payload terminal keeper")
    _require(
        keeper_pid == supervisor_pid,
        "payload terminal: keeper is not the supervisor",
    )
    _require(
        payload_terminal.get("payload_reaped") is True,
        "payload terminal: payload was not reaped into keeper state",
    )
    waitid = _mapping(
        payload_terminal.get("waitid"),
        "payload terminal waitid",
    )
    waitpid = _mapping(
        payload_terminal.get("waitpid"),
        "payload terminal waitpid",
    )
    wait_status = _mapping(
        payload_terminal.get("wait_status"),
        "payload terminal wait_status",
    )
    _require(
        waitid.get("si_pid") == payload_pid
        and waitid.get("si_signo") == int(signal.SIGCHLD)
        and type(waitid.get("si_uid")) is int
        and waitid.get("si_uid") >= 0
        and waitid.get("si_code") == int(os.CLD_EXITED)
        and type(waitid.get("si_status")) is int
        and waitid.get("si_status") in {0, 7}
        and waitpid.get("kind") == "CLD_EXITED"
        and waitpid.get("exit_code") == waitid.get("si_status")
        and waitpid.get("signal") is None
        and waitpid.get("core_dumped") is False
        and wait_status.get("code") == "CLD_EXITED"
        and wait_status.get("status") == waitid.get("si_status"),
        "payload terminal: waitid, waitpid, and wait_status do not jointly agree",
    )
    payload_exit_status = waitid["si_status"]
    expected_payload_exit = 7 if purpose == "synthetic_postseal_failure" else 0
    _require(
        payload_exit_status == expected_payload_exit,
        "payload terminal: exit status contradicts selected purpose",
    )
    _require(
        payload_terminal.get("seal_written") is True,
        "payload terminal: inner SEAL was not recorded",
    )

    _require(
        preterminal.get("supervisor_pid") == supervisor_pid
        and preterminal.get("payload_pid") == payload_pid
        and preterminal.get("keeper_pid") == keeper_pid
        and preterminal.get("payload_reaped") is True,
        "pre-terminal: process transition mismatch",
    )

    systemd_raw = _raw_mapping(
        preterminal,
        "systemd_raw",
        (
            "ActiveState",
            "SubState",
            "MainPID",
            "InvocationID",
            "ControlGroup",
            *SYSTEMD_RESOURCE_FIELDS,
        ),
        "pre-terminal",
    )
    _require(
        _raw_scalar(systemd_raw, "ActiveState", "pre-terminal systemd") == "active",
        "pre-terminal: unit is not active",
    )
    _require(
        _raw_scalar(systemd_raw, "SubState", "pre-terminal systemd") == "running",
        "pre-terminal: unit is not running",
    )
    _require(
        _raw_nonnegative_int(systemd_raw, "MainPID", "pre-terminal systemd") == keeper_pid,
        "pre-terminal: MainPID is not the keeper",
    )
    _require(
        _raw_scalar(systemd_raw, "InvocationID", "pre-terminal systemd") == invocation_id,
        "pre-terminal: raw InvocationID mismatch",
    )
    expected_systemd = {
        "MemoryHigh": str(MEMORY_HIGH),
        "MemoryMax": str(MEMORY_MAX),
        "MemorySwapMax": str(MEMORY_SWAP_MAX),
        "OOMPolicy": "continue",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
    }
    for name, expected in expected_systemd.items():
        _require(
            _raw_scalar(systemd_raw, name, "pre-terminal systemd") == expected,
            f"pre-terminal: raw {name} mismatch",
        )
    _require(
        _raw_duration_usec(
            systemd_raw,
            "RuntimeMaxUSec",
            "pre-terminal systemd",
        )
        == expected_runtime_usec,
        "pre-terminal: raw RuntimeMaxUSec mismatch",
    )

    control_group = _raw_scalar(
        systemd_raw,
        "ControlGroup",
        "pre-terminal systemd",
    )
    _require(
        control_group == initial_control_group,
        "pre-terminal: ControlGroup changed from launch",
    )
    cgroup_path = preterminal.get("cgroup_path")
    _require(
        isinstance(cgroup_path, str)
        and cgroup_path == str(Path("/sys/fs/cgroup") / control_group.lstrip("/"))
        and cgroup_path == initial_cgroup_path,
        "pre-terminal: cgroup path does not match ControlGroup",
    )

    cgroup_raw = _raw_mapping(
        preterminal,
        "cgroup_raw",
        CGROUP_RAW_FIELDS,
        "pre-terminal",
    )
    _require(
        _raw_scalar(cgroup_raw, "memory.high", "pre-terminal cgroup") == str(MEMORY_HIGH),
        "pre-terminal: memory.high mismatch",
    )
    _require(
        _raw_scalar(cgroup_raw, "memory.max", "pre-terminal cgroup") == str(MEMORY_MAX),
        "pre-terminal: memory.max mismatch",
    )
    _require(
        _raw_scalar(cgroup_raw, "memory.swap.max", "pre-terminal cgroup") == str(MEMORY_SWAP_MAX),
        "pre-terminal: memory.swap.max mismatch",
    )
    memory_current = _raw_nonnegative_int(
        cgroup_raw,
        "memory.current",
        "pre-terminal cgroup",
    )
    memory_peak = _raw_nonnegative_int(
        cgroup_raw,
        "memory.peak",
        "pre-terminal cgroup",
    )
    swap_current = _raw_nonnegative_int(
        cgroup_raw,
        "memory.swap.current",
        "pre-terminal cgroup",
    )
    swap_peak = _raw_nonnegative_int(
        cgroup_raw,
        "memory.swap.peak",
        "pre-terminal cgroup",
    )
    _require(
        memory_current <= memory_peak <= MEMORY_MAX,
        "pre-terminal: memory current/peak is inconsistent",
    )
    _require(
        swap_current <= swap_peak <= MEMORY_SWAP_MAX,
        "pre-terminal: swap current/peak is inconsistent",
    )
    for event_name in ("memory.events", "memory.events.local"):
        events = _parse_kv_ints(
            cgroup_raw[event_name],
            f"pre-terminal {event_name}",
        )
        for key in ZERO_EVENT_FIELDS:
            _require(
                key in events and events[key] == 0,
                f"pre-terminal: {event_name} {key} is missing or nonzero",
            )
    procs = _parse_pid_lines(
        cgroup_raw["cgroup.procs"],
        "pre-terminal cgroup.procs",
    )
    _require(
        procs == [keeper_pid],
        "pre-terminal: cgroup does not contain exactly the keeper",
    )
    cgroup_events = _parse_kv_ints(
        cgroup_raw["cgroup.events"],
        "pre-terminal cgroup.events",
    )
    _require(
        cgroup_events.get("populated") == 1,
        "pre-terminal: cgroup is not populated",
    )
    if "frozen" in cgroup_events:
        _require(
            cgroup_events["frozen"] == 0,
            "pre-terminal: cgroup is unexpectedly frozen",
        )
    _require(
        preterminal.get("release_created") is False,
        "pre-terminal: release already existed before verification",
    )
    reaped_monotonic_ns = _positive_monotonic(
        payload_terminal.get("reaped_monotonic_ns"),
        "payload terminal reaped",
    )
    preterminal_monotonic_ns = _positive_monotonic(
        preterminal.get("captured_monotonic_ns"),
        "pre-terminal captured",
    )
    _require(
        preterminal_monotonic_ns >= reaped_monotonic_ns,
        "pre-terminal: captured before payload reaping",
    )

    return {
        "run_nonce": nonce,
        "attempt": attempt,
        "unit": unit,
        "invocation_id": invocation_id,
        "supervisor_pid": supervisor_pid,
        "payload_pid": payload_pid,
        "keeper_pid": keeper_pid,
        "payload_exit_status": payload_exit_status,
        "cgroup_path": cgroup_path,
        "memory_current": memory_current,
        "memory_peak": memory_peak,
        "memory_swap_current": swap_current,
        "memory_swap_peak": swap_peak,
        "resource_contract": normalized_contract,
        "timing_contract": expected_timing,
        "purpose": purpose,
        "preterminal_monotonic_ns": preterminal_monotonic_ns,
        "pid_starttimes": dict(launch_pid_starttimes),
    }


def validate_terminal_cleanup(
    authority: Mapping[str, Any],
    selection: Mapping[str, Any],
    launch: Mapping[str, Any],
    payload_terminal: Mapping[str, Any],
    preterminal: Mapping[str, Any],
    terminal: Mapping[str, Any],
    cleanup: Mapping[str, Any],
    current_epoch: Mapping[str, Any],
    *,
    expected_terminal: str,
) -> dict[str, Any]:
    """Pure validation of terminal metadata and independent cleanup."""

    resource = validate_launch_and_preterminal(
        authority,
        selection,
        launch,
        payload_terminal,
        preterminal,
        current_epoch,
    )
    _schema(terminal, TERMINAL_SCHEMA, "terminal")
    _schema(cleanup, CLEANUP_SCHEMA, "cleanup")
    _require(
        terminal.get("status") == "TERMINAL_CAPTURED" and terminal.get("upper_bound_update_authorized") is False,
        "terminal: invalid capture status",
    )
    _require(
        cleanup.get("status") == "CLEANUP_CAPTURED" and cleanup.get("upper_bound_update_authorized") is False,
        "cleanup: invalid capture status",
    )
    for label, record in (("terminal", terminal), ("cleanup", cleanup)):
        _require(
            _run_nonce(record, label) == resource["run_nonce"],
            f"{label}: run_nonce mismatch",
        )
        _require(
            _unit(record, label) == resource["unit"],
            f"{label}: unit mismatch",
        )
        _require(
            _invocation_id(record, label) == resource["invocation_id"],
            f"{label}: InvocationID mismatch",
        )
        _require(
            record.get("attempt") == resource["attempt"],
            f"{label}: attempt mismatch",
        )
        _require(
            _same_epoch(record.get("manager_epoch"), current_epoch),
            f"{label}: manager/boot epoch mismatch",
        )
        _require(
            _purpose(record, label) == resource["purpose"],
            f"{label}: purpose mismatch",
        )
        _require(
            _normalize_contract(
                record.get("resource_contract"),
                f"{label} resource contract",
            )
            == resource["resource_contract"],
            f"{label}: resource contract mismatch",
        )
        _require(
            _normalize_timing_contract(
                record.get("timing_contract"),
                resource["purpose"],
                resource["resource_contract"],
                f"{label} timing contract",
            )
            == resource["timing_contract"],
            f"{label}: timing contract mismatch",
        )

    terminal_raw = _raw_mapping(
        terminal,
        "systemd_raw",
        (
            "ActiveState",
            "SubState",
            "Result",
            "ExecMainCode",
            "ExecMainStatus",
            "MainPID",
            "InvocationID",
            "ControlGroup",
            *SYSTEMD_RESOURCE_FIELDS,
        ),
        "terminal",
    )
    _require(
        _raw_scalar(terminal_raw, "InvocationID", "terminal systemd") == resource["invocation_id"],
        "terminal: raw InvocationID mismatch",
    )
    _require(
        _raw_scalar(terminal_raw, "ExecMainCode", "terminal systemd") == "1",
        "terminal: ExecMainCode is not CLD_EXITED/code 1",
    )
    _require(
        _raw_nonnegative_int(terminal_raw, "MainPID", "terminal systemd") == 0,
        "terminal: MainPID is not zero",
    )
    expected_runtime_usec = resource["timing_contract"]["runtime_max_seconds"] * 1_000_000
    expected_resources = {
        "MemoryHigh": str(MEMORY_HIGH),
        "MemoryMax": str(MEMORY_MAX),
        "MemorySwapMax": str(MEMORY_SWAP_MAX),
        "OOMPolicy": "continue",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
    }
    for name, expected in expected_resources.items():
        _require(
            _raw_scalar(terminal_raw, name, "terminal systemd") == expected,
            f"terminal: raw {name} mismatch",
        )
    _require(
        _raw_duration_usec(
            terminal_raw,
            "RuntimeMaxUSec",
            "terminal systemd",
        )
        == expected_runtime_usec,
        "terminal: raw RuntimeMaxUSec mismatch",
    )

    if expected_terminal == "success":
        expected_values = {
            "ActiveState": "active",
            "SubState": "exited",
            "Result": "success",
            "ExecMainStatus": "0",
        }
        expected_payload_status = 0
    elif expected_terminal == "postseal-failure":
        expected_values = {
            "ActiveState": "failed",
            "SubState": "failed",
            "Result": "exit-code",
            "ExecMainStatus": "7",
        }
        expected_payload_status = 7
    else:
        raise VerificationError(f"unsupported expected terminal class {expected_terminal!r}")
    purpose_terminal = "postseal-failure" if resource["purpose"] == "synthetic_postseal_failure" else "success"
    _require(
        expected_terminal == purpose_terminal,
        "terminal: requested terminal class contradicts selected purpose",
    )
    for name, expected in expected_values.items():
        _require(
            _raw_scalar(terminal_raw, name, "terminal systemd") == expected,
            f"terminal: {name} mismatch for {expected_terminal}",
        )
    _require(
        resource["payload_exit_status"] == expected_payload_status,
        "terminal: payload wait status does not match terminal class",
    )

    terminal_control_group = _raw_scalar(
        terminal_raw,
        "ControlGroup",
        "terminal systemd",
    )
    if terminal_control_group:
        _require(
            str(Path("/sys/fs/cgroup") / terminal_control_group.lstrip("/")) == resource["cgroup_path"],
            "terminal: nonempty ControlGroup changed",
        )

    terminal_monotonic_ns = _positive_monotonic(
        terminal.get("captured_monotonic_ns"),
        "terminal captured",
    )
    cleanup_monotonic_ns = _positive_monotonic(
        cleanup.get("captured_monotonic_ns"),
        "cleanup captured",
    )
    _require(
        resource["preterminal_monotonic_ns"] < terminal_monotonic_ns < cleanup_monotonic_ns,
        "terminal/cleanup: monotonic capture order is impossible",
    )

    systemctl_path = _mapping(
        _mapping(authority.get("binaries"), "authority binaries").get("systemctl"),
        "authority systemctl",
    ).get("path")
    _require(
        isinstance(systemctl_path, str) and os.path.isabs(systemctl_path),
        "authority systemctl path is invalid",
    )
    for field, expected_action in (("stop", "stop"),):
        command = _mapping(cleanup.get(field), f"cleanup {field}")
        argv = command.get("argv")
        _require(
            isinstance(argv, list)
            and argv == [systemctl_path, "--user", expected_action, resource["unit"]]
            and command.get("exit_code") == 0
            and isinstance(command.get("stdout"), str)
            and isinstance(command.get("stderr"), str),
            f"cleanup: raw {field} command result is invalid",
        )
    reset_failed = _mapping(cleanup.get("reset_failed"), "cleanup reset_failed")
    reset_argv = reset_failed.get("argv")
    reset_exit = reset_failed.get("exit_code")
    reset_stdout = reset_failed.get("stdout")
    reset_stderr = reset_failed.get("stderr")
    reset_not_loaded = (
        reset_exit == 1
        and reset_stdout == ""
        and reset_stderr
        == (f"Failed to reset failed state of unit {resource['unit']}: Unit {resource['unit']} not loaded.\n")
    )
    _require(
        isinstance(reset_argv, list)
        and reset_argv == [systemctl_path, "--user", "reset-failed", resource["unit"]]
        and isinstance(reset_stdout, str)
        and isinstance(reset_stderr, str)
        and (reset_exit == 0 or reset_not_loaded),
        "cleanup: raw reset_failed command result is invalid",
    )
    load_state = _mapping(cleanup.get("load_state"), "cleanup load_state")
    load_argv = load_state.get("argv")
    _require(
        isinstance(load_argv, list)
        and load_argv
        == [
            systemctl_path,
            "--user",
            "show",
            resource["unit"],
            "--property=LoadState",
            "--value",
        ]
        and load_state.get("exit_code") == 0
        and load_state.get("stdout") == "not-found\n"
        and isinstance(load_state.get("stderr"), str),
        "cleanup: raw load_state command does not prove unit absence",
    )

    _require(
        cleanup.get("unit_absent") is True,
        "cleanup: unit remains present",
    )
    checked_pids = cleanup.get("checked_pids")
    remaining_pids = cleanup.get("remaining_pids")
    expected_pids = sorted(
        {
            resource["supervisor_pid"],
            resource["payload_pid"],
            resource["keeper_pid"],
        }
    )
    _require(
        isinstance(checked_pids, list)
        and all(type(value) is int for value in checked_pids)
        and sorted(checked_pids) == expected_pids,
        "cleanup: PID check set is incomplete",
    )
    pid_starttimes = _mapping(
        cleanup.get("pid_starttimes"),
        "cleanup PID starttimes",
    )
    _require(
        set(pid_starttimes) == {str(pid) for pid in expected_pids}
        and dict(pid_starttimes) == resource["pid_starttimes"],
        "cleanup: recorded PID starttimes are incomplete",
    )
    _require(
        remaining_pids == [],
        "cleanup: one or more recorded PIDs remain",
    )
    _require(
        cleanup.get("cgroup_path") == resource["cgroup_path"] and cleanup.get("cgroup_absent") is True,
        "cleanup: original cgroup remains present or path changed",
    )
    _require(
        cleanup.get("terminal_control_group_used_as_cleanup_evidence") is False,
        "cleanup: terminal ControlGroup was used as cleanup evidence",
    )
    return {
        **resource,
        "terminal_class": expected_terminal,
        "terminal_control_group": terminal_control_group,
        "unit_absent": True,
        "remaining_pids": [],
        "cgroup_absent": True,
        "terminal_monotonic_ns": terminal_monotonic_ns,
        "cleanup_monotonic_ns": cleanup_monotonic_ns,
        "pid_starttimes": dict(pid_starttimes),
    }


def _write_exclusive(path: Path, raw: bytes) -> dict[str, Any]:
    absolute = os.path.abspath(os.fspath(path))
    parent, name = os.path.split(absolute)
    if not name or name in {".", ".."}:
        raise VerificationError("output has an invalid final component")
    parent_flags = (
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        parent_fd = os.open(parent, parent_flags)
    except OSError as exc:
        raise VerificationError(f"cannot open output parent directory: {exc}") from exc
    try:
        output_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(
                name,
                output_flags,
                0o644,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise VerificationError(f"cannot create O_EXCL output: {exc}") from exc
        try:
            offset = 0
            while offset < len(raw):
                written = os.write(descriptor, raw[offset:])
                if written <= 0:
                    raise VerificationError("short output write")
                offset += written
            os.fsync(descriptor)
            metadata = os.fstat(descriptor)
            _require(
                metadata.st_size == len(raw),
                "output size mismatch after write",
            )
            identity = {
                "path": absolute,
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "mode_octal": f"{stat.S_IMODE(metadata.st_mode):04o}",
                "device": metadata.st_dev,
                "inode": metadata.st_ino,
                "link_count": metadata.st_nlink,
            }
        finally:
            os.close(descriptor)
    finally:
        os.close(parent_fd)
    return identity


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
        )
        + "\n"
    ).encode("ascii")


def _load_common(
    arguments: argparse.Namespace,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
]:
    payloads: dict[str, dict[str, Any]] = {}
    identities: dict[str, dict[str, Any]] = {}
    for name, path, label in (
        ("authority", arguments.authority, "SMM3 authority"),
        ("selection", arguments.selection, "SMM3 selection"),
        ("payload_spec", arguments.payload_spec, "SMM3 payload spec"),
        (
            "supervisor_start",
            arguments.supervisor_start,
            "SMM3 supervisor start",
        ),
        ("launch", arguments.launch, "SMM3 launch"),
        ("start_token", arguments.start_token, "SMM3 start token"),
        (
            "payload_terminal",
            arguments.payload_terminal,
            "SMM3 payload terminal",
        ),
        ("preterminal", arguments.preterminal, "SMM3 pre-terminal"),
        (
            "completion_seal",
            arguments.completion_seal,
            "SMM3 completion seal",
        ),
    ):
        payload, identity = _load_json(path, label)
        payloads[name] = payload
        identities[name] = identity

    purpose = _purpose(payloads["selection"], "selection")
    if purpose == "formal":
        _require(
            arguments.formal_admission is not None,
            "formal common replay lacks --formal-admission",
        )
        formal_admission, formal_admission_identity = _load_json(
            arguments.formal_admission,
            "SMM3 formal admission",
        )
        payloads["formal_admission"] = formal_admission
        identities["formal_admission"] = formal_admission_identity
    else:
        _require(
            arguments.formal_admission is None,
            "synthetic common replay received --formal-admission",
        )

    authority_tools = _mapping(
        payloads["authority"].get("tools"),
        "authority tools",
    )
    for name, expected_value in authority_tools.items():
        expected = _identity_record(
            expected_value,
            f"authority tool {name}",
        )
        _, replay_identity = _snapshot_regular(
            Path(expected["path"]),
            f"authority tool replay {name}",
            collect=False,
            max_bytes=MANAGER_TOOL_LIMIT,
        )
        _identity_matches(
            expected,
            replay_identity,
            f"authority tool replay {name}",
        )
        identities[f"authority_tool_{name}"] = replay_identity

    executed_argv = payloads["payload_spec"].get("argv")
    _require(
        isinstance(executed_argv, list)
        and len(executed_argv) >= 6
        and isinstance(executed_argv[4], str)
        and os.path.isabs(executed_argv[4]),
        "payload spec: cannot resolve worker source",
    )
    _, worker_identity = _snapshot_regular(
        Path(executed_argv[4]),
        "SMM3 payload worker source",
        collect=False,
        max_bytes=MANAGER_TOOL_LIMIT,
    )
    identities["worker_source"] = worker_identity

    _identity_matches(
        payloads["selection"].get("authority"),
        identities["authority"],
        "selection authority",
    )
    for reference in ("authority", "selection"):
        _identity_matches(
            payloads["launch"].get(reference),
            identities[reference],
            f"launch {reference}",
        )
    for reference in (
        "authority",
        "selection",
        "launch",
        "payload_terminal",
        "payload_spec",
        "start_token",
        "supervisor_start",
        "completion_seal",
    ):
        _identity_matches(
            payloads["preterminal"].get(reference),
            identities[reference],
            f"pre-terminal {reference}",
        )

    common_validation = _validate_common_artifacts(payloads, identities)
    current_epoch, manager_tool_identity = _capture_current_epoch(
        payloads["authority"],
        arguments.manager_epoch_tool,
    )
    payloads["_common_validation"] = common_validation
    return payloads, identities, current_epoch, manager_tool_identity


def _validate_resource_receipt(
    receipt: Mapping[str, Any],
    receipt_identities: Mapping[str, Mapping[str, Any]],
    current_epoch: Mapping[str, Any],
) -> None:
    _schema(receipt, RESOURCE_RECEIPT_SCHEMA, "resource receipt")
    _require(
        receipt.get("status") == "PASS",
        "resource receipt is not PASS",
    )
    recorded = _mapping(receipt.get("inputs"), "resource receipt inputs")
    for name, identity in receipt_identities.items():
        _identity_matches(
            recorded.get(name),
            identity,
            f"resource receipt {name}",
        )
    _require(
        _same_epoch(receipt.get("manager_epoch"), current_epoch),
        "resource receipt manager/boot epoch mismatch",
    )


def _validate_internal_formal(
    internal: Mapping[str, Any],
    internal_identity: Mapping[str, Any],
    authority: Mapping[str, Any],
    identities: Mapping[str, Mapping[str, Any]],
    formula_identity: Mapping[str, Any],
    proof_identity: Mapping[str, Any],
    unit: str,
    terminal: Mapping[str, Any],
    cleanup: Mapping[str, Any],
) -> None:
    _schema(internal, INTERNAL_FORMAL_SCHEMA, "internal formal receipt")
    _require(
        internal.get("status") == "VERIFIED"
        and internal.get("attempt") == ATTEMPT
        and internal.get("purpose") == "formal"
        and internal.get("run_nonce") == _run_nonce(authority, "authority")
        and internal.get("proof_status") == "VERIFIED UNSATISFIABLE"
        and internal.get("upper_bound_update_authorized") is False
        and internal.get("awaiting_terminal_envelope") is True
        and internal.get("production_certified") is False,
        "internal formal receipt semantics failed",
    )
    _require(
        internal.get("expected_systemd_unit") == unit,
        "internal formal receipt unit mismatch",
    )
    _identity_matches(
        terminal.get("internal_receipt"),
        internal_identity,
        "terminal internal receipt",
    )
    _identity_matches(
        cleanup.get("internal_receipt"),
        internal_identity,
        "cleanup internal receipt",
    )
    authority_contract = _normalize_contract(
        authority.get("resource_contract"),
        "authority resource contract",
    )
    _require(
        _normalize_contract(
            internal.get("resource_contract"),
            "internal formal resource contract",
        )
        == authority_contract
        and _normalize_timing_contract(
            internal.get("timing_contract"),
            "formal",
            authority_contract,
            "internal formal timing contract",
        )
        == _expected_timing_contract("formal"),
        "internal formal receipt budget authority mismatch",
    )
    internal_inputs = _mapping(
        internal.get("inputs"),
        "internal formal inputs",
    )
    _identity_matches(
        internal_inputs.get("authority"),
        identities["authority"],
        "internal formal authority",
    )
    _identity_matches(
        internal_inputs.get("selection"),
        identities["selection"],
        "internal formal selection",
    )
    authority_inputs = _mapping(authority.get("inputs"), "authority inputs")
    historical_joins = {
        "historical_pb_authority": "pb_authority",
        "historical_geometry_admission": "geometry_admission",
        "strict_instance": "strict_instance",
        "historical_translation_gate": "translation_gate",
    }
    for internal_name, authority_name in historical_joins.items():
        _identity_matches(
            internal_inputs.get(internal_name),
            _mapping(
                authority_inputs.get(authority_name),
                f"authority input {authority_name}",
            ),
            f"internal formal {internal_name}",
        )
    internal_build = _mapping(
        internal_inputs.get("historical_build_files"),
        "internal formal historical build files",
    )
    authority_build = _mapping(
        authority_inputs.get("build_files"),
        "authority build files",
    )
    _require(
        set(internal_build) == set(authority_build),
        "internal formal historical build set mismatch",
    )
    for name, expected in authority_build.items():
        _identity_matches(
            internal_build.get(name),
            _mapping(expected, f"authority build {name}"),
            f"internal formal historical build {name}",
        )

    snapshots = _mapping(
        internal_inputs.get("execution_snapshots"),
        "internal formal execution snapshots",
    )
    for snapshot_name, authority_name in (
        ("pb_authority.json", "pb_authority"),
        ("geometry_admission.json", "geometry_admission"),
        ("strict_instance.json", "strict_instance"),
        ("translation_gate.previous.json", "translation_gate"),
    ):
        _identity_content_matches(
            authority_inputs.get(authority_name),
            _mapping(snapshots.get(snapshot_name), f"snapshot {snapshot_name}"),
            f"execution snapshot {snapshot_name}",
        )
    snapshot_build = _mapping(
        snapshots.get("build"),
        "internal formal build execution snapshots",
    )
    _require(
        set(snapshot_build) == set(authority_build),
        "internal formal build execution snapshot set mismatch",
    )
    for name, expected in authority_build.items():
        _identity_content_matches(
            expected,
            _mapping(snapshot_build.get(name), f"build snapshot {name}"),
            f"execution build snapshot {name}",
        )

    _identity_matches(
        internal.get("formula"),
        formula_identity,
        "internal formal formula",
    )
    _identity_matches(
        internal.get("proof"),
        proof_identity,
        "internal formal proof",
    )
    _require(
        formula_identity["size_bytes"] == FORMULA_SIZE and formula_identity["sha256"] == FORMULA_SHA256,
        "formal formula identity is not the fixed SMM3 formula",
    )
    _require(
        0 < proof_identity["size_bytes"] <= PROOF_LIMIT,
        "formal proof is empty or exceeds the cap",
    )
    _identity_content_matches(
        authority_inputs.get("formula"),
        formula_identity,
        "formal formula authority input",
    )

    tools = _mapping(internal.get("tools"), "internal formal tools")
    authority_tools = _mapping(authority.get("tools"), "authority tools")
    for name in ("formal_payload", "translation_gate"):
        _identity_matches(
            authority_tools.get(name),
            _mapping(tools.get(name), f"internal formal tool {name}"),
            f"internal formal tool {name}",
        )
    authority_binaries = _mapping(authority.get("binaries"), "authority binaries")
    for name in ("fixed_python", "roundingsat", "veripb"):
        tool = _mapping(tools.get(name), f"internal formal tool {name}")
        authority_binary = _mapping(
            authority_binaries.get(name),
            f"authority binary {name}",
        )
        expected_target = (
            _mapping(
                authority_binary.get("target"),
                f"authority binary {name} target",
            )
            if "target" in authority_binary
            else authority_binary
        )
        _identity_matches(
            tool.get("target"),
            expected_target,
            f"internal formal tool {name} target",
        )
        expected_logical = authority_binary.get("path", expected_target.get("path"))
        _require(
            tool.get("logical_path") == expected_logical and tool.get("execution") == "pinned_fd",
            f"internal formal tool {name} execution provenance mismatch",
        )

    cgroup = _mapping(
        internal.get("cgroup_membership"),
        "internal formal cgroup membership",
    )
    _require(
        cgroup.get("proc_path") == "/proc/self/cgroup"
        and cgroup.get("expected_unit_present") is True
        and isinstance(cgroup.get("unified_path"), str)
        and unit in cgroup["unified_path"]
        and type(cgroup.get("size_bytes")) is int
        and cgroup.get("size_bytes") > 0
        and isinstance(cgroup.get("sha256"), str)
        and SHA256_RE.fullmatch(cgroup["sha256"]) is not None,
        "internal formal cgroup provenance mismatch",
    )

    translation = _mapping(
        internal.get("translation_replay"),
        "internal translation replay",
    )
    solver = _mapping(internal.get("solver"), "internal solver")
    verifier = _mapping(internal.get("verifier"), "internal verifier")
    _require(
        translation.get("executed_from_pinned_fd") is True
        and translation.get("exit_code") == 0
        and translation.get("status") == "PASS",
        "internal translation replay provenance failed",
    )
    _require(
        solver.get("exit_code") == 0
        and solver.get("status_lines") == ["UNSATISFIABLE"]
        and solver.get("executed_from_pinned_fd") is True
        and solver.get("time_limit_seconds") == FORMAL_ROUNDINGSAT_TIME_LIMIT_SECONDS
        and solver.get("monitor_limit_seconds") == FORMAL_ROUNDINGSAT_MONITOR_LIMIT_SECONDS,
        "internal RoundingSat result is not unique UNSAT",
    )
    _require(
        verifier.get("exit_code") == 0
        and verifier.get("status_lines") == ["s VERIFIED UNSATISFIABLE"]
        and verifier.get("executed_from_pinned_fd") is True
        and verifier.get("time_limit_seconds") == FORMAL_VERIPB_TIME_LIMIT_SECONDS,
        "internal VeriPB result is not uniquely verified UNSAT",
    )
    solver_argv = solver.get("logical_argv")
    verifier_argv = verifier.get("logical_argv")
    _require(
        isinstance(solver_argv, list)
        and len(solver_argv) == 4
        and solver_argv[0] == _mapping(tools.get("roundingsat"), "internal RoundingSat tool").get("logical_path")
        and solver_argv[1] == f"--proof-log={proof_identity['path']}"
        and solver_argv[2] == f"--time-limit={FORMAL_ROUNDINGSAT_TIME_LIMIT_SECONDS}"
        and solver_argv[3] == formula_identity["path"],
        "internal RoundingSat argv provenance mismatch",
    )
    _require(
        isinstance(verifier_argv, list)
        and verifier_argv
        == [
            _mapping(tools.get("veripb"), "internal VeriPB tool").get("logical_path"),
            "--opb",
            "--stats",
            formula_identity["path"],
            proof_identity["path"],
        ],
        "internal VeriPB argv provenance mismatch",
    )
    artifact_contract = _mapping(
        internal.get("artifact_contract"),
        "internal artifact contract",
    )
    _require(
        artifact_contract.get("proof_limit_bytes") == PROOF_LIMIT
        and artifact_contract.get("low_water_bytes") == authority["resource_contract"]["artifact_low_water_bytes"]
        and artifact_contract.get("required_free_before_formal_bytes")
        == authority["resource_contract"]["required_free_before_formal_bytes"]
        and type(artifact_contract.get("free_before_solver_bytes")) is int
        and artifact_contract["free_before_solver_bytes"] >= artifact_contract["required_free_before_formal_bytes"]
        and type(artifact_contract.get("free_after_verifier_bytes")) is int
        and artifact_contract["free_after_verifier_bytes"] >= artifact_contract["low_water_bytes"],
        "internal formal artifact resource provenance mismatch",
    )
    _require(
        internal.get("ledger_candidate")
        == {
            "old_upper": [1188, 22],
            "new_upper": [1188, 18],
            "lower": "absent",
        },
        "internal formal ledger candidate mismatch",
    )


def _open_pinned_executable(
    path: Path,
    expected: Any,
    label: str,
) -> tuple[int, dict[str, Any], str]:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise VerificationError(f"{label}: cannot resolve: {exc}") from exc
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(resolved, flags)
    except OSError as exc:
        raise VerificationError(f"{label}: cannot open: {exc}") from exc
    try:
        metadata = os.fstat(descriptor)
        _require(
            stat.S_ISREG(metadata.st_mode),
            f"{label}: target is not regular",
        )
        _require(metadata.st_size > 0, f"{label}: target is empty")
        digest = hashlib.sha256()
        total = 0
        while True:
            block = os.read(descriptor, 1 << 20)
            if not block:
                break
            total += len(block)
            digest.update(block)
        after = os.fstat(descriptor)
        _require(
            _stable(metadata, after) and total == metadata.st_size,
            f"{label}: target drifted during pinned hash",
        )
        identity = {
            "path": str(resolved.absolute()),
            "size_bytes": total,
            "sha256": digest.hexdigest(),
            "mode_octal": f"{stat.S_IMODE(metadata.st_mode):04o}",
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "link_count": metadata.st_nlink,
        }
        _identity_matches(expected, identity, label)
        _require(
            stat.S_IMODE(metadata.st_mode) & 0o111 != 0,
            f"{label}: executable bit missing",
        )
        os.lseek(descriptor, 0, os.SEEK_SET)
        return descriptor, identity, str(path.absolute())
    except Exception:
        os.close(descriptor)
        raise


def _open_pinned_input(
    path: Path,
    expected: Mapping[str, Any],
    label: str,
) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path.absolute(), flags)
    except OSError as exc:
        raise VerificationError(f"{label}: cannot open: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        _require(
            stat.S_ISREG(before.st_mode),
            f"{label}: not a regular file",
        )
        digest = hashlib.sha256()
        total = 0
        while True:
            block = os.read(descriptor, 1 << 20)
            if not block:
                break
            total += len(block)
            digest.update(block)
        after = os.fstat(descriptor)
        _require(
            _stable(before, after) and total == before.st_size,
            f"{label}: changed during pinned hash",
        )
        identity = {
            "path": str(path.absolute()),
            "size_bytes": total,
            "sha256": digest.hexdigest(),
            "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
            "device": before.st_dev,
            "inode": before.st_ino,
            "link_count": before.st_nlink,
        }
        _identity_matches(expected, identity, label)
        os.lseek(descriptor, 0, os.SEEK_SET)
        return descriptor, before
    except Exception:
        os.close(descriptor)
        raise


def _bounded_temp_bytes(
    handle: Any,
    label: str,
) -> bytes:
    handle.flush()
    size = os.fstat(handle.fileno()).st_size
    _require(size <= TEXT_LIMIT, f"{label}: output exceeded cap")
    handle.seek(0)
    raw = handle.read(TEXT_LIMIT + 1)
    _require(len(raw) == size, f"{label}: short output read")
    return raw


def _proc_starttime(pid: int) -> int | None:
    path = Path(f"/proc/{pid}/stat")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if exc.errno == 2:
            return None
        raise VerificationError(f"live PID {pid} stat cannot be opened: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        _require(
            stat.S_ISREG(before.st_mode),
            f"live PID {pid} stat is not regular",
        )
        raw = os.read(descriptor, 64 * 1024 + 1)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    _require(
        len(raw) <= 64 * 1024 and before.st_dev == after.st_dev and before.st_ino == after.st_ino,
        f"live PID {pid} stat was unstable or oversized",
    )
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise VerificationError(f"live PID {pid} stat is not ASCII") from exc
    closing = text.rfind(")")
    _require(closing > 0, f"live PID {pid} stat has no comm terminator")
    fields = text[closing + 1 :].split()
    _require(
        len(fields) >= 20 and fields[19].isdecimal(),
        f"live PID {pid} stat lacks starttime",
    )
    return int(fields[19], 10)


def _cgroup_path_absent(path_value: str) -> bool:
    root = Path("/sys/fs/cgroup")
    path = Path(path_value)
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise VerificationError("cleanup cgroup escaped /sys/fs/cgroup") from exc
    parts = relative.parts
    _require(
        bool(parts) and all(part not in {"", ".", ".."} for part in parts),
        "cleanup cgroup path is malformed",
    )
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(root, flags)
    try:
        for part in parts:
            try:
                child = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                return True
            os.close(descriptor)
            descriptor = child
        return False
    finally:
        os.close(descriptor)


def _live_absence_replay(
    authority: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    binaries = _mapping(authority.get("binaries"), "authority binaries")
    expected_systemctl = _mapping(
        binaries.get("systemctl"),
        "authority systemctl",
    )
    systemctl_path = expected_systemctl.get("path")
    _require(
        isinstance(systemctl_path, str) and os.path.isabs(systemctl_path),
        "authority systemctl path is invalid",
    )
    descriptor, systemctl_identity, logical_path = _open_pinned_executable(
        Path(systemctl_path),
        expected_systemctl,
        "detached live systemctl",
    )
    logical_argv = [
        logical_path,
        "--user",
        "show",
        validation["unit"],
        "--property=LoadState",
        "--value",
    ]
    executed_argv = [f"/proc/self/fd/{descriptor}", *logical_argv[1:]]
    try:
        completed = subprocess.run(
            executed_argv,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            pass_fds=(descriptor,),
            env={**os.environ, "LC_ALL": "C"},
        )
    finally:
        os.close(descriptor)
    _require(
        len(completed.stdout) <= TEXT_LIMIT and len(completed.stderr) <= TEXT_LIMIT,
        "detached live systemctl output exceeded cap",
    )
    _require(
        completed.returncode == 0 and completed.stdout == b"not-found\n",
        "detached live replay found the transient unit",
    )

    recorded_starttimes = _mapping(
        validation.get("pid_starttimes"),
        "validated cleanup PID starttimes",
    )
    live_pids: dict[str, Any] = {}
    for pid_text, recorded_starttime in recorded_starttimes.items():
        pid = int(pid_text, 10)
        live_starttime = _proc_starttime(pid)
        _require(
            live_starttime is None or live_starttime != recorded_starttime,
            f"detached live replay found recorded process {pid}",
        )
        live_pids[pid_text] = {
            "recorded_starttime": recorded_starttime,
            "live_starttime": live_starttime,
            "recorded_process_absent": True,
        }
    _require(
        _cgroup_path_absent(str(validation["cgroup_path"])),
        "detached live replay found the original cgroup",
    )
    return {
        "unit": {
            "logical_argv": logical_argv,
            "executed_from_pinned_fd": True,
            "tool": systemctl_identity,
            "exit_code": completed.returncode,
            "stdout": completed.stdout.decode("ascii"),
            "stderr": completed.stderr.decode("utf-8", "backslashreplace"),
            "absent": True,
        },
        "pids": live_pids,
        "cgroup_path": validation["cgroup_path"],
        "cgroup_absent": True,
    }


def _run_second_veripb(
    internal: Mapping[str, Any],
    formula_path: Path,
    proof_path: Path,
    veripb_path: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    tools = _mapping(internal.get("tools"), "internal formal tools")
    veripb_record = _mapping(
        tools.get("veripb"),
        "internal formal VeriPB tool",
    )
    descriptor, identity, logical_path = _open_pinned_executable(
        veripb_path,
        veripb_record.get("target"),
        "detached VeriPB",
    )
    internal_formula = _mapping(
        internal.get("formula"),
        "internal formal formula identity",
    )
    internal_proof = _mapping(
        internal.get("proof"),
        "internal formal proof identity",
    )
    try:
        formula_fd, formula_before = _open_pinned_input(
            formula_path,
            internal_formula,
            "detached formula",
        )
    except Exception:
        os.close(descriptor)
        raise
    try:
        proof_fd, proof_before = _open_pinned_input(
            proof_path,
            internal_proof,
            "detached proof",
        )
    except Exception:
        os.close(formula_fd)
        os.close(descriptor)
        raise
    executed_path = f"/proc/self/fd/{descriptor}"
    logical_argv = [
        logical_path,
        "--opb",
        "--stats",
        str(formula_path.absolute()),
        str(proof_path.absolute()),
    ]
    executed_argv = [
        executed_path,
        "--opb",
        "--stats",
        f"/proc/self/fd/{formula_fd}",
        f"/proc/self/fd/{proof_fd}",
    ]
    environment = os.environ.copy()
    environment.update({"LC_ALL": "C"})
    try:
        with tempfile.TemporaryFile() as stdout_file:
            with tempfile.TemporaryFile() as stderr_file:
                try:
                    completed = subprocess.run(
                        executed_argv,
                        check=False,
                        stdin=subprocess.DEVNULL,
                        stdout=stdout_file,
                        stderr=stderr_file,
                        timeout=timeout_seconds,
                        pass_fds=(descriptor, formula_fd, proof_fd),
                        env=environment,
                    )
                except subprocess.TimeoutExpired as exc:
                    raise VerificationError("detached VeriPB exceeded its fixed timeout") from exc
                stdout = _bounded_temp_bytes(
                    stdout_file,
                    "detached VeriPB stdout",
                )
                stderr = _bounded_temp_bytes(
                    stderr_file,
                    "detached VeriPB stderr",
                )
    finally:
        try:
            formula_after = os.fstat(formula_fd)
            proof_after = os.fstat(proof_fd)
        finally:
            os.close(proof_fd)
            os.close(formula_fd)
            os.close(descriptor)
    _require(
        _stable(formula_before, formula_after),
        "detached formula changed while VeriPB used its pinned FD",
    )
    _require(
        _stable(proof_before, proof_after),
        "detached proof changed while VeriPB used its pinned FD",
    )
    stdout_text = stdout.decode("utf-8", "replace")
    stderr_text = stderr.decode("utf-8", "replace")
    status_lines = [line for line in stdout_text.splitlines() if line.startswith("s ")]
    _require(
        completed.returncode == 0 and len(status_lines) == 1 and VERIPB_SUCCESS.fullmatch(status_lines[0]) is not None,
        "detached VeriPB did not uniquely verify UNSAT",
    )
    combined = stdout_text + "\n" + stderr_text
    _require(
        not any(marker in combined for marker in VERIPB_ERROR_MARKERS),
        "detached VeriPB output contains an error marker",
    )
    return {
        "logical_argv": logical_argv,
        "executed_from_pinned_fd": True,
        "inputs_from_pinned_fds": True,
        "tool": identity,
        "exit_code": completed.returncode,
        "status_lines": status_lines,
        "stdout": {
            "size_bytes": len(stdout),
            "sha256": hashlib.sha256(stdout).hexdigest(),
        },
        "stderr": {
            "size_bytes": len(stderr),
            "sha256": hashlib.sha256(stderr).hexdigest(),
        },
        "timeout_seconds": timeout_seconds,
    }


def _resource_command(arguments: argparse.Namespace) -> dict[str, Any]:
    payloads, identities, current_epoch, manager_tool_identity = _load_common(arguments)
    validation = validate_launch_and_preterminal(
        payloads["authority"],
        payloads["selection"],
        payloads["launch"],
        payloads["payload_terminal"],
        payloads["preterminal"],
        current_epoch,
    )
    validation["common_artifacts"] = payloads["_common_validation"]
    return {
        "schema_version": RESOURCE_RECEIPT_SCHEMA,
        "status": "PASS",
        "mode": "resource",
        "inputs": identities,
        "manager_epoch": current_epoch,
        "manager_epoch_authority_tool": manager_tool_identity,
        "validation": validation,
        "release_authorized": True,
        "upper_bound_update_authorized": False,
        "production_certified": False,
    }


def _detached_command(arguments: argparse.Namespace) -> dict[str, Any]:
    payloads, identities, current_epoch, manager_tool_identity = _load_common(arguments)
    resource_receipt, resource_receipt_identity = _load_json(
        arguments.resource_receipt,
        "SMM3 resource verification receipt",
    )
    _validate_resource_receipt(
        resource_receipt,
        identities,
        current_epoch,
    )
    release_token, release_token_identity = _load_json(
        arguments.release_token,
        "SMM3 release token",
    )
    _schema(release_token, RELEASE_TOKEN_SCHEMA, "release token")
    _require(
        release_token.get("status") == "RESOURCE_VERIFIED_RELEASE",
        "release token status mismatch",
    )
    validation_seed = _mapping(
        resource_receipt.get("validation"),
        "resource receipt validation",
    )
    _require(
        _run_nonce(release_token, "release token") == validation_seed.get("run_nonce")
        and _unit(release_token, "release token") == validation_seed.get("unit")
        and _invocation_id(release_token, "release token") == validation_seed.get("invocation_id")
        and release_token.get("attempt") == validation_seed.get("attempt")
        and _same_epoch(
            release_token.get("manager_epoch"),
            current_epoch,
        ),
        "release token lifecycle identity mismatch",
    )
    _identity_matches(
        release_token.get("resource_receipt"),
        resource_receipt_identity,
        "release token resource receipt",
    )
    for reference in (
        "authority",
        "selection",
        "payload_spec",
        "supervisor_start",
        "launch",
        "start_token",
        "payload_terminal",
        "preterminal",
        "completion_seal",
    ):
        _identity_matches(
            release_token.get(reference),
            identities[reference],
            f"release token {reference}",
        )
    terminal, terminal_identity = _load_json(
        arguments.terminal,
        "SMM3 terminal envelope",
    )
    cleanup, cleanup_identity = _load_json(
        arguments.cleanup,
        "SMM3 cleanup receipt",
    )
    common_references = (
        "authority",
        "selection",
        "payload_spec",
        "supervisor_start",
        "launch",
        "start_token",
        "payload_terminal",
        "preterminal",
        "completion_seal",
    )
    for reference in common_references:
        _identity_matches(
            terminal.get(reference),
            identities[reference],
            f"terminal {reference}",
        )
    _identity_matches(
        terminal.get("release_token"),
        release_token_identity,
        "terminal release token",
    )
    for reference, identity in (
        *((name, identities[name]) for name in common_references),
        ("release_token", release_token_identity),
        ("terminal", terminal_identity),
    ):
        _identity_matches(
            cleanup.get(reference),
            identity,
            f"cleanup {reference}",
        )
    validation = validate_terminal_cleanup(
        payloads["authority"],
        payloads["selection"],
        payloads["launch"],
        payloads["payload_terminal"],
        payloads["preterminal"],
        terminal,
        cleanup,
        current_epoch,
        expected_terminal=arguments.expected_terminal,
    )
    released_monotonic_ns = _positive_monotonic(
        release_token.get("released_monotonic_ns"),
        "release token",
    )
    _require(
        validation["preterminal_monotonic_ns"] < released_monotonic_ns < validation["terminal_monotonic_ns"],
        "release token: monotonic order is impossible",
    )
    live_absence = _live_absence_replay(
        payloads["authority"],
        validation,
    )
    absence_epoch, absence_manager_tool_identity = _capture_current_epoch(
        payloads["authority"],
        arguments.manager_epoch_tool,
    )
    _require(
        _same_epoch(current_epoch, absence_epoch),
        "manager/boot epoch drifted during detached live absence replay",
    )
    _require(
        absence_manager_tool_identity == manager_tool_identity,
        "manager epoch tool drifted during detached live absence replay",
    )

    formal: dict[str, Any] | None = None
    final_epoch = absence_epoch
    if arguments.formal:
        _require(
            validation["attempt"] == ATTEMPT,
            "formal detached replay is not attempt a002",
        )
        _require(
            arguments.veripb_timeout == validation["timing_contract"]["veripb_time_limit_seconds"],
            "formal detached VeriPB timeout differs from authority-rooted budget",
        )
        _require(
            arguments.expected_terminal == "success",
            "formal detached replay requires a success terminal",
        )
        _require(
            all(
                value is not None
                for value in (
                    arguments.internal_receipt,
                    arguments.formula,
                    arguments.proof,
                    arguments.veripb,
                )
            ),
            "formal detached replay arguments are incomplete",
        )
        internal, internal_identity = _load_json(
            arguments.internal_receipt,
            "SMM3 internal formal receipt",
        )
        _require(
            internal_identity == identities["completion_seal"],
            "formal internal receipt is not the pinned completion seal",
        )
        _identity_matches(
            terminal.get("internal_receipt"),
            internal_identity,
            "terminal internal formal receipt",
        )
        _identity_matches(
            cleanup.get("internal_receipt"),
            internal_identity,
            "cleanup internal formal receipt",
        )
        _, formula_identity = _snapshot_regular(
            arguments.formula,
            "SMM3 formal formula",
            collect=False,
            max_bytes=FORMULA_SIZE,
        )
        _, proof_identity = _snapshot_regular(
            arguments.proof,
            "SMM3 formal proof",
            collect=False,
            max_bytes=PROOF_LIMIT,
        )
        _validate_internal_formal(
            internal,
            internal_identity,
            payloads["authority"],
            identities,
            formula_identity,
            proof_identity,
            validation["unit"],
            terminal,
            cleanup,
        )
        second_veripb = _run_second_veripb(
            internal,
            arguments.formula,
            arguments.proof,
            arguments.veripb,
            arguments.veripb_timeout,
        )
        _, formula_replay = _snapshot_regular(
            arguments.formula,
            "SMM3 formal formula replay",
            collect=False,
            max_bytes=FORMULA_SIZE,
        )
        _, proof_replay = _snapshot_regular(
            arguments.proof,
            "SMM3 formal proof replay",
            collect=False,
            max_bytes=PROOF_LIMIT,
        )
        _require(
            formula_replay == formula_identity,
            "formal formula drifted during detached VeriPB",
        )
        _require(
            proof_replay == proof_identity,
            "formal proof drifted during detached VeriPB",
        )
        final_epoch, final_manager_tool_identity = _capture_current_epoch(
            payloads["authority"],
            arguments.manager_epoch_tool,
        )
        _require(
            _same_epoch(current_epoch, final_epoch),
            "manager/boot epoch drifted during detached VeriPB",
        )
        _require(
            final_manager_tool_identity == manager_tool_identity,
            "manager epoch tool drifted during detached VeriPB",
        )
        formal = {
            "internal_receipt": internal_identity,
            "formula": formula_identity,
            "proof": proof_identity,
            "second_veripb": second_veripb,
            "proof_status": "VERIFIED UNSATISFIABLE",
        }

    return {
        "schema_version": DETACHED_RECEIPT_SCHEMA,
        "status": "VERIFIED" if arguments.formal else "PASS",
        "mode": "detached",
        "inputs": identities,
        "resource_receipt": resource_receipt_identity,
        "release_token": release_token_identity,
        "terminal": terminal_identity,
        "cleanup": cleanup_identity,
        "manager_epoch": final_epoch,
        "manager_epoch_authority_tool": manager_tool_identity,
        "validation": validation,
        "live_absence_replay": live_absence,
        "formal": formal,
        "upper_bound_update_authorized": bool(arguments.formal),
        "ledger": {
            "upper": [1188, 18] if arguments.formal else [1188, 22],
            "lower": "absent",
        },
        "production_certified": False,
    }


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--authority", required=True, type=Path)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--payload-spec", required=True, type=Path)
    parser.add_argument("--supervisor-start", required=True, type=Path)
    parser.add_argument("--launch", required=True, type=Path)
    parser.add_argument("--start-token", required=True, type=Path)
    parser.add_argument("--payload-terminal", required=True, type=Path)
    parser.add_argument("--preterminal", required=True, type=Path)
    parser.add_argument("--completion-seal", required=True, type=Path)
    parser.add_argument("--formal-admission", type=Path)
    parser.add_argument("--manager-epoch-tool", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Independently verify SMM3 two-stage authority.",
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)
    resource = subparsers.add_parser(
        "resource",
        help="verify launch, payload terminal, and pre-terminal resources",
    )
    _add_common_arguments(resource)

    detached = subparsers.add_parser(
        "detached",
        help="repeat resource replay and verify terminal/cleanup",
    )
    _add_common_arguments(detached)
    detached.add_argument("--resource-receipt", required=True, type=Path)
    detached.add_argument("--release-token", required=True, type=Path)
    detached.add_argument("--terminal", required=True, type=Path)
    detached.add_argument("--cleanup", required=True, type=Path)
    detached.add_argument(
        "--expected-terminal",
        required=True,
        choices=("success", "postseal-failure"),
    )
    detached.add_argument("--formal", action="store_true")
    detached.add_argument("--internal-receipt", type=Path)
    detached.add_argument("--formula", type=Path)
    detached.add_argument("--proof", type=Path)
    detached.add_argument("--veripb", type=Path)
    detached.add_argument(
        "--veripb-timeout",
        type=int,
        default=DEFAULT_VERIPB_TIMEOUT_SECONDS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    schema = RESOURCE_RECEIPT_SCHEMA if arguments.mode == "resource" else DETACHED_RECEIPT_SCHEMA
    try:
        _require(
            getattr(arguments, "veripb_timeout", 1) > 0,
            "VeriPB timeout must be positive",
        )
        payload = _resource_command(arguments) if arguments.mode == "resource" else _detached_command(arguments)
        raw = _json_bytes(payload)
        output_identity = _write_exclusive(arguments.output, raw)
    except (
        OSError,
        VerificationError,
        subprocess.SubprocessError,
    ) as exc:
        failure = {
            "schema_version": schema,
            "status": "FAIL_CLOSED",
            "mode": arguments.mode,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "upper_bound_update_authorized": False,
            "ledger": {"upper": [1188, 22], "lower": "absent"},
            "production_certified": False,
        }
        try:
            output_identity = _write_exclusive(
                arguments.output,
                _json_bytes(failure),
            )
        except (OSError, VerificationError) as output_exc:
            print(
                f"SMM3_VERIFIER_ERROR: {exc}; failure receipt not written: {output_exc}",
                file=sys.stderr,
            )
            return 2
        print(
            json.dumps(
                {
                    "status": "FAIL_CLOSED",
                    "output": output_identity,
                },
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": output_identity,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
