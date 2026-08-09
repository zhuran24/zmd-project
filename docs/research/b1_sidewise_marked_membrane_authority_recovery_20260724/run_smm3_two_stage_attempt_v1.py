#!/usr/bin/env python3
"""Drive one SMM3 two-stage synthetic or formal transient-unit attempt.

The target unit contains a main supervisor and its payload.  After the payload
has terminated and been reaped, the supervisor remains as the only cgroup
member.  This ordinary-user observer records the still-live cgroup, invokes an
independent resource verifier, releases the supervisor, records the systemd
terminal state, and finally proves cleanup.

This file never invokes sudo.  Privileged read-only manager executable
attestation is isolated in the separately pinned manager-epoch helper.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from types import ModuleType
from typing import Any


AUTHORITY_SCHEMA = "b1_sidewise_smm3_pre_run_authority_v1"
SELECTION_SCHEMA = "b1_sidewise_smm3_attempt_selection_v1"
LAUNCH_SCHEMA = "b1_sidewise_smm3_launch_receipt_v1"
PRETERMINAL_SCHEMA = "b1_sidewise_smm3_preterminal_resource_v1"
TERMINAL_SCHEMA = "b1_sidewise_smm3_terminal_envelope_v1"
CLEANUP_SCHEMA = "b1_sidewise_smm3_cleanup_v1"
START_TOKEN_SCHEMA = "b1_sidewise_smm3_payload_start_token_v1"
RELEASE_TOKEN_SCHEMA = "b1_sidewise_smm3_release_token_v1"
FORMAL_ADMISSION_SCHEMA = "b1_sidewise_smm3_formal_admission_v1"
RECOVERY_CLOSEOUT_SCHEMA = "b1_sidewise_smm3_recovery_closeout_v1"

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = Path(__file__).resolve().parent
ORCHESTRATOR = RESEARCH / "run_smm3_authority_recovery_v1.py"
MANAGER_TOOL = RESEARCH / "manager_epoch_authority_v1.py"
FORMAL_PAYLOAD = RESEARCH / "run_smm3_formal_payload_v1.py"
VERIFIER = RESEARCH / "verify_smm3_two_stage_v1.py"
FIXED_PYTHON = Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13")
SYSTEMD_RUN = Path("/usr/bin/systemd-run")
SYSTEMCTL = Path("/usr/bin/systemctl")

MEMORY_HIGH = 35 * 1024**3
MEMORY_MAX = 39 * 1024**3
MEMORY_SWAP_MAX = 16 * 1024**3
PROOF_LIMIT = 5_000_000_000
LOW_WATER = 10 * 1024**3
REQUIRED_FREE = LOW_WATER + PROOF_LIMIT
FORMAL_RUNTIME_MAX_SECONDS = 9000
FORMAL_PAYLOAD_WAIT_SECONDS = 8000
FORMAL_KEEPER_TIMEOUT_SECONDS = 8700
SYNTHETIC_RUNTIME_MAX_SECONDS = 120
SYNTHETIC_PAYLOAD_WAIT_SECONDS = 30
SYNTHETIC_KEEPER_TIMEOUT_SECONDS = 90
ROUNDINGSAT_TIME_LIMIT_SECONDS = 3600
ROUNDINGSAT_MONITOR_LIMIT_SECONDS = 3900
VERIPB_TIME_LIMIT_SECONDS = 3600

UNIT_RE = re.compile(r"b1-smm3-[a-z0-9-]{8,80}\.service\Z")
INVOCATION_RE = re.compile(r"[0-9a-f]{32}\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")

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
CGROUP_FIELDS = (
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

# This loader executes exactly the bytes read from one O_NOFOLLOW descriptor.
# The expected digest and the complete logical argv are part of the immutable
# payload specification and selection.
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


class AttemptError(RuntimeError):
    """A no-overwrite, lifecycle, or authority failure."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def _strict_json(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AttemptError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise AttemptError(f"{label}: non-integer JSON number {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AttemptError(f"{label}: malformed strict JSON: {exc}") from exc


def _read_regular(
    path: Path,
    label: str,
    *,
    limit: int = 64 * 1024 * 1024,
) -> tuple[bytes, dict[str, Any]]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path.absolute(), flags)
    except OSError as exc:
        raise AttemptError(f"{label}: cannot open: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise AttemptError(f"{label}: not a regular file")
        if before.st_size < 0 or before.st_size > limit:
            raise AttemptError(f"{label}: size exceeds fixed cap")
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, min(1 << 20, limit - total + 1))
            if not block:
                break
            total += len(block)
            if total > limit:
                raise AttemptError(f"{label}: read exceeds fixed cap")
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    fields = (
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
    if tuple(getattr(before, field) for field in fields) != tuple(getattr(after, field) for field in fields):
        raise AttemptError(f"{label}: changed during same-FD read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise AttemptError(f"{label}: short read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": _sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
        "device": before.st_dev,
        "inode": before.st_ino,
        "link_count": before.st_nlink,
    }


def _identity(path: Path, label: str) -> dict[str, Any]:
    return _read_regular(path, label)[1]


def _load_json(path: Path, label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, identity = _read_regular(path, label)
    payload = _strict_json(raw, label)
    if not isinstance(payload, dict):
        raise AttemptError(f"{label}: root is not an object")
    return payload, identity


def _matches(
    actual: Mapping[str, Any],
    expected: Any,
    label: str,
) -> None:
    if not isinstance(expected, Mapping):
        raise AttemptError(f"{label}: missing pinned identity")
    for field in ("path", "size_bytes", "sha256", "mode_octal"):
        if actual.get(field) != expected.get(field):
            raise AttemptError(f"{label}: {field} drifted")


def _write_once(path: Path, raw: bytes) -> dict[str, Any]:
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise AttemptError(f"{path}: output parent is not a real directory")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o644)
    except OSError as exc:
        raise AttemptError(f"{path}: cannot create O_EXCL output: {exc}") from exc
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(descriptor, raw[offset:])
            if count <= 0:
                raise AttemptError(f"{path}: short write")
            offset += count
        os.fsync(descriptor)
        if os.fstat(descriptor).st_size != len(raw):
            raise AttemptError(f"{path}: final size mismatch")
    finally:
        os.close(descriptor)
    return _identity(path, f"output {path.name}")


def _mkdir_once(path: Path) -> None:
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise AttemptError(f"{path}: directory parent is not real")
    try:
        os.mkdir(path, 0o755)
    except OSError as exc:
        raise AttemptError(f"{path}: cannot create directory: {exc}") from exc


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_pinned_module(
    path: Path,
    expected: Any,
    label: str,
) -> tuple[ModuleType, dict[str, Any]]:
    raw, identity = _read_regular(path, label)
    _matches(identity, expected, label)
    module = ModuleType(f"_smm3_{path.stem}_{identity['sha256'][:12]}")
    module.__file__ = str(path.absolute())
    module.__package__ = None
    try:
        exec(
            compile(raw, str(path.absolute()), "exec", dont_inherit=True),
            module.__dict__,
        )
    except Exception as exc:
        raise AttemptError(f"{label}: pinned execution failed: {exc}") from exc
    return module, identity


def _load_authority(
    path: Path,
) -> tuple[dict[str, Any], dict[str, Any], ModuleType]:
    authority, authority_identity = _load_json(path, "SMM3 authority")
    if authority.get("schema_version") != AUTHORITY_SCHEMA or authority.get("status") != "PRE_RUN_AUTHORITY_PASS":
        raise AttemptError("SMM3 authority semantics failed")
    tools = authority.get("tools")
    if not isinstance(tools, dict):
        raise AttemptError("SMM3 authority tools missing")
    _matches(
        _identity(Path(__file__), "two-stage attempt runner"),
        tools.get("attempt_runner"),
        "two-stage attempt runner",
    )
    orchestrator, _ = _load_pinned_module(
        ORCHESTRATOR,
        tools.get("orchestrator"),
        "SMM3 orchestrator",
    )
    orchestrator.replay_current_toolchain(authority)
    if authority.get("git") != orchestrator.git_snapshot():
        raise AttemptError("repository identity drifted from SMM3 authority")
    current_epoch, _ = orchestrator.capture_epoch()
    if not orchestrator.same_epoch(authority.get("manager_epoch", {}), current_epoch):
        raise AttemptError("manager/boot epoch drifted from pre-run authority")
    return authority, authority_identity, orchestrator


def _epoch(
    authority: Mapping[str, Any],
    orchestrator: ModuleType,
    stage: str,
) -> dict[str, Any]:
    current, _ = orchestrator.capture_epoch()
    if not orchestrator.same_epoch(authority.get("manager_epoch", {}), current):
        raise AttemptError(f"manager/boot epoch drifted at {stage}")
    return current


def _run(
    argv: Sequence[str],
    *,
    timeout: int,
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update(
        {
            "LC_ALL": "C",
            "SYSTEMD_COLORS": "0",
            "SYSTEMD_PAGER": "cat",
            "SYSTEMD_PAGERSECURE": "1",
        }
    )
    try:
        completed = subprocess.run(
            list(argv),
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=environment,
        )
    except subprocess.TimeoutExpired as exc:
        raise AttemptError(f"command timed out: {list(argv)!r}") from exc
    return {
        "argv": list(argv),
        "exit_code": completed.returncode,
        "stdout": completed.stdout.decode("utf-8", "backslashreplace"),
        "stderr": completed.stderr.decode("utf-8", "backslashreplace"),
    }


def _systemctl_show(
    unit: str,
    fields: Sequence[str],
) -> tuple[dict[str, str], dict[str, Any]]:
    argv = [
        str(SYSTEMCTL),
        "--user",
        "show",
        unit,
        "--no-pager",
        *[f"--property={field}" for field in fields],
    ]
    record = _run(argv, timeout=15)
    if record["exit_code"] != 0 or record["stderr"]:
        raise AttemptError(f"systemctl show failed for {unit}: {record}")
    raw_stdout = record["stdout"]
    values: dict[str, str] = {}
    for line in raw_stdout.splitlines():
        if "=" not in line:
            raise AttemptError(f"systemctl show returned malformed line {line!r}")
        name, value = line.split("=", 1)
        if name in values:
            raise AttemptError(f"systemctl show duplicated property {name}")
        values[name] = value + "\n"
    if set(values) != set(fields):
        raise AttemptError(f"systemctl show field set mismatch: {sorted(values)}")
    return values, record


def _raw_scalar(values: Mapping[str, str], field: str) -> str:
    raw = values[field]
    if not raw.endswith("\n") or raw.count("\n") != 1:
        raise AttemptError(f"{field}: not a raw one-line scalar")
    return raw[:-1]


def _wait_for_file(path: Path, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file() and not path.is_symlink():
            return
        time.sleep(0.05)
    raise AttemptError(f"timed out waiting for {path}")


def _wait_for_unit(
    unit: str,
    predicate: Any,
    fields: Sequence[str],
    timeout: int,
) -> tuple[dict[str, str], dict[str, Any]]:
    deadline = time.monotonic() + timeout
    last: tuple[dict[str, str], dict[str, Any]] | None = None
    while time.monotonic() < deadline:
        current = _systemctl_show(unit, fields)
        last = current
        if predicate(current[0]):
            return current
        time.sleep(0.1)
    raise AttemptError(f"unit {unit} missed expected state; last={last!r}")


def _read_cgroup_file(path: Path, label: str) -> str:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path.absolute(), flags)
    except OSError as exc:
        raise AttemptError(f"{label}: cannot open: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise AttemptError(f"{label}: not a regular cgroup pseudo-file")
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, min(65536, 8 * 1024 * 1024 - total + 1))
            if not block:
                break
            total += len(block)
            if total > 8 * 1024 * 1024:
                raise AttemptError(f"{label}: exceeded fixed cap")
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    stable_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_nlink",
        "st_uid",
        "st_gid",
    )
    if tuple(getattr(before, name) for name in stable_fields) != tuple(getattr(after, name) for name in stable_fields):
        raise AttemptError(f"{label}: changed during same-FD read")
    raw = b"".join(chunks)
    try:
        text = raw.decode("ascii", "strict")
    except UnicodeDecodeError as exc:
        raise AttemptError(f"{label}: not strict ASCII") from exc
    if not text.endswith("\n") or "\x00" in text:
        raise AttemptError(f"{label}: raw framing failed")
    return text


def _capture_cgroup(control_group: str) -> tuple[str, dict[str, str]]:
    if not control_group.startswith("/") or ".." in control_group.split("/") or "\x00" in control_group:
        raise AttemptError("invalid ControlGroup path")
    root = Path("/sys/fs/cgroup")
    cgroup = root / control_group.lstrip("/")
    resolved_parent = cgroup.parent.resolve(strict=True)
    if root not in (resolved_parent, *resolved_parent.parents):
        raise AttemptError("ControlGroup escaped cgroup root")
    if cgroup.is_symlink() or not cgroup.is_dir():
        raise AttemptError("ControlGroup directory is absent or symlinked")
    raw = {name: _read_cgroup_file(cgroup / name, f"cgroup {name}") for name in CGROUP_FIELDS}
    return str(cgroup), raw


def _pid_exists(pid: int) -> bool:
    try:
        os.stat(f"/proc/{pid}")
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise AttemptError(f"cannot inspect PID {pid}: {exc}") from exc
    return True


def _pid_starttime(pid: int) -> int:
    raw = _read_cgroup_file(Path(f"/proc/{pid}/stat"), f"PID {pid} stat").strip()
    closing = raw.rfind(")")
    if closing < 0:
        raise AttemptError(f"PID {pid} stat lacks comm terminator")
    fields = raw[closing + 1 :].strip().split()
    if len(fields) < 20:
        raise AttemptError(f"PID {pid} stat is truncated")
    try:
        value = int(fields[19], 10)
    except ValueError as exc:
        raise AttemptError(f"PID {pid} stat starttime is malformed") from exc
    if value <= 0:
        raise AttemptError(f"PID {pid} stat starttime is nonpositive")
    return value


def _same_pid_remains(pid: int, starttime: int) -> bool:
    if not _pid_exists(pid):
        return False
    try:
        return _pid_starttime(pid) == starttime
    except AttemptError:
        if not _pid_exists(pid):
            return False
        raise


def _read_proc_cmdline(pid: int) -> list[str] | None:
    path = Path(f"/proc/{pid}/cmdline")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise AttemptError(f"cannot open PID {pid} cmdline: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, min(65536, 1_048_576 - total + 1))
            if not block:
                break
            total += len(block)
            if total > 1_048_576:
                raise AttemptError(f"PID {pid} cmdline exceeded fixed cap")
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    stable_fields = ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid")
    if tuple(getattr(before, name) for name in stable_fields) != tuple(getattr(after, name) for name in stable_fields):
        raise AttemptError(f"PID {pid} cmdline changed during same-FD read")
    raw = b"".join(chunks)
    if not raw:
        return []
    if not raw.endswith(b"\0"):
        raise AttemptError(f"PID {pid} cmdline framing failed")
    return [part.decode("utf-8", "surrogateescape") for part in raw[:-1].split(b"\0")]


def _formal_process_gate(authority: Mapping[str, Any]) -> dict[str, Any]:
    binaries = authority.get("binaries")
    tools = authority.get("tools")
    if not isinstance(binaries, dict) or not isinstance(tools, dict):
        raise AttemptError("formal process gate lacks authority toolchain")
    forbidden_paths: set[str] = {str(FORMAL_PAYLOAD.absolute())}
    forbidden_basenames = {"roundingsat", "veripb"}
    for name in ("roundingsat", "veripb"):
        value = binaries.get(name)
        if not isinstance(value, dict):
            raise AttemptError(f"formal process gate lacks {name} identity")
        for field in ("path", "resolved_path"):
            path = value.get(field)
            if isinstance(path, str) and os.path.isabs(path):
                forbidden_paths.add(path)
        target = value.get("target")
        if isinstance(target, dict):
            path = target.get("path")
            if isinstance(path, str) and os.path.isabs(path):
                forbidden_paths.add(path)
    matches: list[dict[str, Any]] = []
    scanned = 0
    current_pid = os.getpid()
    current_uid = os.getuid()
    for entry in sorted(Path("/proc").iterdir(), key=lambda path: path.name):
        if not entry.name.isdecimal():
            continue
        pid = int(entry.name, 10)
        if pid == current_pid:
            continue
        try:
            if entry.stat().st_uid != current_uid:
                continue
            argv = _read_proc_cmdline(pid)
        except FileNotFoundError:
            continue
        except AttemptError:
            if not entry.exists():
                continue
            raise
        if argv is None:
            continue
        scanned += 1
        hit = any(argument in forbidden_paths or Path(argument).name in forbidden_basenames for argument in argv)
        if hit:
            try:
                starttime = _pid_starttime(pid)
            except AttemptError:
                if not entry.exists():
                    continue
                raise
            raw = b"\0".join(argument.encode("utf-8", "surrogateescape") for argument in argv)
            matches.append(
                {
                    "pid": pid,
                    "starttime": starttime,
                    "argv_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    if matches:
        raise AttemptError(f"formal process gate found active solver workers: {matches}")
    return {
        "status": "PASS",
        "single_worker_contract": True,
        "scanned_same_uid_processes": scanned,
        "matches": [],
        "forbidden_paths": sorted(forbidden_paths),
        "forbidden_basenames": sorted(forbidden_basenames),
    }


def _make_loader_argv(
    python_path: str,
    script_path: Path,
    script_identity: Mapping[str, Any],
    logical_arguments: Sequence[str],
) -> list[str]:
    digest = script_identity.get("sha256")
    if not isinstance(digest, str) or SHA_RE.fullmatch(digest) is None:
        raise AttemptError("script identity has invalid SHA-256")
    return [
        python_path,
        "-I",
        "-c",
        PINNED_SOURCE_LOADER,
        str(script_path.absolute()),
        digest,
        *logical_arguments,
    ]


def _resource_contract(authority: Mapping[str, Any]) -> dict[str, Any]:
    value = authority.get("resource_contract")
    if not isinstance(value, dict):
        raise AttemptError("authority resource contract missing")
    expected = {
        "memory_high_bytes": MEMORY_HIGH,
        "memory_max_bytes": MEMORY_MAX,
        "memory_swap_max_bytes": MEMORY_SWAP_MAX,
        "oom_policy": "continue",
        "kill_mode": "control-group",
        "send_sigkill": "yes",
        "formal_runtime_max_seconds": FORMAL_RUNTIME_MAX_SECONDS,
        "formal_payload_wait_seconds": FORMAL_PAYLOAD_WAIT_SECONDS,
        "formal_keeper_timeout_seconds": FORMAL_KEEPER_TIMEOUT_SECONDS,
        "formal_roundingsat_time_limit_seconds": ROUNDINGSAT_TIME_LIMIT_SECONDS,
        "formal_roundingsat_monitor_limit_seconds": ROUNDINGSAT_MONITOR_LIMIT_SECONDS,
        "formal_veripb_time_limit_seconds": VERIPB_TIME_LIMIT_SECONDS,
    }
    for key, expected_value in expected.items():
        if value.get(key) != expected_value:
            raise AttemptError(f"authority resource contract drifted: {key}")
    return dict(value)


def _free_bytes(path: Path) -> int:
    stats = os.statvfs(path)
    return int(stats.f_bavail * stats.f_frsize)


def _timing_contract(purpose: str) -> dict[str, int]:
    if purpose == "formal":
        runtime = FORMAL_RUNTIME_MAX_SECONDS
        payload_wait = FORMAL_PAYLOAD_WAIT_SECONDS
        keeper_timeout = FORMAL_KEEPER_TIMEOUT_SECONDS
    elif purpose in {"synthetic_success", "synthetic_postseal_failure"}:
        runtime = SYNTHETIC_RUNTIME_MAX_SECONDS
        payload_wait = SYNTHETIC_PAYLOAD_WAIT_SECONDS
        keeper_timeout = SYNTHETIC_KEEPER_TIMEOUT_SECONDS
    else:
        raise AttemptError(f"unsupported timing purpose {purpose!r}")
    return {
        "runtime_max_seconds": runtime,
        "payload_wait_seconds": payload_wait,
        "keeper_timeout_seconds": keeper_timeout,
        "roundingsat_time_limit_seconds": ROUNDINGSAT_TIME_LIMIT_SECONDS,
        "roundingsat_monitor_limit_seconds": ROUNDINGSAT_MONITOR_LIMIT_SECONDS,
        "veripb_time_limit_seconds": VERIPB_TIME_LIMIT_SECONDS,
    }


def _validate_synthetic_detached(
    path: Path,
    expected_terminal: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload, identity = _load_json(path, f"{expected_terminal} detached receipt")
    validation = payload.get("validation")
    if not isinstance(validation, dict):
        raise AttemptError("synthetic detached receipt lacks validation")
    if (
        payload.get("status") != "PASS"
        or payload.get("mode") != "detached"
        or payload.get("upper_bound_update_authorized") is not False
        or payload.get("ledger") != {"upper": [1188, 22], "lower": "absent"}
        or validation.get("terminal_class") != expected_terminal
        or validation.get("unit_absent") is not True
        or validation.get("cgroup_absent") is not True
        or validation.get("remaining_pids") != []
    ):
        raise AttemptError(f"synthetic {expected_terminal} detached semantics failed")
    return payload, identity


def _publish_formal_admission(
    *,
    authority_path: Path,
    success_path: Path,
    failure_path: Path,
    output: Path,
) -> dict[str, Any]:
    authority, authority_identity, orchestrator = _load_authority(authority_path)
    run_dir = ROOT / authority["run"]
    if (
        output.parent != run_dir
        or success_path != run_dir / "synthetic-success-a001/detached-verification.json"
        or failure_path != run_dir / "synthetic-postseal-fail-a001/detached-verification.json"
    ):
        raise AttemptError("formal admission paths are not canonical")
    _, success_identity = _validate_synthetic_detached(success_path, "success")
    _, failure_identity = _validate_synthetic_detached(
        failure_path,
        "postseal-failure",
    )
    replay_dir = run_dir / "formal-admission-replays-a001"
    _mkdir_once(replay_dir)
    replay_commands: dict[str, Any] = {}
    replay_identities: dict[str, Any] = {}
    for label, attempt_name, expected_terminal in (
        ("success", "synthetic-success-a001", "success"),
        (
            "postseal_failure",
            "synthetic-postseal-fail-a001",
            "postseal-failure",
        ),
    ):
        attempt_root = run_dir / attempt_name
        replay_output = replay_dir / f"{label}.json"
        detached_arguments = [
            "detached",
            "--authority",
            str(authority_path),
            "--selection",
            str(attempt_root / "selection.json"),
            "--payload-spec",
            str(attempt_root / "payload-spec.json"),
            "--supervisor-start",
            str(attempt_root / "state/supervisor-start.json"),
            "--launch",
            str(attempt_root / "launch.json"),
            "--start-token",
            str(attempt_root / "start-token.json"),
            "--payload-terminal",
            str(attempt_root / "state/payload-terminal.json"),
            "--preterminal",
            str(attempt_root / "preterminal.json"),
            "--completion-seal",
            str(attempt_root / "state/payload-seal.json"),
            "--manager-epoch-tool",
            str(MANAGER_TOOL),
            "--resource-receipt",
            str(attempt_root / "resource-verification.json"),
            "--release-token",
            str(attempt_root / "release-token.json"),
            "--terminal",
            str(attempt_root / "terminal.json"),
            "--cleanup",
            str(attempt_root / "cleanup.json"),
            "--expected-terminal",
            expected_terminal,
            "--output",
            str(replay_output),
        ]
        replay_commands[label] = _run_verifier(
            authority,
            detached_arguments,
        )
        _, replay_identities[label] = _validate_synthetic_detached(
            replay_output,
            expected_terminal,
        )
    if (run_dir / "formal-attempt-a002").exists():
        raise AttemptError("formal a002 attempt already exists")
    available = _free_bytes(run_dir)
    if available < REQUIRED_FREE:
        raise AttemptError(f"formal disk gate failed: {available} < {REQUIRED_FREE}")
    process_gate = _formal_process_gate(authority)
    current_epoch = _epoch(authority, orchestrator, "formal admission")
    admission = {
        "schema_version": FORMAL_ADMISSION_SCHEMA,
        "status": "FORMAL_ADMISSION_PASS",
        "created_utc": _utc_now(),
        "run_nonce": authority["run_nonce"],
        "authority": authority_identity,
        "manager_epoch": current_epoch,
        "synthetic_success": success_identity,
        "synthetic_postseal_failure": failure_identity,
        "independent_detached_replays": replay_identities,
        "independent_detached_replay_commands": replay_commands,
        "resource_contract": _resource_contract(authority),
        "timing_contract": _timing_contract("formal"),
        "disk_gate": {
            "available_bytes": available,
            "required_bytes": REQUIRED_FREE,
            "proof_reservation_bytes": PROOF_LIMIT,
            "artifact_low_water_bytes": LOW_WATER,
            "pass": True,
        },
        "process_gate": process_gate,
        "historical_inputs_replayed_by_authority": True,
        "formal_attempt": "a002",
        "formal_attempt_selected": False,
        "upper_bound_update_authorized": False,
        "ledger": {"upper": [1188, 22], "lower": "absent"},
        "production_certified": False,
    }
    identity = _write_once(output, _json_bytes(admission))
    _epoch(authority, orchestrator, "formal admission published")
    return {
        "status": "FORMAL_ADMISSION_PASS",
        "admission": identity,
        "formal_attempt_selected": False,
        "upper_bound_update_authorized": False,
    }


def _replay_formal_admission(
    *,
    path: Path,
    authority: Mapping[str, Any],
    authority_identity: Mapping[str, Any],
    orchestrator: ModuleType,
    attempt_dir: Path,
) -> dict[str, Any]:
    admission, admission_identity = _load_json(path, "formal admission")
    if (
        admission.get("schema_version") != FORMAL_ADMISSION_SCHEMA
        or admission.get("status") != "FORMAL_ADMISSION_PASS"
        or admission.get("run_nonce") != authority["run_nonce"]
        or admission.get("formal_attempt") != "a002"
        or admission.get("formal_attempt_selected") is not False
        or admission.get("upper_bound_update_authorized") is not False
        or admission.get("ledger") != {"upper": [1188, 22], "lower": "absent"}
    ):
        raise AttemptError("formal admission semantics failed")
    _matches(authority_identity, admission.get("authority"), "formal admission authority")
    if not orchestrator.same_epoch(
        authority["manager_epoch"],
        admission.get("manager_epoch", {}),
    ):
        raise AttemptError("formal admission manager epoch drifted")
    run_dir = ROOT / authority["run"]
    if path != run_dir / "formal-admission-a001.json":
        raise AttemptError("formal admission path is not canonical")
    for field, expected_path, expected_terminal in (
        (
            "synthetic_success",
            run_dir / "synthetic-success-a001/detached-verification.json",
            "success",
        ),
        (
            "synthetic_postseal_failure",
            run_dir / "synthetic-postseal-fail-a001/detached-verification.json",
            "postseal-failure",
        ),
    ):
        _, current_identity = _validate_synthetic_detached(
            expected_path,
            expected_terminal,
        )
        _matches(current_identity, admission.get(field), f"formal admission {field}")
    replay_identities = admission.get("independent_detached_replays")
    if not isinstance(replay_identities, dict):
        raise AttemptError("formal admission lacks detached replay identities")
    for label, expected_terminal in (
        ("success", "success"),
        ("postseal_failure", "postseal-failure"),
    ):
        replay_path = run_dir / f"formal-admission-replays-a001/{label}.json"
        _, replay_identity = _validate_synthetic_detached(
            replay_path,
            expected_terminal,
        )
        _matches(
            replay_identity,
            replay_identities.get(label),
            f"formal admission replay {label}",
        )
    if attempt_dir != run_dir / "formal-attempt-a002":
        raise AttemptError("formal a002 directory is not canonical")
    available = _free_bytes(run_dir)
    if available < REQUIRED_FREE:
        raise AttemptError(f"formal disk gate drifted: {available} < {REQUIRED_FREE}")
    process_gate = admission.get("process_gate")
    if (
        not isinstance(process_gate, dict)
        or process_gate.get("status") != "PASS"
        or process_gate.get("single_worker_contract") is not True
        or process_gate.get("matches") != []
    ):
        raise AttemptError("formal admission process gate semantics failed")
    _formal_process_gate(authority)
    _epoch(authority, orchestrator, "formal pre-selection admission replay")
    return admission_identity


def _publish_recovery_closeout(
    *,
    authority_path: Path,
    result_path: Path,
    output: Path,
) -> dict[str, Any]:
    authority, authority_identity, orchestrator = _load_authority(authority_path)
    run_dir = ROOT / authority["run"]
    if output != run_dir / "closeout-a001.json":
        raise AttemptError("recovery closeout path is not canonical")
    canonical_success = run_dir / "formal-attempt-a002/detached-verification.json"
    canonical_failure = run_dir / "formal-attempt-a002/attempt-failure-a001.json"
    if result_path == canonical_success:
        result, result_identity = _load_json(result_path, "formal detached result")
        inputs = result.get("inputs")
        if (
            result.get("schema_version") != "b1_sidewise_smm3_detached_closeout_v1"
            or result.get("status") != "VERIFIED"
            or result.get("upper_bound_update_authorized") is not True
            or result.get("ledger") != {"upper": [1188, 18], "lower": "absent"}
            or result.get("production_certified") is not False
            or not isinstance(inputs, dict)
        ):
            raise AttemptError("formal detached result semantics failed")
        _matches(
            authority_identity,
            inputs.get("authority"),
            "formal detached authority",
        )
        if not orchestrator.same_epoch(
            authority["manager_epoch"],
            result.get("manager_epoch", {}),
        ):
            raise AttemptError("formal detached manager/boot epoch drifted")
        status = "VERIFIED"
        ledger = {"upper": [1188, 18], "lower": "absent"}
        update_authorized = True
    elif result_path == canonical_failure:
        result, result_identity = _load_json(result_path, "formal attempt failure")
        if (
            result.get("schema_version") != "b1_sidewise_smm3_attempt_failure_v1"
            or result.get("status") != "FORMAL_AUTHORITY_INCOMPLETE"
            or result.get("attempt") != "a002"
            or result.get("purpose") != "formal"
            or result.get("selection_created") is not True
            or result.get("attempt_consumed") is not True
            or result.get("upper_bound_update_authorized") is not False
            or result.get("ledger") != {"upper": [1188, 22], "lower": "absent"}
        ):
            raise AttemptError("formal attempt failure semantics failed")
        status = "FORMAL_AUTHORITY_INCOMPLETE"
        ledger = {"upper": [1188, 22], "lower": "absent"}
        update_authorized = False
    else:
        raise AttemptError("recovery closeout result path is not canonical")
    closeout = {
        "schema_version": RECOVERY_CLOSEOUT_SCHEMA,
        "status": status,
        "created_utc": _utc_now(),
        "run_nonce": authority["run_nonce"],
        "authority": authority_identity,
        "result": result_identity,
        "formal_attempt": "a002_consumed_no_retry",
        "upper_bound_update_authorized": update_authorized,
        "ledger": ledger,
        "next_required_task": "CUTS_GATE1_V4_AUTHORITY_COMPLETION",
        "claim_scope": "research_only",
        "production_certified": False,
    }
    closeout_identity = _write_once(output, _json_bytes(closeout))
    _epoch(authority, orchestrator, "recovery closeout published")
    return {
        "status": status,
        "closeout": closeout_identity,
        "upper_bound_update_authorized": update_authorized,
        "ledger": ledger,
        "next_required_task": "CUTS_GATE1_V4_AUTHORITY_COMPLETION",
    }


def _publish_selection(
    *,
    authority: Mapping[str, Any],
    authority_identity: Mapping[str, Any],
    orchestrator: ModuleType,
    path: Path,
    attempt: str,
    purpose: str,
    unit: str,
    worker_argv: list[str],
    payload_spec_identity: Mapping[str, Any],
    formal_admission: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    before = _epoch(authority, orchestrator, f"{attempt} pre-selection")
    selection = {
        "schema_version": SELECTION_SCHEMA,
        "status": "SELECTED_CONSUMED",
        "created_utc": _utc_now(),
        "attempt": attempt,
        "purpose": purpose,
        "run_nonce": authority["run_nonce"],
        "unit": unit,
        "authority": dict(authority_identity),
        "manager_epoch": before,
        "worker_argv": worker_argv,
        "payload_spec": dict(payload_spec_identity),
        "formal_admission": (None if formal_admission is None else dict(formal_admission)),
        "resource_contract": _resource_contract(authority),
        "timing_contract": _timing_contract(purpose),
        "upper_bound_update_authorized": False,
    }
    selection_identity = _write_once(path, _json_bytes(selection))
    _epoch(authority, orchestrator, f"{attempt} post-selection")
    return selection, selection_identity


def _run_verifier(
    authority: Mapping[str, Any],
    mode_arguments: Sequence[str],
) -> dict[str, Any]:
    tools = authority["tools"]
    verifier_identity = tools["independent_verifier"]
    python_target = authority["binaries"]["fixed_python"]["target"]
    python_path = python_target["path"]
    argv = _make_loader_argv(
        python_path,
        VERIFIER,
        verifier_identity,
        mode_arguments,
    )
    timeout = 3700 if "--formal" in mode_arguments else 60
    record = _run(argv, timeout=timeout)
    if record["exit_code"] != 0:
        raise AttemptError(f"independent verifier failed: {record}")
    return record


def _validate_attempt_name(attempt: str, purpose: str) -> None:
    expected = {
        "synthetic-success-a001": "synthetic_success",
        "synthetic-postseal-fail-a001": "synthetic_postseal_failure",
        "a002": "formal",
    }
    if expected.get(attempt) != purpose:
        raise AttemptError("attempt/purpose pair is not pre-registered")


def _terminal_matches(raw: Mapping[str, str], expected: str) -> bool:
    if expected == "success":
        values = {
            "ActiveState": "active",
            "SubState": "exited",
            "Result": "success",
            "ExecMainCode": "1",
            "ExecMainStatus": "0",
        }
    elif expected == "postseal-failure":
        values = {
            "ActiveState": "failed",
            "SubState": "failed",
            "Result": "exit-code",
            "ExecMainCode": "1",
            "ExecMainStatus": "7",
        }
    else:
        raise AttemptError(f"unsupported terminal class {expected!r}")
    return all(_raw_scalar(raw, name) == value for name, value in values.items())


def _attempt_paths(attempt_dir: Path) -> dict[str, Path]:
    return {
        "payload_spec": attempt_dir / "payload-spec.json",
        "selection": attempt_dir / "selection.json",
        "launch": attempt_dir / "launch.json",
        "start": attempt_dir / "start-token.json",
        "payload_terminal": attempt_dir / "state/payload-terminal.json",
        "preterminal": attempt_dir / "preterminal.json",
        "resource": attempt_dir / "resource-verification.json",
        "release": attempt_dir / "release-token.json",
        "terminal": attempt_dir / "terminal.json",
        "cleanup": attempt_dir / "cleanup.json",
        "detached": attempt_dir / "detached-verification.json",
        "seal": attempt_dir / "state/payload-seal.json",
        "formal": attempt_dir / "formal-a002",
    }


def _build_payload(
    *,
    authority: Mapping[str, Any],
    authority_path: Path,
    selection_path: Path,
    attempt_dir: Path,
    attempt: str,
    purpose: str,
    unit: str,
) -> tuple[list[str], list[str], Path]:
    tools = authority["tools"]
    python_path = authority["binaries"]["fixed_python"]["target"]["path"]
    if purpose == "formal":
        logical = [
            str(FORMAL_PAYLOAD.absolute()),
            "--authority",
            str(authority_path.absolute()),
            "--selection",
            str(selection_path.absolute()),
            "--output-dir",
            str((attempt_dir / "formal-a002").absolute()),
            "--expected-systemd-unit",
            unit,
        ]
        executed = _make_loader_argv(
            python_path,
            FORMAL_PAYLOAD,
            tools["formal_payload"],
            logical[1:],
        )
        completion_seal = attempt_dir / "formal-a002/internal_formal_receipt.json"
        return logical, executed, completion_seal
    exit_code = 0 if purpose == "synthetic_success" else 7
    logical = [
        str(ORCHESTRATOR.absolute()),
        "--synthetic-payload",
        "--run-nonce",
        authority["run_nonce"],
        "--attempt",
        attempt,
        "--synthetic-seal",
        str((attempt_dir / "state/payload-seal.json").absolute()),
        "--synthetic-exit-code",
        str(exit_code),
        "--synthetic-purpose",
        purpose,
        "--synthetic-unit",
        unit,
    ]
    executed = _make_loader_argv(
        python_path,
        ORCHESTRATOR,
        tools["orchestrator"],
        logical[1:],
    )
    return logical, executed, attempt_dir / "state/payload-seal.json"


def _launch_attempt(
    *,
    authority_path: Path,
    attempt_dir: Path,
    attempt: str,
    purpose: str,
    unit: str,
    formal_admission_path: Path | None,
) -> dict[str, Any]:
    _validate_attempt_name(attempt, purpose)
    if not UNIT_RE.fullmatch(unit):
        raise AttemptError("unit name is not canonical")
    authority, authority_identity, orchestrator = _load_authority(authority_path)
    paths = _attempt_paths(attempt_dir)
    expected_dir_name = {
        "synthetic_success": "synthetic-success-a001",
        "synthetic_postseal_failure": "synthetic-postseal-fail-a001",
        "formal": "formal-attempt-a002",
    }[purpose]
    if attempt_dir.name != expected_dir_name:
        raise AttemptError("attempt directory name is not pre-registered")
    if attempt_dir.parent != ROOT / authority["run"]:
        raise AttemptError("attempt directory is outside the authority run")
    formal_admission_identity: dict[str, Any] | None = None
    if purpose == "formal":
        if formal_admission_path is None:
            raise AttemptError("formal attempt lacks admission receipt")
        formal_admission_identity = _replay_formal_admission(
            path=formal_admission_path,
            authority=authority,
            authority_identity=authority_identity,
            orchestrator=orchestrator,
            attempt_dir=attempt_dir,
        )
    elif formal_admission_path is not None:
        raise AttemptError("synthetic attempt cannot consume formal admission")
    if attempt_dir.exists() or attempt_dir.is_symlink():
        raise AttemptError("attempt directory already exists")
    _mkdir_once(attempt_dir)
    _mkdir_once(attempt_dir / "state")

    logical_worker, executed_worker, completion_seal = _build_payload(
        authority=authority,
        authority_path=authority_path,
        selection_path=paths["selection"],
        attempt_dir=attempt_dir,
        attempt=attempt,
        purpose=purpose,
        unit=unit,
    )
    payload_spec = {
        "schema_version": "b1_sidewise_smm3_payload_spec_v1",
        "run_nonce": authority["run_nonce"],
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "authority": authority_identity,
        "manager_epoch": authority["manager_epoch"],
        "argv": executed_worker,
        "logical_worker_argv": logical_worker,
        "completion_seal": str(completion_seal.absolute()),
        "resource_contract": _resource_contract(authority),
        "timing_contract": _timing_contract(purpose),
    }
    payload_spec_identity = _write_once(
        paths["payload_spec"],
        _json_bytes(payload_spec),
    )
    _, selection_identity = _publish_selection(
        authority=authority,
        authority_identity=authority_identity,
        orchestrator=orchestrator,
        path=paths["selection"],
        attempt=attempt,
        purpose=purpose,
        unit=unit,
        worker_argv=logical_worker,
        payload_spec_identity=payload_spec_identity,
        formal_admission=formal_admission_identity,
    )

    supervisor_arguments = [
        "--supervisor",
        "--state-dir",
        str((attempt_dir / "state").absolute()),
        "--payload-spec",
        str(paths["payload_spec"].absolute()),
        "--payload-spec-sha256",
        payload_spec_identity["sha256"],
        "--unit",
        unit,
        "--attempt",
        attempt,
        "--run-nonce",
        authority["run_nonce"],
        "--start-token",
        str(paths["start"].absolute()),
        "--release-token",
        str(paths["release"].absolute()),
        "--keeper-timeout",
        str(_timing_contract(purpose)["keeper_timeout_seconds"]),
    ]
    python_path = authority["binaries"]["fixed_python"]["target"]["path"]
    supervisor_argv = _make_loader_argv(
        python_path,
        ORCHESTRATOR,
        authority["tools"]["orchestrator"],
        supervisor_arguments,
    )
    timing_contract = _timing_contract(purpose)
    runtime_seconds = timing_contract["runtime_max_seconds"]
    systemd_argv = [
        str(SYSTEMD_RUN),
        "--user",
        "--no-block",
        f"--unit={unit}",
        "--property=Type=exec",
        "--property=RemainAfterExit=yes",
        f"--property=MemoryHigh={MEMORY_HIGH}",
        f"--property=MemoryMax={MEMORY_MAX}",
        f"--property=MemorySwapMax={MEMORY_SWAP_MAX}",
        "--property=OOMPolicy=continue",
        "--property=KillMode=control-group",
        "--property=SendSIGKILL=yes",
        f"--property=RuntimeMaxSec={runtime_seconds}",
        *supervisor_argv,
    ]
    _epoch(authority, orchestrator, f"{attempt} launch")
    launch_requested_monotonic_ns = time.monotonic_ns()
    launch_command = _run(systemd_argv, timeout=30)
    if launch_command["exit_code"] != 0:
        raise AttemptError(f"systemd-run failed: {launch_command}")
    _wait_for_file(attempt_dir / "state/supervisor-start.json", 30)
    supervisor_start, supervisor_start_identity = _load_json(
        attempt_dir / "state/supervisor-start.json",
        "supervisor start",
    )
    if (
        supervisor_start.get("run_nonce") != authority["run_nonce"]
        or supervisor_start.get("attempt") != attempt
        or supervisor_start.get("unit") != unit
    ):
        raise AttemptError("supervisor start semantics failed")
    supervisor_pid = supervisor_start.get("supervisor_pid")
    payload_pid = supervisor_start.get("payload_pid")
    if (
        type(supervisor_pid) is not int
        or type(payload_pid) is not int
        or supervisor_pid <= 0
        or payload_pid <= 0
        or supervisor_pid == payload_pid
    ):
        raise AttemptError("supervisor start PIDs are invalid")
    pid_starttimes = {
        str(supervisor_pid): _pid_starttime(supervisor_pid),
        str(payload_pid): _pid_starttime(payload_pid),
    }
    initial_raw, initial_command = _wait_for_unit(
        unit,
        lambda raw: (
            _raw_scalar(raw, "ActiveState") == "active"
            and _raw_scalar(raw, "SubState") == "running"
            and _raw_scalar(raw, "MainPID") == str(supervisor_pid)
            and bool(_raw_scalar(raw, "InvocationID"))
            and bool(_raw_scalar(raw, "ControlGroup"))
        ),
        SYSTEMD_PRETERMINAL_FIELDS,
        30,
    )
    invocation_id = _raw_scalar(initial_raw, "InvocationID")
    if INVOCATION_RE.fullmatch(invocation_id) is None:
        raise AttemptError("systemd returned malformed InvocationID")
    if supervisor_start.get("invocation_id") != invocation_id:
        raise AttemptError("supervisor and systemd InvocationID differ")
    cgroup_path, initial_cgroup = _capture_cgroup(_raw_scalar(initial_raw, "ControlGroup"))
    initial_procs = [int(line) for line in initial_cgroup["cgroup.procs"].splitlines() if line]
    if sorted(initial_procs) != sorted([supervisor_pid, payload_pid]):
        raise AttemptError("initial cgroup does not contain exactly supervisor and payload")
    launch_epoch = _epoch(authority, orchestrator, f"{attempt} launched")
    launch_observed_monotonic_ns = time.monotonic_ns()
    launch = {
        "schema_version": LAUNCH_SCHEMA,
        "status": "LAUNCHED",
        "created_utc": _utc_now(),
        "run_nonce": authority["run_nonce"],
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "invocation_id": invocation_id,
        "manager_epoch": launch_epoch,
        "authority": authority_identity,
        "selection": selection_identity,
        "resource_contract": _resource_contract(authority),
        "timing_contract": timing_contract,
        "supervisor_pid": supervisor_pid,
        "payload_pid": payload_pid,
        "pid_starttimes": pid_starttimes,
        "payload_spec": payload_spec_identity,
        "supervisor_start": supervisor_start_identity,
        "systemd_run": launch_command,
        "systemd_argv": systemd_argv,
        "initial_systemd_raw": initial_raw,
        "initial_systemctl": initial_command,
        "initial_cgroup_path": cgroup_path,
        "initial_cgroup_procs_raw": initial_cgroup["cgroup.procs"],
        "initial_cgroup_raw": initial_cgroup,
        "launch_requested_monotonic_ns": launch_requested_monotonic_ns,
        "launch_observed_monotonic_ns": launch_observed_monotonic_ns,
        "upper_bound_update_authorized": False,
    }
    launch_identity = _write_once(paths["launch"], _json_bytes(launch))
    start_token = {
        "schema_version": START_TOKEN_SCHEMA,
        "status": "PAYLOAD_START_AUTHORIZED",
        "created_utc": _utc_now(),
        "run_nonce": authority["run_nonce"],
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "invocation_id": invocation_id,
        "manager_epoch": launch_epoch,
        "authority": authority_identity,
        "selection": selection_identity,
        "launch": launch_identity,
        "payload_spec": payload_spec_identity,
        "supervisor_start": supervisor_start_identity,
        "resource_contract": _resource_contract(authority),
        "timing_contract": timing_contract,
        "completion_seal": str(completion_seal.absolute()),
        "authorized_monotonic_ns": time.monotonic_ns(),
    }
    start_token_identity = _write_once(paths["start"], _json_bytes(start_token))

    payload_timeout = timing_contract["payload_wait_seconds"]
    _wait_for_file(paths["payload_terminal"], payload_timeout)
    payload_terminal, payload_terminal_identity = _load_json(
        paths["payload_terminal"],
        "payload terminal",
    )
    _, completion_seal_identity = _load_json(
        completion_seal,
        "payload completion seal",
    )
    _matches(
        completion_seal_identity,
        payload_terminal.get("completion_seal"),
        "payload terminal completion seal",
    )
    pre_epoch = _epoch(authority, orchestrator, f"{attempt} pre-terminal")
    pre_raw, pre_command = _wait_for_unit(
        unit,
        lambda raw: (
            _raw_scalar(raw, "ActiveState") == "active"
            and _raw_scalar(raw, "SubState") == "running"
            and _raw_scalar(raw, "MainPID") == str(supervisor_pid)
        ),
        SYSTEMD_PRETERMINAL_FIELDS,
        30,
    )
    pre_cgroup_path, cgroup_raw = _capture_cgroup(_raw_scalar(pre_raw, "ControlGroup"))
    if pre_cgroup_path != cgroup_path:
        raise AttemptError("ControlGroup path changed before terminal")
    if paths["release"].exists() or paths["release"].is_symlink():
        raise AttemptError("release token existed before resource verification")
    preterminal_captured_monotonic_ns = time.monotonic_ns()
    preterminal = {
        "schema_version": PRETERMINAL_SCHEMA,
        "status": "PRETERMINAL_CAPTURED",
        "created_utc": _utc_now(),
        "run_nonce": authority["run_nonce"],
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "invocation_id": invocation_id,
        "manager_epoch": pre_epoch,
        "authority": authority_identity,
        "selection": selection_identity,
        "launch": launch_identity,
        "payload_terminal": payload_terminal_identity,
        "payload_spec": payload_spec_identity,
        "start_token": start_token_identity,
        "supervisor_start": supervisor_start_identity,
        "completion_seal": completion_seal_identity,
        "resource_contract": _resource_contract(authority),
        "timing_contract": timing_contract,
        "supervisor_pid": supervisor_pid,
        "payload_pid": payload_pid,
        "keeper_pid": supervisor_pid,
        "payload_reaped": payload_terminal.get("payload_reaped") is True,
        "release_created": False,
        "systemd_raw": pre_raw,
        "systemctl": pre_command,
        "cgroup_path": pre_cgroup_path,
        "cgroup_raw": cgroup_raw,
        "captured_monotonic_ns": preterminal_captured_monotonic_ns,
        "upper_bound_update_authorized": False,
    }
    preterminal_identity = _write_once(
        paths["preterminal"],
        _json_bytes(preterminal),
    )
    resource_arguments = [
        "resource",
        "--authority",
        str(authority_path.absolute()),
        "--selection",
        str(paths["selection"].absolute()),
        "--payload-spec",
        str(paths["payload_spec"].absolute()),
        "--supervisor-start",
        str((attempt_dir / "state/supervisor-start.json").absolute()),
        "--launch",
        str(paths["launch"].absolute()),
        "--start-token",
        str(paths["start"].absolute()),
        "--payload-terminal",
        str(paths["payload_terminal"].absolute()),
        "--preterminal",
        str(paths["preterminal"].absolute()),
        "--completion-seal",
        str(completion_seal.absolute()),
        "--manager-epoch-tool",
        str(MANAGER_TOOL.absolute()),
        "--output",
        str(paths["resource"].absolute()),
    ]
    if formal_admission_path is not None:
        resource_arguments.extend(["--formal-admission", str(formal_admission_path.absolute())])
    resource_command = _run_verifier(authority, resource_arguments)
    resource, resource_identity = _load_json(
        paths["resource"],
        "resource verification",
    )
    if resource.get("status") != "PASS" or resource.get("release_authorized") is not True:
        raise AttemptError("resource verifier did not authorize release")
    release_epoch = _epoch(authority, orchestrator, f"{attempt} release")
    release_monotonic_ns = time.monotonic_ns()
    release = {
        "schema_version": RELEASE_TOKEN_SCHEMA,
        "status": "RESOURCE_VERIFIED_RELEASE",
        "created_utc": _utc_now(),
        "run_nonce": authority["run_nonce"],
        "attempt": attempt,
        "unit": unit,
        "invocation_id": invocation_id,
        "manager_epoch": release_epoch,
        "authority": authority_identity,
        "selection": selection_identity,
        "launch": launch_identity,
        "payload_spec": payload_spec_identity,
        "supervisor_start": supervisor_start_identity,
        "start_token": start_token_identity,
        "payload_terminal": payload_terminal_identity,
        "preterminal": preterminal_identity,
        "completion_seal": completion_seal_identity,
        "resource_receipt": resource_identity,
        "resource_contract": _resource_contract(authority),
        "timing_contract": timing_contract,
        "released_monotonic_ns": release_monotonic_ns,
    }
    release_identity = _write_once(paths["release"], _json_bytes(release))

    if purpose in {"synthetic_success", "formal"}:
        expected_terminal = "success"
    else:
        expected_terminal = "postseal-failure"
    terminal_raw, terminal_command = _wait_for_unit(
        unit,
        lambda raw: _terminal_matches(raw, expected_terminal),
        SYSTEMD_TERMINAL_FIELDS,
        60,
    )
    terminal_epoch = _epoch(authority, orchestrator, f"{attempt} terminal")
    terminal_captured_monotonic_ns = time.monotonic_ns()
    terminal = {
        "schema_version": TERMINAL_SCHEMA,
        "status": "TERMINAL_CAPTURED",
        "created_utc": _utc_now(),
        "run_nonce": authority["run_nonce"],
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "invocation_id": invocation_id,
        "manager_epoch": terminal_epoch,
        "authority": authority_identity,
        "selection": selection_identity,
        "launch": launch_identity,
        "payload_spec": payload_spec_identity,
        "supervisor_start": supervisor_start_identity,
        "start_token": start_token_identity,
        "payload_terminal": payload_terminal_identity,
        "preterminal": preterminal_identity,
        "completion_seal": completion_seal_identity,
        "resource_verification": resource_identity,
        "release_token": release_identity,
        "resource_contract": _resource_contract(authority),
        "timing_contract": timing_contract,
        "systemd_raw": terminal_raw,
        "systemctl": terminal_command,
        "captured_monotonic_ns": terminal_captured_monotonic_ns,
        "upper_bound_update_authorized": False,
    }
    if purpose == "formal":
        terminal["internal_receipt"] = completion_seal_identity
    terminal_identity = _write_once(paths["terminal"], _json_bytes(terminal))

    stop_record = _run(
        [str(SYSTEMCTL), "--user", "stop", unit],
        timeout=30,
    )
    reset_record = _run(
        [str(SYSTEMCTL), "--user", "reset-failed", unit],
        timeout=30,
    )
    deadline = time.monotonic() + 30
    load_state_record: dict[str, Any] | None = None
    unit_absent = False
    while time.monotonic() < deadline:
        load_state_record = _run(
            [
                str(SYSTEMCTL),
                "--user",
                "show",
                unit,
                "--property=LoadState",
                "--value",
            ],
            timeout=10,
        )
        if load_state_record["exit_code"] == 0 and load_state_record["stdout"] == "not-found\n":
            unit_absent = True
            break
        time.sleep(0.1)
    checked_pids = sorted({supervisor_pid, payload_pid})
    remaining_pids = [pid for pid in checked_pids if _same_pid_remains(pid, pid_starttimes[str(pid)])]
    cgroup_absent = not Path(cgroup_path).exists()
    cleanup_epoch = _epoch(authority, orchestrator, f"{attempt} cleanup")
    cleanup_captured_monotonic_ns = time.monotonic_ns()
    cleanup = {
        "schema_version": CLEANUP_SCHEMA,
        "status": "CLEANUP_CAPTURED",
        "created_utc": _utc_now(),
        "run_nonce": authority["run_nonce"],
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "invocation_id": invocation_id,
        "manager_epoch": cleanup_epoch,
        "authority": authority_identity,
        "selection": selection_identity,
        "launch": launch_identity,
        "payload_spec": payload_spec_identity,
        "supervisor_start": supervisor_start_identity,
        "start_token": start_token_identity,
        "payload_terminal": payload_terminal_identity,
        "preterminal": preterminal_identity,
        "completion_seal": completion_seal_identity,
        "terminal": terminal_identity,
        "resource_verification": resource_identity,
        "release_token": release_identity,
        "resource_contract": _resource_contract(authority),
        "timing_contract": timing_contract,
        "stop": stop_record,
        "reset_failed": reset_record,
        "load_state": load_state_record,
        "unit_absent": unit_absent,
        "checked_pids": checked_pids,
        "pid_starttimes": pid_starttimes,
        "remaining_pids": remaining_pids,
        "cgroup_path": cgroup_path,
        "cgroup_absent": cgroup_absent,
        "terminal_control_group_used_as_cleanup_evidence": False,
        "captured_monotonic_ns": cleanup_captured_monotonic_ns,
        "upper_bound_update_authorized": False,
    }
    if purpose == "formal":
        cleanup["internal_receipt"] = completion_seal_identity
    cleanup_identity = _write_once(paths["cleanup"], _json_bytes(cleanup))
    detached_arguments = [
        "detached",
        "--authority",
        str(authority_path.absolute()),
        "--selection",
        str(paths["selection"].absolute()),
        "--payload-spec",
        str(paths["payload_spec"].absolute()),
        "--supervisor-start",
        str((attempt_dir / "state/supervisor-start.json").absolute()),
        "--launch",
        str(paths["launch"].absolute()),
        "--start-token",
        str(paths["start"].absolute()),
        "--payload-terminal",
        str(paths["payload_terminal"].absolute()),
        "--preterminal",
        str(paths["preterminal"].absolute()),
        "--completion-seal",
        str(completion_seal.absolute()),
        "--manager-epoch-tool",
        str(MANAGER_TOOL.absolute()),
        "--resource-receipt",
        str(paths["resource"].absolute()),
        "--release-token",
        str(paths["release"].absolute()),
        "--terminal",
        str(paths["terminal"].absolute()),
        "--cleanup",
        str(paths["cleanup"].absolute()),
        "--expected-terminal",
        expected_terminal,
    ]
    if purpose == "formal":
        detached_arguments.extend(
            [
                "--formal-admission",
                str(formal_admission_path.absolute()),
                "--formal",
                "--internal-receipt",
                str(paths["formal"] / "internal_formal_receipt.json"),
                "--formula",
                str(paths["formal"] / "formula.opb"),
                "--proof",
                str(paths["formal"] / "roundingsat.proof.pbp"),
                "--veripb",
                str(Path(authority["binaries"]["veripb"]["path"])),
            ]
        )
    detached_arguments.extend(["--output", str(paths["detached"].absolute())])
    detached_command = _run_verifier(authority, detached_arguments)
    detached, detached_identity = _load_json(
        paths["detached"],
        "detached verification",
    )
    expected_status = "VERIFIED" if purpose == "formal" else "PASS"
    if detached.get("status") != expected_status:
        raise AttemptError("detached verifier did not establish expected status")
    return {
        "status": expected_status,
        "purpose": purpose,
        "attempt": attempt,
        "unit": unit,
        "selection": selection_identity,
        "launch": launch_identity,
        "payload_terminal": payload_terminal_identity,
        "preterminal": preterminal_identity,
        "resource_verification": resource_identity,
        "terminal": terminal_identity,
        "cleanup": cleanup_identity,
        "detached": detached_identity,
        "resource_verifier_command": resource_command,
        "detached_verifier_command": detached_command,
        "upper_bound_update_authorized": purpose == "formal",
        "ledger": {
            "upper": [1188, 18] if purpose == "formal" else [1188, 22],
            "lower": "absent",
        },
    }


def _failure_closeout(
    path: Path,
    *,
    attempt: str,
    purpose: str,
    error: BaseException,
) -> None:
    if path.exists() or path.is_symlink():
        return
    selection_created = (path.parent / "selection.json").is_file() and not (path.parent / "selection.json").is_symlink()
    payload = {
        "schema_version": "b1_sidewise_smm3_attempt_failure_v1",
        "status": "FORMAL_AUTHORITY_INCOMPLETE",
        "created_utc": _utc_now(),
        "attempt": attempt,
        "purpose": purpose,
        "error_type": type(error).__name__,
        "error": str(error),
        "selection_created": selection_created,
        "attempt_consumed": selection_created,
        "upper_bound_update_authorized": False,
        "ledger": {"upper": [1188, 22], "lower": "absent"},
        "next_required_task": "CUTS_GATE1_V4_AUTHORITY_COMPLETION",
        "production_certified": False,
    }
    try:
        _write_once(path, _json_bytes(payload))
    except Exception:
        pass


def _emergency_cleanup(unit: str) -> None:
    """Best-effort cleanup of this runner's exact pre-registered unit only."""

    if UNIT_RE.fullmatch(unit) is None:
        return
    for argv in (
        [str(SYSTEMCTL), "--user", "stop", unit],
        [str(SYSTEMCTL), "--user", "reset-failed", unit],
    ):
        try:
            _run(argv, timeout=30)
        except Exception:
            pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--admit-formal", action="store_true")
    modes.add_argument("--publish-closeout", action="store_true")
    parser.add_argument(
        "--authority",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--attempt-dir",
        type=Path,
    )
    parser.add_argument(
        "--attempt",
        choices=(
            "synthetic-success-a001",
            "synthetic-postseal-fail-a001",
            "a002",
        ),
    )
    parser.add_argument(
        "--purpose",
        choices=(
            "synthetic_success",
            "synthetic_postseal_failure",
            "formal",
        ),
    )
    parser.add_argument("--unit")
    parser.add_argument("--synthetic-success", type=Path)
    parser.add_argument("--synthetic-postseal-failure", type=Path)
    parser.add_argument("--formal-admission", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.publish_closeout:
        if (
            args.result is None
            or args.output is None
            or any(
                value is not None
                for value in (
                    args.attempt_dir,
                    args.attempt,
                    args.purpose,
                    args.unit,
                    args.synthetic_success,
                    args.synthetic_postseal_failure,
                    args.formal_admission,
                )
            )
        ):
            print(
                json.dumps(
                    {
                        "status": "FAIL_CLOSED",
                        "error": "recovery closeout arguments are incomplete or mixed",
                        "upper_bound_update_authorized": False,
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
        try:
            result = _publish_recovery_closeout(
                authority_path=args.authority.absolute(),
                result_path=args.result.absolute(),
                output=args.output.absolute(),
            )
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "status": "FORMAL_AUTHORITY_INCOMPLETE",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "upper_bound_update_authorized": False,
                        "ledger": {"upper": [1188, 22], "lower": "absent"},
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
        print(json.dumps(result, sort_keys=True))
        return 0
    if args.admit_formal:
        if (
            args.synthetic_success is None
            or args.synthetic_postseal_failure is None
            or args.output is None
            or any(
                value is not None
                for value in (
                    args.attempt_dir,
                    args.attempt,
                    args.purpose,
                    args.unit,
                    args.formal_admission,
                    args.result,
                )
            )
        ):
            print(
                json.dumps(
                    {
                        "status": "FAIL_CLOSED",
                        "error": "formal admission arguments are incomplete or mixed",
                        "upper_bound_update_authorized": False,
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
        try:
            result = _publish_formal_admission(
                authority_path=args.authority.absolute(),
                success_path=args.synthetic_success.absolute(),
                failure_path=args.synthetic_postseal_failure.absolute(),
                output=args.output.absolute(),
            )
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "status": "FORMAL_AUTHORITY_INCOMPLETE",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "formal_attempt_selected": False,
                        "upper_bound_update_authorized": False,
                        "ledger": {"upper": [1188, 22], "lower": "absent"},
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
        print(json.dumps(result, sort_keys=True))
        return 0
    if (
        args.attempt_dir is None
        or args.attempt is None
        or args.purpose is None
        or args.unit is None
        or args.synthetic_success is not None
        or args.synthetic_postseal_failure is not None
        or args.output is not None
        or args.result is not None
    ):
        print(
            json.dumps(
                {
                    "status": "FAIL_CLOSED",
                    "error": "attempt arguments are incomplete or mixed",
                    "upper_bound_update_authorized": False,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    try:
        result = _launch_attempt(
            authority_path=args.authority.absolute(),
            attempt_dir=args.attempt_dir.absolute(),
            attempt=args.attempt,
            purpose=args.purpose,
            unit=args.unit,
            formal_admission_path=(None if args.formal_admission is None else args.formal_admission.absolute()),
        )
    except Exception as exc:
        _emergency_cleanup(args.unit)
        _failure_closeout(
            args.attempt_dir / "attempt-failure.json",
            attempt=args.attempt,
            purpose=args.purpose,
            error=exc,
        )
        print(
            json.dumps(
                {
                    "status": "FORMAL_AUTHORITY_INCOMPLETE",
                    "attempt": args.attempt,
                    "purpose": args.purpose,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "upper_bound_update_authorized": False,
                    "ledger": {"upper": [1188, 22], "lower": "absent"},
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
