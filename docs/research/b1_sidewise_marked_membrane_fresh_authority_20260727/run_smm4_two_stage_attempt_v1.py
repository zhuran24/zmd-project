#!/usr/bin/env python3
"""Drive one SMM4 two-stage synthetic or formal transient-unit attempt.

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
import fcntl
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


AUTHORITY_SCHEMA = "b1_sidewise_smm4_pre_run_authority_v1"
SELECTION_SCHEMA = "b1_sidewise_smm4_attempt_selection_v1"
LAUNCH_SCHEMA = "b1_sidewise_smm4_launch_receipt_v1"
PRETERMINAL_SCHEMA = "b1_sidewise_smm4_preterminal_resource_v1"
TERMINAL_SCHEMA = "b1_sidewise_smm4_terminal_envelope_v1"
CLEANUP_SCHEMA = "b1_sidewise_smm4_cleanup_v1"
START_TOKEN_SCHEMA = "b1_sidewise_smm4_payload_start_token_v1"
RELEASE_TOKEN_SCHEMA = "b1_sidewise_smm4_release_token_v1"
FORMAL_ADMISSION_SCHEMA = "b1_sidewise_smm4_formal_admission_v1"
RECOVERY_CLOSEOUT_SCHEMA = "b1_sidewise_smm4_recovery_closeout_v1"
FAILURE_TERMINAL_SCHEMA = "b1_sidewise_smm4_failure_terminal_v1"
FAILURE_CLEANUP_SCHEMA = "b1_sidewise_smm4_failure_cleanup_v1"
ATTEMPT_FAILURE_SCHEMA = "b1_sidewise_smm4_postselection_failure_v1"
DETACHED_FAILURE_SCHEMA = "b1_sidewise_smm4_detached_failure_closeout_v1"

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = Path(__file__).resolve().parent
ORCHESTRATOR = RESEARCH / "run_smm4_authority_recovery_v1.py"
LEGACY_RESEARCH = RESEARCH.parent / "b1_sidewise_marked_membrane_authority_recovery_20260724"
MANAGER_TOOL = LEGACY_RESEARCH / "manager_epoch_authority_v1.py"
FORMAL_PAYLOAD = RESEARCH / "run_smm4_formal_payload_v1.py"
VERIFIER = RESEARCH / "verify_smm4_two_stage_v1.py"
IDENTITY_CONTRACT = RESEARCH / "identity_contract_v1.py"
AUTHORITY_PACKAGE = RESEARCH / "authority_package_v1.py"
COMPOSITION_VERIFIER = RESEARCH / "verify_smm4_composition_v1.py"
FIXED_PYTHON = Path("/home/zhuran24/.local/share/uv/python/cpython-3.13.13-linux-x86_64-gnu/bin/python3.13")
SYSTEMD_RUN = Path("/usr/bin/systemd-run")
SYSTEMCTL = Path("/usr/bin/systemctl")
FORMAL_ATTEMPT = "smm4-formal-a004"
FORMAL_ATTEMPT_DIR = "formal-attempt-a004"
FORMAL_OUTPUT_DIR = "formal-a004"
ATTEMPT_FAILURE_NAME = "attempt-failure.json"
PRESELECTION_DIR = "preselection-a001"
HEAVY_LOCK = Path("/tmp/zmd-pj-codex-heavy-validation.lock")
PROD_SCALE_LOCKS = (
    Path(f"/run/user/{os.getuid()}/zmd_pj_prod_scale_solver.lock"),
    Path(f"/run/user/{os.getuid()}/zmd-pj-prod-scale-solve.lock"),
)

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

UNIT_RE = re.compile(r"b1-smm4-[a-z0-9-]{8,80}\.service\Z")
INVOCATION_RE = re.compile(r"[0-9a-f]{32}\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
FULL_IDENTITY_FIELDS = (
    "path",
    "size_bytes",
    "sha256",
    "mode_octal",
    "device",
    "inode",
    "link_count",
)

_ACTIVE_IDENTITY_CONTRACT: ModuleType | None = None

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
    "import hashlib,json,os,stat,sys\n"
    "p=sys.argv[1];e=json.loads(sys.argv[2]);a=sys.argv[3:]\n"
    "k={'path','size_bytes','sha256','mode_octal','device','inode','link_count'}\n"
    "if type(e) is not dict or set(e)!=k or e.get('path')!=p: raise SystemExit(125)\n"
    "if not os.path.isabs(p) or os.path.realpath(p)!=p: raise SystemExit(125)\n"
    "f=os.open(p,os.O_RDONLY|getattr(os,'O_CLOEXEC',0)|getattr(os,'O_NOFOLLOW',0))\n"
    "try:\n"
    " s=os.fstat(f);r=b''\n"
    " while True:\n"
    "  b=os.read(f,1048576)\n"
    "  if not b: break\n"
    "  r+=b\n"
    " t=os.fstat(f)\n"
    "finally:\n"
    " os.close(f)\n"
    "q=('st_dev','st_ino','st_mode','st_nlink','st_uid','st_gid','st_size','st_mtime_ns','st_ctime_ns')\n"
    "v={'path':p,'size_bytes':len(r),'sha256':hashlib.sha256(r).hexdigest(),"
    "'mode_octal':format(stat.S_IMODE(s.st_mode),'04o'),'device':s.st_dev,"
    "'inode':s.st_ino,'link_count':s.st_nlink}\n"
    "if (not stat.S_ISREG(s.st_mode) or tuple(getattr(s,x) for x in q)!="
    "tuple(getattr(t,x) for x in q) or v!=e or s.st_nlink!=1): raise SystemExit(125)\n"
    "sys.argv=[p]+a\n"
    "g={'__name__':'__main__','__file__':p,'__package__':None,'__cached__':None}\n"
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
    if not path.is_absolute():
        raise AttemptError(f"{label}: path is not absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise AttemptError(f"{label}: cannot resolve: {exc}") from exc
    if path != resolved:
        raise AttemptError(f"{label}: path is not canonical or traverses a symlink")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(resolved, flags)
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
    contract = _ACTIVE_IDENTITY_CONTRACT
    if contract is None:
        raise AttemptError(f"{label}: shared identity contract is not active")
    try:
        expected_full = contract.validate_full_identity(
            expected,
            f"{label} expected identity",
        )
        expected_projection = contract.canonical_content_projection(
            expected_full,
            f"{label} expected identity",
        )
        contract.assert_identity_join(
            expected_full,
            expected_projection,
            actual,
            label,
        )
    except Exception as exc:
        raise AttemptError(f"{label}: exact identity mismatch: {exc}") from exc


def _bootstrap_full_identity(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(FULL_IDENTITY_FIELDS):
        raise AttemptError(f"{label}: exact full7 identity key set mismatch")
    result = {field: value[field] for field in FULL_IDENTITY_FIELDS}
    path = result["path"]
    if (
        type(path) is not str
        or not os.path.isabs(path)
        or path.startswith("//")
        or os.path.normpath(path) != path
    ):
        raise AttemptError(f"{label}: noncanonical absolute identity path")
    if type(result["size_bytes"]) is not int or result["size_bytes"] < 0:
        raise AttemptError(f"{label}: invalid identity size")
    if type(result["sha256"]) is not str or SHA_RE.fullmatch(result["sha256"]) is None:
        raise AttemptError(f"{label}: invalid identity SHA-256")
    if type(result["mode_octal"]) is not str or re.fullmatch(r"[0-7]{4}", result["mode_octal"]) is None:
        raise AttemptError(f"{label}: invalid identity mode")
    for field, minimum in (("device", 0), ("inode", 1)):
        if type(result[field]) is not int or result[field] < minimum:
            raise AttemptError(f"{label}: invalid identity {field}")
    if type(result["link_count"]) is not int or result["link_count"] != 1:
        raise AttemptError(f"{label}: identity link_count must equal one")
    return result


def _activate_identity_contract(module: ModuleType) -> ModuleType:
    required = (
        "IdentityContractError",
        "validate_full_identity",
        "validate_projection",
        "canonical_content_projection",
        "assert_identity_join",
    )
    if any(not hasattr(module, name) for name in required):
        raise AttemptError("canonical content identity contract API missing")
    global _ACTIVE_IDENTITY_CONTRACT
    _ACTIVE_IDENTITY_CONTRACT = module
    return module


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
        os.fchmod(descriptor, 0o644)
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise AttemptError(f"{path}: output is not a regular file")
        if metadata.st_size != len(raw):
            raise AttemptError(f"{path}: final size mismatch")
        if metadata.st_nlink != 1:
            raise AttemptError(f"{path}: output link_count must equal one")
        if stat.S_IMODE(metadata.st_mode) != 0o644:
            raise AttemptError(f"{path}: output mode is not 0644")
        identity = {
            "path": os.path.abspath(os.fspath(path)),
            "size_bytes": len(raw),
            "sha256": _sha(raw),
            "mode_octal": f"{stat.S_IMODE(metadata.st_mode):04o}",
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "link_count": metadata.st_nlink,
        }
    finally:
        os.close(descriptor)
    validated = _bootstrap_full_identity(identity, f"output {path.name}")
    contract = _ACTIVE_IDENTITY_CONTRACT
    if contract is not None:
        try:
            return contract.validate_full_identity(
                validated,
                f"output {path.name}",
            )
        except Exception as exc:
            raise AttemptError(f"{path}: output identity contract failed: {exc}") from exc
    return validated


def _mkdir_once(path: Path) -> None:
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise AttemptError(f"{path}: directory parent is not real")
    try:
        os.mkdir(path, 0o755)
    except OSError as exc:
        raise AttemptError(f"{path}: cannot create directory: {exc}") from exc
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        os.fchmod(descriptor, 0o755)
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o755:
            raise AttemptError(f"{path}: created directory mode/type mismatch")
    except OSError as exc:
        raise AttemptError(f"{path}: cannot finalize directory: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _acquire_formal_locks() -> list[int]:
    descriptors: list[int] = []
    try:
        for path in (HEAVY_LOCK, *PROD_SCALE_LOCKS):
            if not path.is_absolute() or path.parent.is_symlink() or not path.parent.is_dir():
                raise AttemptError(f"formal lock parent is not a real directory: {path}")
            descriptor = os.open(
                path,
                os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise AttemptError(f"formal lock is not a single-link regular file: {path}")
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                os.close(descriptor)
                raise AttemptError(f"formal lock busy before selection: {path}") from exc
            except Exception:
                os.close(descriptor)
                raise
            descriptors.append(descriptor)
        return descriptors
    except Exception:
        _release_formal_locks(descriptors)
        raise


def _release_formal_locks(descriptors: Sequence[int]) -> None:
    for descriptor in reversed(descriptors):
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_pinned_module(
    path: Path,
    expected: Any,
    label: str,
) -> tuple[ModuleType, dict[str, Any]]:
    raw, identity = _read_regular(path, label)
    _matches(identity, expected, label)
    module = ModuleType(f"_smm4_{path.stem}_{identity['sha256'][:12]}")
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
    package_id: str,
) -> tuple[dict[str, Any], dict[str, Any], ModuleType]:
    identity_raw, identity_observed = _read_regular(
        IDENTITY_CONTRACT,
        "canonical content identity contract",
    )
    identity_module = ModuleType("_smm4_bootstrap_identity_contract")
    identity_module.__file__ = str(IDENTITY_CONTRACT)
    identity_module.__package__ = None
    exec(
        compile(identity_raw, str(IDENTITY_CONTRACT), "exec", dont_inherit=True),
        identity_module.__dict__,
    )
    _activate_identity_contract(identity_module)
    package_raw, package_observed = _read_regular(
        AUTHORITY_PACKAGE,
        "sealed authority package verifier",
    )
    package_module = ModuleType("_smm4_bootstrap_authority_package")
    package_module.__file__ = str(AUTHORITY_PACKAGE)
    package_module.__package__ = None
    previous = sys.modules.get("identity_contract_v1")
    sys.modules["identity_contract_v1"] = identity_module
    try:
        exec(
            compile(package_raw, str(AUTHORITY_PACKAGE), "exec", dont_inherit=True),
            package_module.__dict__,
        )
    finally:
        if previous is None:
            sys.modules.pop("identity_contract_v1", None)
        else:
            sys.modules["identity_contract_v1"] = previous
    try:
        package = package_module.verify_authority_package(
            path.parent,
            package_id,
        )
    except Exception as exc:
        raise AttemptError(f"SMM4 authority package verification failed: {exc}") from exc
    if not isinstance(package, dict) or set(package) != {
        "authority_raw",
        "authority",
        "seal",
        "package_id",
    }:
        raise AttemptError("SMM4 authority package verifier returned malformed output")
    authority_raw = package.get("authority_raw")
    authority_identity = package.get("authority")
    if (
        not isinstance(authority_raw, bytes)
        or not isinstance(authority_identity, dict)
        or authority_identity.get("path") != str(path)
        or package.get("package_id") != package_id
    ):
        raise AttemptError("SMM4 authority package identity drifted")
    authority = _strict_json(authority_raw, "SMM4 sealed authority")
    if not isinstance(authority, dict):
        raise AttemptError("SMM4 sealed authority root is not an object")
    if authority.get("schema_version") != AUTHORITY_SCHEMA or authority.get("status") != "PRE_RUN_AUTHORITY_PASS":
        raise AttemptError("SMM4 authority semantics failed")
    tools = authority.get("tools")
    if not isinstance(tools, dict):
        raise AttemptError("SMM4 authority tools missing")
    _matches(
        identity_observed,
        tools.get("identity_contract"),
        "canonical content identity contract",
    )
    _matches(
        package_observed,
        tools.get("authority_package"),
        "sealed authority package verifier",
    )
    _matches(
        _identity(Path(__file__).resolve(strict=True), "two-stage attempt runner"),
        tools.get("attempt_runner"),
        "two-stage attempt runner",
    )
    orchestrator, _ = _load_pinned_module(
        ORCHESTRATOR,
        tools.get("orchestrator"),
        "SMM4 orchestrator",
    )
    orchestrator.replay_current_toolchain(authority)
    if authority.get("git") != orchestrator.git_snapshot(
        authority.get("implementation_head", ""),
    ):
        raise AttemptError("repository identity drifted from SMM4 authority")
    current_epoch, _ = orchestrator.capture_epoch()
    if not orchestrator.same_epoch(authority.get("manager_epoch", {}), current_epoch):
        raise AttemptError("manager/boot epoch drifted from pre-run authority")
    try:
        orchestrator.replay_manager_epoch_toolchain(authority, current_epoch)
    except Exception as exc:
        raise AttemptError(f"manager epoch toolchain replay failed: {exc}") from exc
    return authority, authority_identity, orchestrator


def _load_identity_contract(authority: Mapping[str, Any]) -> ModuleType:
    tools = authority.get("tools")
    if not isinstance(tools, Mapping):
        raise AttemptError("SMM4 authority tools missing")
    raw, observed = _read_regular(
        IDENTITY_CONTRACT,
        "canonical content identity contract",
    )
    expected = _bootstrap_full_identity(
        tools.get("identity_contract"),
        "canonical content identity contract expected identity",
    )
    actual = _bootstrap_full_identity(
        observed,
        "canonical content identity contract actual identity",
    )
    if actual != expected:
        raise AttemptError("canonical content identity contract drifted")
    module = ModuleType(f"_smm4_{IDENTITY_CONTRACT.stem}_{actual['sha256'][:12]}")
    module.__file__ = actual["path"]
    module.__package__ = None
    try:
        exec(
            compile(raw, actual["path"], "exec", dont_inherit=True),
            module.__dict__,
        )
    except Exception as exc:
        raise AttemptError(
            f"canonical content identity contract pinned execution failed: {exc}"
        ) from exc
    return _activate_identity_contract(module)


def _epoch(
    authority: Mapping[str, Any],
    orchestrator: ModuleType,
    stage: str,
) -> dict[str, Any]:
    current, _ = orchestrator.capture_epoch()
    if not orchestrator.same_epoch(authority.get("manager_epoch", {}), current):
        raise AttemptError(f"manager/boot epoch drifted at {stage}")
    try:
        orchestrator.replay_manager_epoch_toolchain(authority, current)
    except Exception as exc:
        raise AttemptError(
            f"manager epoch toolchain replay drifted at {stage}: {exc}"
        ) from exc
    return current


def _run(
    argv: Sequence[str],
    *,
    timeout: int,
    pass_fds: Sequence[int] = (),
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
            pass_fds=tuple(pass_fds),
        )
    except subprocess.TimeoutExpired as exc:
        raise AttemptError(f"command timed out: {list(argv)!r}") from exc
    return {
        "argv": list(argv),
        "exit_code": completed.returncode,
        "stdout": completed.stdout.decode("utf-8", "backslashreplace"),
        "stderr": completed.stderr.decode("utf-8", "backslashreplace"),
    }


def _run_authority_binary(
    authority: Mapping[str, Any],
    name: str,
    expected_path: Path,
    arguments: Sequence[str],
    *,
    timeout: int,
) -> dict[str, Any]:
    """Read, validate, and execute one authority binary through the same FD."""

    binaries = authority.get("binaries")
    if not isinstance(binaries, Mapping):
        raise AttemptError("authority binaries mapping missing")
    expected = _bootstrap_full_identity(
        binaries.get(name),
        f"authority binary {name}",
    )
    if expected["path"] != str(expected_path.absolute()):
        raise AttemptError(f"authority binary {name} path is not canonical")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(expected["path"], flags)
    except OSError as exc:
        raise AttemptError(f"authority binary {name}: cannot retain executable: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise AttemptError(f"authority binary {name}: not a single-link regular file")
        chunks: list[bytes] = []
        offset = 0
        while offset < before.st_size:
            block = os.pread(descriptor, min(1024 * 1024, before.st_size - offset), offset)
            if not block:
                raise AttemptError(f"authority binary {name}: short retained-FD read")
            chunks.append(block)
            offset += len(block)
        raw = b"".join(chunks)
        observed = {
            "path": expected["path"],
            "size_bytes": len(raw),
            "sha256": _sha(raw),
            "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
            "device": before.st_dev,
            "inode": before.st_ino,
            "link_count": before.st_nlink,
        }
        if _bootstrap_full_identity(observed, f"authority binary {name} observed") != expected:
            raise AttemptError(f"authority binary {name}: retained identity drifted")
        logical_argv = [expected["path"], *arguments]
        executed_argv = [f"/proc/self/fd/{descriptor}", *arguments]
        record = _run(
            executed_argv,
            timeout=timeout,
            pass_fds=(descriptor,),
        )
        after = os.fstat(descriptor)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if tuple(getattr(before, field) for field in stable_fields) != tuple(
            getattr(after, field) for field in stable_fields
        ):
            raise AttemptError(f"authority binary {name}: changed during retained-FD execution")
        executed_record_argv = record.pop("argv")
        record["argv"] = logical_argv
        record["logical_argv"] = logical_argv
        record["executed_argv"] = executed_record_argv
        record["executable"] = expected
        record["transport"] = "retained_proc_self_fd"
        record["executed_from_retained_fd"] = True
        record["same_fd_stable_before_after"] = True
        return record
    finally:
        os.close(descriptor)


def _systemctl_show(
    authority: Mapping[str, Any],
    unit: str,
    fields: Sequence[str],
) -> tuple[dict[str, str], dict[str, Any]]:
    arguments = [
        "--user",
        "show",
        unit,
        "--no-pager",
        *[f"--property={field}" for field in fields],
    ]
    record = _run_authority_binary(
        authority,
        "systemctl",
        SYSTEMCTL,
        arguments,
        timeout=15,
    )
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
    authority: Mapping[str, Any],
    unit: str,
    predicate: Any,
    fields: Sequence[str],
    timeout: int,
) -> tuple[dict[str, str], dict[str, Any]]:
    deadline = time.monotonic() + timeout
    last: tuple[dict[str, str], dict[str, Any]] | None = None
    while time.monotonic() < deadline:
        current = _systemctl_show(authority, unit, fields)
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
    identity = _bootstrap_full_identity(
        dict(script_identity),
        "pinned source loader script identity",
    )
    return [
        python_path,
        "-I",
        "-c",
        PINNED_SOURCE_LOADER,
        str(script_path.absolute()),
        json.dumps(
            identity,
            sort_keys=True,
            separators=(",", ":"),
        ),
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
    authority_package_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload, identity = _load_json(path, f"{expected_terminal} detached receipt")
    validation = payload.get("validation")
    if not isinstance(validation, dict):
        raise AttemptError("synthetic detached receipt lacks validation")
    if (
        payload.get("status") != "PASS"
        or payload.get("mode") != "detached"
        or payload.get("authority_package_id") != authority_package_id
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
    authority_package_id: str,
    success_path: Path,
    failure_path: Path,
    output: Path,
) -> dict[str, Any]:
    authority, authority_identity, orchestrator = _load_authority(
        authority_path,
        authority_package_id,
    )
    run_dir = ROOT / authority["run"]
    if (
        output.parent != run_dir
        or success_path != run_dir / "synthetic-success-a001/detached-verification.json"
        or failure_path != run_dir / "synthetic-postseal-fail-a001/detached-verification.json"
    ):
        raise AttemptError("formal admission paths are not canonical")
    _, success_identity = _validate_synthetic_detached(
        success_path,
        "success",
        authority_package_id,
    )
    _, failure_identity = _validate_synthetic_detached(
        failure_path,
        "postseal-failure",
        authority_package_id,
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
            "--authority-package-id",
            authority_package_id,
            "--selection",
            str(attempt_root / "selection.json"),
            "--payload-spec",
            str(_attempt_paths(attempt_root)["payload_spec"]),
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
            authority_package_id,
        )
    if (run_dir / FORMAL_ATTEMPT_DIR).exists():
        raise AttemptError("formal SMM4 a004 attempt already exists")
    try:
        old_upper_replay = orchestrator.replay_old_upper(authority)
        composition_replay = orchestrator.replay_composition(authority)
    except Exception as exc:
        raise AttemptError(f"formal composition admission replay failed: {exc}") from exc
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
        "authority_package_id": authority_package_id,
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
        "old_upper_replay": old_upper_replay,
        "composition_replay": composition_replay,
        "historical_inputs_replayed_by_authority": True,
        "formal_attempt": FORMAL_ATTEMPT,
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
    authority_package_id: str,
    orchestrator: ModuleType,
    attempt_dir: Path,
) -> dict[str, Any]:
    admission, admission_identity = _load_json(path, "formal admission")
    if (
        admission.get("schema_version") != FORMAL_ADMISSION_SCHEMA
        or admission.get("status") != "FORMAL_ADMISSION_PASS"
        or admission.get("run_nonce") != authority["run_nonce"]
        or admission.get("authority_package_id") != authority_package_id
        or admission.get("formal_attempt") != FORMAL_ATTEMPT
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
            authority_package_id,
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
            authority_package_id,
        )
        _matches(
            replay_identity,
            replay_identities.get(label),
            f"formal admission replay {label}",
        )
    if attempt_dir != run_dir / FORMAL_ATTEMPT_DIR:
        raise AttemptError("formal SMM4 a004 directory is not canonical")
    try:
        old_upper_replay = orchestrator.replay_old_upper(authority)
        composition_replay = orchestrator.replay_composition(authority)
    except Exception as exc:
        raise AttemptError(f"formal pre-selection composition replay failed: {exc}") from exc
    if (
        admission.get("old_upper_replay") != old_upper_replay
        or admission.get("composition_replay") != composition_replay
    ):
        raise AttemptError("formal admission composition closure drifted")
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
    authority_package_id: str,
    result_path: Path,
    output: Path,
) -> dict[str, Any]:
    authority, authority_identity, orchestrator = _load_authority(
        authority_path,
        authority_package_id,
    )
    run_dir = ROOT / authority["run"]
    if output != run_dir / "closeout-a001.json":
        raise AttemptError("recovery closeout path is not canonical")
    canonical_success = run_dir / FORMAL_ATTEMPT_DIR / "detached-verification.json"
    canonical_failure = run_dir / FORMAL_ATTEMPT_DIR / ATTEMPT_FAILURE_NAME
    canonical_detached_failure = (
        run_dir / FORMAL_ATTEMPT_DIR / "detached-failure-verification.json"
    )
    detached_failure_state: dict[str, Any] | None = None
    if result_path == canonical_success:
        result, result_identity = _load_json(result_path, "formal detached result")
        inputs = result.get("inputs")
        if (
            result.get("schema_version") != "b1_sidewise_smm4_detached_closeout_v1"
            or result.get("status") != "VERIFIED"
            or result.get("authority_package_id") != authority_package_id
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
    elif result_path == canonical_detached_failure:
        result, result_identity = _load_json(
            result_path,
            "formal detached failure result",
        )
        failure_inputs = result.get("inputs")
        if (
            result.get("schema_version") != DETACHED_FAILURE_SCHEMA
            or result.get("status") != "VERIFIED_FAIL_CLOSED"
            or result.get("authority_package_id") != authority_package_id
            or result.get("attempt") != FORMAL_ATTEMPT
            or result.get("attempt_consumed") is not True
            or result.get("retry_authorized") is not False
            or result.get("upper_bound_update_authorized") is not False
            or result.get("ledger") != {"upper": [1188, 22], "lower": "absent"}
            or result.get("production_certified") is not False
            or not isinstance(failure_inputs, Mapping)
        ):
            raise AttemptError("formal detached failure result semantics failed")
        _matches(
            authority_identity,
            failure_inputs.get("authority"),
            "formal detached failure authority",
        )
        if not orchestrator.same_epoch(
            authority["manager_epoch"],
            result.get("manager_epoch", {}),
        ):
            raise AttemptError("formal detached failure manager/boot epoch drifted")
        detached_failure_state = {
            "status": "VERIFIED_FAIL_CLOSED",
            "receipt": result_identity,
        }
        status = "FORMAL_AUTHORITY_INCOMPLETE"
        ledger = {"upper": [1188, 22], "lower": "absent"}
        update_authorized = False
    elif result_path == canonical_failure:
        result, result_identity = _load_json(result_path, "formal attempt failure")
        if (
            result.get("schema_version") != ATTEMPT_FAILURE_SCHEMA
            or result.get("status") != "FORMAL_AUTHORITY_INCOMPLETE"
            or result.get("attempt") != FORMAL_ATTEMPT
            or result.get("purpose") != "formal"
            or result.get("selection_created") is not True
            or result.get("attempt_consumed") is not True
            or result.get("retry_authorized") is not False
            or result.get("detached_failure_expected_path")
            != str(canonical_detached_failure)
            or result.get("upper_bound_update_authorized") is not False
            or result.get("ledger") != {"upper": [1188, 22], "lower": "absent"}
        ):
            raise AttemptError("formal attempt failure semantics failed")
        detached_failure_state = {
            "status": "DETACHED_FAILURE_NOT_VERIFIED",
            "expected_path": str(canonical_detached_failure),
            "present": canonical_detached_failure.is_file()
            and not canonical_detached_failure.is_symlink(),
        }
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
        "authority_package_id": authority_package_id,
        "result": result_identity,
        "detached_failure": detached_failure_state,
        "formal_attempt": f"{FORMAL_ATTEMPT}_consumed_no_retry",
        "upper_bound_update_authorized": update_authorized,
        "ledger": ledger,
        "next_required_task": "AB16_GATE_B_AND_16_ORGANIC_ARMS",
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
        "next_required_task": "AB16_GATE_B_AND_16_ORGANIC_ARMS",
    }


def _publish_selection(
    *,
    authority: Mapping[str, Any],
    authority_identity: Mapping[str, Any],
    authority_package_id: str,
    orchestrator: ModuleType,
    path: Path,
    attempt: str,
    purpose: str,
    unit: str,
    worker_argv: list[str],
    payload_spec_identity: Mapping[str, Any],
    formal_admission: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = _load_identity_contract(authority)
    try:
        full_identity = contract.validate_full_identity(
            authority_identity,
            "selection authority full identity",
        )
        content_identity = contract.canonical_content_projection(
            full_identity,
            "selection authority full identity",
        )
    except Exception as exc:
        raise AttemptError(f"selection authority identity contract failed: {exc}") from exc
    before = _epoch(authority, orchestrator, f"{attempt} pre-selection")
    selection = {
        "schema_version": SELECTION_SCHEMA,
        "status": "SELECTED_CONSUMED",
        "created_utc": _utc_now(),
        "attempt": attempt,
        "purpose": purpose,
        "run_nonce": authority["run_nonce"],
        "unit": unit,
        "authority": full_identity,
        "authority_content_identity": content_identity,
        "authority_package_id": authority_package_id,
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
        FORMAL_ATTEMPT: "formal",
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
        # Payload specifications are deterministic, immutable preselection
        # inputs.  Keeping them outside the canonical attempt directory lets
        # selection.json be the first immutable attempt object.
        "payload_spec": attempt_dir.parent / PRESELECTION_DIR / f"{attempt_dir.name}-payload-spec.json",
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
        "failure_terminal": attempt_dir / "failure-terminal.json",
        "failure_cleanup": attempt_dir / "failure-cleanup.json",
        "failure_detached": attempt_dir / "detached-failure-verification.json",
        "attempt_failure": attempt_dir / ATTEMPT_FAILURE_NAME,
        "seal": attempt_dir / "state/payload-seal.json",
        "formal": attempt_dir / FORMAL_OUTPUT_DIR,
    }


def _ensure_real_directory(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise AttemptError(f"{label}: not a real directory")
    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o755:
            raise AttemptError(f"{label}: directory mode/type mismatch")
    except OSError as exc:
        raise AttemptError(f"{label}: cannot retain directory: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _prepare_preselection_root(path: Path) -> None:
    if path.exists() or path.is_symlink():
        _ensure_real_directory(path, "preselection root")
    else:
        _mkdir_once(path)
    allowed = {
        "synthetic-success-a001-payload-spec.json",
        "synthetic-postseal-fail-a001-payload-spec.json",
        f"{FORMAL_ATTEMPT_DIR}-payload-spec.json",
    }
    for entry in path.iterdir():
        if entry.name not in allowed or entry.is_symlink() or not entry.is_file():
            raise AttemptError(
                f"preselection root contains unexpected member {entry.name!r}"
            )


def _write_or_reuse_exact(path: Path, raw: bytes, label: str) -> dict[str, Any]:
    """Publish immutable preselection bytes, or reuse only the exact bytes."""

    if path.exists() or path.is_symlink():
        observed_raw, observed_identity = _read_regular(path, label)
        if (
            observed_raw != raw
            or observed_identity["mode_octal"] != "0644"
            or observed_identity["link_count"] != 1
        ):
            raise AttemptError(f"{label}: existing immutable bytes differ")
        return observed_identity
    return _write_once(path, raw)


def _prepare_unconsumed_attempt_dir(path: Path) -> None:
    """Create, or safely resume, the empty directory before selection.

    A crash between mkdir and the O_EXCL selection write has not consumed the
    attempt.  Only that exact empty topology may be resumed; any file, symlink,
    or subdirectory is fail-closed.
    """

    if not (path.exists() or path.is_symlink()):
        _mkdir_once(path)
        return
    _ensure_real_directory(path, "unconsumed attempt directory")
    entries = list(path.iterdir())
    if entries:
        raise AttemptError(
            "attempt directory exists without a reusable empty preselection topology"
        )


def _detached_authority_result(
    detached: Mapping[str, Any],
    purpose: str,
    authority_package_id: str,
) -> tuple[bool, dict[str, Any]]:
    expected_status = "VERIFIED" if purpose == "formal" else "PASS"
    expected_update = purpose == "formal"
    expected_ledger = {
        "upper": [1188, 18] if expected_update else [1188, 22],
        "lower": "absent",
    }
    if (
        detached.get("status") != expected_status
        or detached.get("authority_package_id") != authority_package_id
        or detached.get("upper_bound_update_authorized") is not expected_update
        or detached.get("ledger") != expected_ledger
    ):
        raise AttemptError("detached verifier did not establish exact expected authority")
    return expected_update, expected_ledger


def _build_payload(
    *,
    authority: Mapping[str, Any],
    authority_path: Path,
    authority_package_id: str,
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
            "--authority-package-id",
            authority_package_id,
            "--selection",
            str(selection_path.absolute()),
            "--output-dir",
            str((attempt_dir / FORMAL_OUTPUT_DIR).absolute()),
            "--expected-systemd-unit",
            unit,
        ]
        executed = _make_loader_argv(
            python_path,
            FORMAL_PAYLOAD,
            tools["formal_payload"],
            logical[1:],
        )
        completion_seal = attempt_dir / FORMAL_OUTPUT_DIR / "internal_formal_receipt.json"
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
    authority_package_id: str,
    attempt_dir: Path,
    attempt: str,
    purpose: str,
    unit: str,
    formal_admission_path: Path | None,
) -> dict[str, Any]:
    _validate_attempt_name(attempt, purpose)
    if not UNIT_RE.fullmatch(unit):
        raise AttemptError("unit name is not canonical")
    authority, authority_identity, orchestrator = _load_authority(
        authority_path,
        authority_package_id,
    )
    paths = _attempt_paths(attempt_dir)
    expected_dir_name = {
        "synthetic_success": "synthetic-success-a001",
        "synthetic_postseal_failure": "synthetic-postseal-fail-a001",
        "formal": FORMAL_ATTEMPT_DIR,
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
            authority_package_id=authority_package_id,
            orchestrator=orchestrator,
            attempt_dir=attempt_dir,
        )
    elif formal_admission_path is not None:
        raise AttemptError("synthetic attempt cannot consume formal admission")
    logical_worker, executed_worker, completion_seal = _build_payload(
        authority=authority,
        authority_path=authority_path,
        authority_package_id=authority_package_id,
        selection_path=paths["selection"],
        attempt_dir=attempt_dir,
        attempt=attempt,
        purpose=purpose,
        unit=unit,
    )
    payload_spec = {
        "schema_version": "b1_sidewise_smm4_payload_spec_v1",
        "run_nonce": authority["run_nonce"],
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "authority": authority_identity,
        "authority_package_id": authority_package_id,
        "manager_epoch": authority["manager_epoch"],
        "argv": executed_worker,
        "logical_worker_argv": logical_worker,
        "completion_seal": str(completion_seal.absolute()),
        "resource_contract": _resource_contract(authority),
        "timing_contract": _timing_contract(purpose),
    }
    _prepare_preselection_root(attempt_dir.parent / PRESELECTION_DIR)
    payload_spec_identity = _write_or_reuse_exact(
        paths["payload_spec"],
        _json_bytes(payload_spec),
        f"{attempt} immutable preselection payload spec",
    )
    _prepare_unconsumed_attempt_dir(attempt_dir)
    _, selection_identity = _publish_selection(
        authority=authority,
        authority_identity=authority_identity,
        authority_package_id=authority_package_id,
        orchestrator=orchestrator,
        path=paths["selection"],
        attempt=attempt,
        purpose=purpose,
        unit=unit,
        worker_argv=logical_worker,
        payload_spec_identity=payload_spec_identity,
        formal_admission=formal_admission_identity,
    )
    # The selection is now the first immutable object in the canonical
    # attempt directory and is the sole consumption boundary.
    _mkdir_once(attempt_dir / "state")

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
    launch_command = _run_authority_binary(
        authority,
        "systemd_run",
        SYSTEMD_RUN,
        systemd_argv[1:],
        timeout=30,
    )
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
        authority,
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
        authority,
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
        "--authority-package-id",
        authority_package_id,
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
        authority,
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

    stop_record = _run_authority_binary(
        authority,
        "systemctl",
        SYSTEMCTL,
        ["--user", "stop", unit],
        timeout=30,
    )
    reset_record = _run_authority_binary(
        authority,
        "systemctl",
        SYSTEMCTL,
        ["--user", "reset-failed", unit],
        timeout=30,
    )
    deadline = time.monotonic() + 30
    load_state_record: dict[str, Any] | None = None
    unit_absent = False
    while time.monotonic() < deadline:
        load_state_record = _run_authority_binary(
            authority,
            "systemctl",
            SYSTEMCTL,
            [
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
        "--authority-package-id",
        authority_package_id,
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
        if formal_admission_path is None:
            raise AttemptError("formal detached verification lacks admission path")
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
    detached_update, detached_ledger = _detached_authority_result(
        detached,
        purpose,
        authority_package_id,
    )
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
        "upper_bound_update_authorized": detached_update,
        "ledger": detached_ledger,
    }


def _emergency_cleanup(authority: Mapping[str, Any], unit: str) -> list[dict[str, Any]]:
    """Best-effort cleanup of this runner's exact pre-registered unit only."""

    if UNIT_RE.fullmatch(unit) is None:
        return []
    records: list[dict[str, Any]] = []
    for arguments in (
        ["--user", "stop", unit],
        ["--user", "reset-failed", unit],
    ):
        try:
            records.append(
                _run_authority_binary(
                    authority,
                    "systemctl",
                    SYSTEMCTL,
                    arguments,
                    timeout=30,
                )
            )
        except Exception as exc:
            records.append(
                {
                    "logical_argv": [str(SYSTEMCTL), *arguments],
                    "status": "FAIL_CLOSED",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    return records


def _run_last_resort_systemctl(
    arguments: Sequence[str],
    *,
    timeout: int,
) -> dict[str, Any]:
    """Execute the fixed host systemctl from its retained FD without authority.

    This is cleanup-only and can never feed an authorizing receipt.  It exists
    for the case where the authority package/tool/epoch replay itself is the
    post-selection failure and therefore cannot be trusted to clean its unit.
    """

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(SYSTEMCTL, flags)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != 0
            or before.st_nlink != 1
            or stat.S_IMODE(before.st_mode) & 0o111 == 0
        ):
            raise AttemptError("last-resort systemctl is not a root-owned executable")
        digest = hashlib.sha256()
        offset = 0
        while offset < before.st_size:
            block = os.pread(descriptor, min(1024 * 1024, before.st_size - offset), offset)
            if not block:
                raise AttemptError("last-resort systemctl short retained-FD read")
            digest.update(block)
            offset += len(block)
        logical_argv = [str(SYSTEMCTL), *arguments]
        executed_argv = [f"/proc/self/fd/{descriptor}", *arguments]
        record = _run(
            executed_argv,
            timeout=timeout,
            pass_fds=(descriptor,),
        )
        after = os.fstat(descriptor)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if tuple(getattr(before, field) for field in stable_fields) != tuple(
            getattr(after, field) for field in stable_fields
        ):
            raise AttemptError("last-resort systemctl changed during retained-FD execution")
        record["executed_argv"] = record.pop("argv")
        record["logical_argv"] = logical_argv
        record["executable_sha256"] = digest.hexdigest()
        record["transport"] = "retained_proc_self_fd_cleanup_only"
        record["authority_bound"] = False
        record["upper_bound_update_authorized"] = False
        return record
    finally:
        os.close(descriptor)


def _last_resort_cleanup(unit: str) -> list[dict[str, Any]]:
    if UNIT_RE.fullmatch(unit) is None:
        return []
    records: list[dict[str, Any]] = []
    for arguments in (
        ["--user", "stop", unit],
        ["--user", "reset-failed", unit],
        ["--user", "show", unit, "--property=LoadState", "--value"],
    ):
        try:
            records.append(
                _run_last_resort_systemctl(
                    arguments,
                    timeout=30,
                )
            )
        except Exception as exc:
            records.append(
                {
                    "logical_argv": [str(SYSTEMCTL), *arguments],
                    "status": "FAIL_CLOSED",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "authority_bound": False,
                    "upper_bound_update_authorized": False,
                }
            )
    return records


def _load_or_write_failure_record(
    path: Path,
    payload: Mapping[str, Any],
    label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reuse an immutable closeout prefix, or append exactly one new record."""

    if path.exists() or path.is_symlink():
        return _load_json(path, label)
    identity = _write_once(path, _json_bytes(payload))
    return dict(payload), identity


def _failure_process_seed(
    paths: Mapping[str, Path],
) -> tuple[dict[str, int], str | None, dict[str, dict[str, Any]]]:
    pid_starttimes: dict[str, int] = {}
    cgroup_path: str | None = None
    observed: dict[str, dict[str, Any]] = {}
    if paths["launch"].is_file() and not paths["launch"].is_symlink():
        launch, launch_identity = _load_json(paths["launch"], "failure launch prefix")
        observed["launch"] = launch_identity
        starttimes = launch.get("pid_starttimes")
        if isinstance(starttimes, Mapping):
            for raw_pid, raw_starttime in starttimes.items():
                if (
                    isinstance(raw_pid, str)
                    and raw_pid.isdecimal()
                    and type(raw_starttime) is int
                    and raw_starttime > 0
                ):
                    pid_starttimes[raw_pid] = raw_starttime
        candidate_cgroup = launch.get("initial_cgroup_path")
        if isinstance(candidate_cgroup, str) and candidate_cgroup.startswith("/sys/fs/cgroup/"):
            cgroup_path = candidate_cgroup
    supervisor_path = paths["selection"].parent / "state/supervisor-start.json"
    if supervisor_path.is_file() and not supervisor_path.is_symlink():
        supervisor, supervisor_identity = _load_json(
            supervisor_path,
            "failure supervisor-start prefix",
        )
        observed["supervisor_start"] = supervisor_identity
        for field in ("supervisor_pid", "payload_pid"):
            pid = supervisor.get(field)
            if type(pid) is not int or pid <= 0 or str(pid) in pid_starttimes:
                continue
            try:
                pid_starttimes[str(pid)] = _pid_starttime(pid)
            except AttemptError:
                # It is already absent; cleanup records the checked PID with no
                # surviving start-time identity.
                continue
    return pid_starttimes, cgroup_path, observed


def _failure_unit_observation(
    authority: Mapping[str, Any],
    unit: str,
) -> dict[str, Any]:
    try:
        return _run_authority_binary(
            authority,
            "systemctl",
            SYSTEMCTL,
            [
                "--user",
                "show",
                unit,
                "--no-pager",
                "--property=LoadState",
                "--property=ActiveState",
                "--property=SubState",
                "--property=Result",
                "--property=MainPID",
                "--property=InvocationID",
                "--property=ControlGroup",
            ],
            timeout=15,
        )
    except Exception as exc:
        return {
            "status": "FAIL_CLOSED",
            "logical_argv": [str(SYSTEMCTL), "--user", "show", unit],
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _failure_observed_cgroup(record: Mapping[str, Any]) -> str | None:
    stdout = record.get("stdout")
    if not isinstance(stdout, str):
        return None
    values: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            return None
        name, value = line.split("=", 1)
        if name in values:
            return None
        values[name] = value
    control_group = values.get("ControlGroup")
    if not control_group:
        return None
    if not control_group.startswith("/") or ".." in control_group.split("/"):
        return None
    return str(Path("/sys/fs/cgroup") / control_group.lstrip("/"))


def _failure_absence_observation(
    authority: Mapping[str, Any],
    unit: str,
    pid_starttimes: Mapping[str, int],
    cgroup_path: str | None,
) -> dict[str, Any]:
    deadline = time.monotonic() + 30
    load_state_record: dict[str, Any] | None = None
    unit_absent = False
    while time.monotonic() < deadline:
        try:
            load_state_record = _run_authority_binary(
                authority,
                "systemctl",
                SYSTEMCTL,
                [
                    "--user",
                    "show",
                    unit,
                    "--property=LoadState",
                    "--value",
                ],
                timeout=10,
            )
        except Exception as exc:
            load_state_record = {
                "status": "FAIL_CLOSED",
                "logical_argv": [
                    str(SYSTEMCTL),
                    "--user",
                    "show",
                    unit,
                    "--property=LoadState",
                    "--value",
                ],
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            break
        if load_state_record["exit_code"] == 0 and load_state_record["stdout"] == "not-found\n":
            unit_absent = True
            break
        time.sleep(0.1)
    checked_pids = sorted(int(raw_pid) for raw_pid in pid_starttimes)
    remaining_pids = [
        pid
        for pid in checked_pids
        if _same_pid_remains(pid, pid_starttimes[str(pid)])
    ]
    cgroup_absent = cgroup_path is None or not Path(cgroup_path).exists()
    return {
        "load_state": load_state_record,
        "unit_absent": unit_absent,
        "checked_pids": checked_pids,
        "pid_starttimes": dict(pid_starttimes),
        "remaining_pids": remaining_pids,
        "cgroup_path": cgroup_path,
        "cgroup_absent": cgroup_absent,
        "absence_verified": (
            unit_absent
            and not remaining_pids
            and cgroup_absent
        ),
    }


def _close_postselection_failure(
    *,
    authority_path: Path,
    authority_package_id: str,
    attempt_dir: Path,
    attempt: str,
    purpose: str,
    unit: str,
    error: BaseException,
) -> Path | None:
    """Append terminal/cleanup/detached evidence after selection, never retry."""

    paths = _attempt_paths(attempt_dir)
    if not paths["selection"].is_file() or paths["selection"].is_symlink():
        # Before selection the attempt is unconsumed.  Do not create any
        # canonical attempt file; an exact empty directory may be resumed.
        return None
    authority, authority_identity, orchestrator = _load_authority(
        authority_path,
        authority_package_id,
    )
    selection, selection_identity = _load_json(
        paths["selection"],
        "postselection failure selection",
    )
    if (
        selection.get("status") != "SELECTED_CONSUMED"
        or selection.get("attempt") != attempt
        or selection.get("purpose") != purpose
        or selection.get("unit") != unit
        or selection.get("authority_package_id") != authority_package_id
        or selection.get("upper_bound_update_authorized") is not False
    ):
        raise AttemptError("postselection failure selection semantics drifted")
    payload_spec, payload_spec_identity = _load_json(
        paths["payload_spec"],
        "postselection failure payload spec",
    )
    _matches(payload_spec_identity, selection.get("payload_spec"), "failure selection payload spec")
    completion_seal_value = payload_spec.get("completion_seal")
    if not isinstance(completion_seal_value, str) or not os.path.isabs(completion_seal_value):
        raise AttemptError("postselection failure completion seal path is invalid")
    completion_seal_path = Path(completion_seal_value)
    seal_present = completion_seal_path.is_file() and not completion_seal_path.is_symlink()
    pid_starttimes, cgroup_path, observed_prefix = _failure_process_seed(paths)
    systemd_before_cleanup = _failure_unit_observation(authority, unit)
    if cgroup_path is None:
        cgroup_path = _failure_observed_cgroup(systemd_before_cleanup)
    terminal_payload = {
        "schema_version": FAILURE_TERMINAL_SCHEMA,
        "status": "FAILURE_TERMINAL_CAPTURED",
        "created_utc": _utc_now(),
        "run_nonce": authority["run_nonce"],
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "manager_epoch": _epoch(authority, orchestrator, f"{attempt} failure terminal"),
        "authority": authority_identity,
        "authority_package_id": authority_package_id,
        "selection": selection_identity,
        "payload_spec": payload_spec_identity,
        "observed_prefix": observed_prefix,
        "pid_starttimes": pid_starttimes,
        "cgroup_path": cgroup_path,
        "completion_seal_path": str(completion_seal_path),
        "completion_seal_present": seal_present,
        "systemd_before_cleanup": systemd_before_cleanup,
        "error_type": type(error).__name__,
        "error": str(error),
        "upper_bound_update_authorized": False,
        "ledger": {"upper": [1188, 22], "lower": "absent"},
        "production_certified": False,
    }
    terminal, terminal_identity = _load_or_write_failure_record(
        paths["failure_terminal"],
        terminal_payload,
        "postselection failure terminal",
    )
    cleanup_records = _emergency_cleanup(authority, unit)
    absence = _failure_absence_observation(
        authority,
        unit,
        terminal.get("pid_starttimes", {}),
        terminal.get("cgroup_path"),
    )
    cleanup_payload = {
        "schema_version": FAILURE_CLEANUP_SCHEMA,
        "status": "FAILURE_CLEANUP_CAPTURED",
        "created_utc": _utc_now(),
        "run_nonce": authority["run_nonce"],
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "manager_epoch": _epoch(authority, orchestrator, f"{attempt} failure cleanup"),
        "authority": authority_identity,
        "authority_package_id": authority_package_id,
        "selection": selection_identity,
        "failure_terminal": terminal_identity,
        "cleanup_commands": cleanup_records,
        **absence,
        "upper_bound_update_authorized": False,
        "ledger": {"upper": [1188, 22], "lower": "absent"},
        "production_certified": False,
    }
    cleanup, cleanup_identity = _load_or_write_failure_record(
        paths["failure_cleanup"],
        cleanup_payload,
        "postselection failure cleanup",
    )
    failure_payload = {
        "schema_version": ATTEMPT_FAILURE_SCHEMA,
        "status": "FORMAL_AUTHORITY_INCOMPLETE",
        "created_utc": _utc_now(),
        "run_nonce": authority["run_nonce"],
        "attempt": attempt,
        "purpose": purpose,
        "unit": unit,
        "authority": authority_identity,
        "authority_package_id": authority_package_id,
        "selection": selection_identity,
        "failure_terminal": terminal_identity,
        "failure_cleanup": cleanup_identity,
        "completion_seal_present": terminal.get("completion_seal_present"),
        "absence_verified": cleanup.get("absence_verified"),
        "error_type": type(error).__name__,
        "error": str(error),
        "selection_created": True,
        "attempt_consumed": True,
        "retry_authorized": False,
        "detached_failure_expected_path": str(paths["failure_detached"].absolute()),
        "upper_bound_update_authorized": False,
        "ledger": {"upper": [1188, 22], "lower": "absent"},
        "next_required_task": "AB16_GATE_B_AND_16_ORGANIC_ARMS",
        "production_certified": False,
    }
    _, failure_identity = _load_or_write_failure_record(
        paths["attempt_failure"],
        failure_payload,
        "postselection attempt failure",
    )
    if not (paths["failure_detached"].exists() or paths["failure_detached"].is_symlink()):
        failure_arguments = [
            "detached-failure",
            "--authority",
            str(authority_path.absolute()),
            "--authority-package-id",
            authority_package_id,
            "--selection",
            str(paths["selection"].absolute()),
            "--payload-spec",
            str(paths["payload_spec"].absolute()),
            "--failure-terminal",
            str(paths["failure_terminal"].absolute()),
            "--failure-cleanup",
            str(paths["failure_cleanup"].absolute()),
            "--attempt-failure",
            str(paths["attempt_failure"].absolute()),
            "--manager-epoch-tool",
            str(MANAGER_TOOL.absolute()),
            "--output",
            str(paths["failure_detached"].absolute()),
        ]
        try:
            _run_verifier(authority, failure_arguments)
        except Exception:
            # The verifier writes its own immutable FAIL_CLOSED receipt when
            # possible.  The caller will freeze the attempt against the bare
            # failure receipt if detached validation did not complete.
            pass
    if paths["failure_detached"].is_file() and not paths["failure_detached"].is_symlink():
        detached, _ = _load_json(paths["failure_detached"], "detached failure verification")
        if (
            detached.get("schema_version") == DETACHED_FAILURE_SCHEMA
            and detached.get("status") == "VERIFIED_FAIL_CLOSED"
            and detached.get("upper_bound_update_authorized") is False
            and detached.get("ledger") == {"upper": [1188, 22], "lower": "absent"}
        ):
            return paths["failure_detached"]
    # Explicit fallback: the immutable failure record names the missing or
    # failed detached path, and no authorization is possible.
    _matches(
        failure_identity,
        _identity(paths["attempt_failure"], "postselection failure fallback"),
        "postselection failure fallback",
    )
    return paths["attempt_failure"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--admit-formal", action="store_true")
    parser.add_argument(
        "--authority",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--authority-package-id",
        required=True,
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
            FORMAL_ATTEMPT,
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
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
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
                authority_package_id=args.authority_package_id,
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
    formal_locks: list[int] = []
    try:
        if args.purpose == "formal":
            formal_locks = _acquire_formal_locks()
        result = _launch_attempt(
            authority_path=args.authority.absolute(),
            authority_package_id=args.authority_package_id,
            attempt_dir=args.attempt_dir.absolute(),
            attempt=args.attempt,
            purpose=args.purpose,
            unit=args.unit,
            formal_admission_path=(None if args.formal_admission is None else args.formal_admission.absolute()),
        )
        if args.purpose == "formal":
            closeout = _publish_recovery_closeout(
                authority_path=args.authority.absolute(),
                authority_package_id=args.authority_package_id,
                result_path=(args.attempt_dir / "detached-verification.json").absolute(),
                output=(args.attempt_dir.parent / "closeout-a001.json").absolute(),
            )
            result["closeout"] = closeout
    except Exception as exc:
        failure_result: Path | None = None
        failure_evidence_error: BaseException | None = None
        last_resort_cleanup: list[dict[str, Any]] | None = None
        try:
            failure_result = _close_postselection_failure(
                authority_path=args.authority.absolute(),
                authority_package_id=args.authority_package_id,
                attempt_dir=args.attempt_dir.absolute(),
                attempt=args.attempt,
                purpose=args.purpose,
                unit=args.unit,
                error=exc,
            )
        except Exception as closeout_exc:
            failure_evidence_error = closeout_exc
            last_resort_cleanup = _last_resort_cleanup(args.unit)
        if args.purpose == "formal" and failure_result is not None:
            try:
                _publish_recovery_closeout(
                    authority_path=args.authority.absolute(),
                    authority_package_id=args.authority_package_id,
                    result_path=failure_result.absolute(),
                    output=(args.attempt_dir.parent / "closeout-a001.json").absolute(),
                )
            except Exception:
                pass
        print(
            json.dumps(
                {
                    "status": "FORMAL_AUTHORITY_INCOMPLETE",
                    "attempt": args.attempt,
                    "purpose": args.purpose,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "failure_evidence_error": (
                        None
                        if failure_evidence_error is None
                        else {
                            "error_type": type(failure_evidence_error).__name__,
                            "error": str(failure_evidence_error),
                        }
                    ),
                    "last_resort_cleanup": last_resort_cleanup,
                    "attempt_consumed": failure_result is not None
                    or (
                        (args.attempt_dir / "selection.json").is_file()
                        and not (args.attempt_dir / "selection.json").is_symlink()
                    ),
                    "upper_bound_update_authorized": False,
                    "ledger": {"upper": [1188, 22], "lower": "absent"},
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    finally:
        _release_formal_locks(formal_locks)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
