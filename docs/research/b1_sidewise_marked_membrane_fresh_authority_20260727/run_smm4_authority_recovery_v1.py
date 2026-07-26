#!/usr/bin/env python3
"""Fail-closed SMM4 authority bootstrap and two-stage unit supervisor.

The operational modes in this file deliberately keep the formal payload
separate from the unit lifecycle.  A payload is first held inside the target
cgroup, then reaped by the main supervisor.  The supervisor remains as the
sole keeper until an external resource verifier publishes a release token.

No manager executable fallback exists.  If the pinned manager-epoch helper
cannot open the actual ``/proc/<pid>/exe`` bytes, bootstrap records an
incomplete result before any synthetic unit or formal selection is created.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
from types import ModuleType
from typing import Any


BASE_HEAD = "e03bc98dbb00fb38d941e471c61879c499b33213"
SCHEMA = "b1_sidewise_smm4_pre_run_authority_v1"
SELECTION_SCHEMA = "b1_sidewise_smm4_attempt_selection_v1"
SUPERVISOR_SCHEMA = "b1_sidewise_smm4_supervisor_state_v1"
PAYLOAD_TERMINAL_SCHEMA = "b1_sidewise_smm4_payload_terminal_v1"
TOKEN_SCHEMA = "b1_sidewise_smm4_release_token_v1"

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = Path(__file__).resolve().parent
SMM4_ARTIFACT_ROOT = ROOT / ".artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727"
FIXED_PYTHON = Path("/home/zhuran24/.local/share/uv/python/cpython-3.13.13-linux-x86_64-gnu/bin/python3.13")
ROUNDINGSAT = Path("/home/zhuran24/tools/roundingsat/build/roundingsat")
VERIPB = Path("/home/zhuran24/.cargo/bin/veripb")
SYSTEMD_RUN = Path("/usr/bin/systemd-run")
SYSTEMCTL = Path("/usr/bin/systemctl")
BUSCTL = Path("/usr/bin/busctl")
SUDO = Path("/usr/bin/sudo")
PRIVILEGED_PYTHON = Path("/usr/bin/python3.14")

LEGACY_RESEARCH = RESEARCH.parent / "b1_sidewise_marked_membrane_authority_recovery_20260724"
MANAGER_TOOL = LEGACY_RESEARCH / "manager_epoch_authority_v1.py"
PRIVILEGED_ATTESTOR = LEGACY_RESEARCH / "privileged_manager_exe_attestor_v1.py"
ATTEMPT_RUNNER = RESEARCH / "run_smm4_two_stage_attempt_v1.py"
FORMAL_PAYLOAD = RESEARCH / "run_smm4_formal_payload_v1.py"
INDEPENDENT_VERIFIER = RESEARCH / "verify_smm4_two_stage_v1.py"
IDENTITY_CONTRACT = RESEARCH / "identity_contract_v1.py"
AUTHORITY_PACKAGE = RESEARCH / "authority_package_v1.py"
COMPOSITION_VERIFIER = RESEARCH / "verify_smm4_composition_v1.py"
OLD_UPPER_VERIFIER = RESEARCH / "verify_smm4_old_upper_v1.py"
RESUME_AUTHORITY_TOOL = (
    RESEARCH.parent
    / "b1_sidewise_marked_membrane_strict_20260724"
    / "resume_authority_v1.py"
)
TRANSLATION_GATE = (
    RESEARCH.parent / "b1_sidewise_marked_membrane_strict_20260724" / "verify_ceiling_exclusion_translation_v1.py"
)

MEMORY_HIGH = 35 * 1024**3
MEMORY_MAX = 39 * 1024**3
MEMORY_SWAP_MAX = 16 * 1024**3
PROOF_LIMIT = 5_000_000_000
LOW_WATER = 10 * 1024**3
REQUIRED_FREE = LOW_WATER + PROOF_LIMIT

RUN_RE = re.compile(r"run-[0-9]{8}T[0-9]{6}Z-SMM4-[A-Za-z0-9_-]{4,16}\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")

BUILD_FILES = (
    "formula.opb",
    "variable_map.json",
    "encoder.meta.json",
    "build_record.json",
    "estimate.json",
    "SHA256SUMS",
)
BUILD_FILE_ANCHORS: dict[str, tuple[int, str, str]] = {
    "formula.opb": (
        283,
        "d4b79cd76c80d23e509ad09b1d2e7fa02fa337049f40459ab803f0fc55a4d865",
        "0644",
    ),
    "variable_map.json": (
        1152,
        "f02e948739ee63a0e6b74c7a7cae5dc0015211c111c17621bb0d3951cb6c0cce",
        "0644",
    ),
    "encoder.meta.json": (
        2525,
        "74a2f3377f530ff81926c4c61b7cbb86325cb2665504e144e2811c3ac076eaeb",
        "0644",
    ),
    "build_record.json": (
        2161,
        "351e4e360a50cb31ee85a31ad3e02e690678b600d91b8303c8fae7eee13d9297",
        "0644",
    ),
    "estimate.json": (
        2269,
        "873aa754cceff6b457e3698e2cf31ef43f4bf4935ed9f17f5ab046d7fddd45b5",
        "0644",
    ),
    "SHA256SUMS": (
        410,
        "aca5bb1bdacc3d044f12c3b4dae9b903b936c607686e9ecadf834ea0a28e4c2c",
        "0644",
    ),
}
COMPOSITION_INPUT_NAMES = (
    "old_r4_receipt",
    "geometry_admission",
    "strict_instance",
    "formula",
    "variable_map",
)
OLD_R4_FORMAL_MEMBERS: dict[str, tuple[int, str, str]] = {
    "build_authority.SHA256SUMS": (
        942,
        "652a7bdf5bab1488e40fa1bce6eab18e59437f038acef0d7b3f39b197c74771a",
        "0644",
    ),
    "build_authority.record.json": (
        11982,
        "4f8124c582d0c4134538abd2574f2f2ebb3fb5eeb56f0aba7fb1d760fc72f886",
        "0644",
    ),
    "encoder.meta.json": (
        15390,
        "f304342bd6b1ac51b8be5dc0c4c6d439dfde06b667fec3c8fd7928f714d73c3d",
        "0644",
    ),
    "estimate.json": (
        13231,
        "0a8bdfd6a3b38e9aa4085942788240087a7db335d05583447a7d02004521786b",
        "0644",
    ),
    "formal_attempt.reservation.json": (
        2682,
        "9710e9bb99cd82562791a2d6f66319356bca7eaf028299933a23571a65df0ab6",
        "0644",
    ),
    "formula.opb": (
        56881,
        "9ce8f110757ecf87af888ed7fd2fbc334eecaf2e1a9be784a8a1b5dc8f3435d8",
        "0644",
    ),
    "resource_monitor.jsonl": (
        6773,
        "cb241cffe7b79d57b9d2d6f3f89e1e5b632f5e459d224986d8280c48e8c4e2c5",
        "0600",
    ),
    "roundingsat.proof.pbp": (
        39446,
        "54c4b9c61f7a4505808e8cad895c863ca8579400e3df83e7e7c8d269d0504531",
        "0644",
    ),
    "roundingsat.stderr.txt": (
        0,
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "0644",
    ),
    "roundingsat.stdout.txt": (
        2371,
        "fc741e3db09b4297f880d6ebfc24bca9b1b045c0137cca9950d91c41303d01d1",
        "0644",
    ),
    "toolchain_started.json": (
        39128,
        "a1b35570ceb8740cecaedae4099df0f9a3bc659829c53593cb6bebde395f6e2e",
        "0644",
    ),
    "translation_gate.json": (
        10332,
        "0146770cdad317f80523f6d05e4a59997209a28b2cb657e844fd458e8af79602",
        "0644",
    ),
    "translation_gate.recheck.json": (
        10332,
        "0146770cdad317f80523f6d05e4a59997209a28b2cb657e844fd458e8af79602",
        "0644",
    ),
    "translation_gate.recheck.stderr.txt": (
        0,
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "0644",
    ),
    "translation_gate.recheck.stdout.txt": (
        208,
        "2d2a61e2138147b711500a31ae4774d9008eef82f11ec5876b56206c2a17a8c2",
        "0644",
    ),
    "variable_map.json": (
        967694,
        "877fe9ee63e96bb616761b8c1719fde40d5fe14a9eaf852adce747275830c028",
        "0644",
    ),
    "veripb.stderr.txt": (
        0,
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "0644",
    ),
    "veripb.stdout.txt": (
        183,
        "e99277368076972906e135c4a443a361b6ddbdaa5c596a1118326d6b2776c09f",
        "0644",
    ),
    "veripb.version.stderr.txt": (
        0,
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "0644",
    ),
    "veripb.version.stdout.txt": (
        42,
        "179a3be6a120ee0f76ec97355197e605b3a7217584d3c344af9949d0248a4e86",
        "0644",
    ),
}


def old_r4_member_key(filename: str) -> str:
    return "old_r4_member_" + filename.replace(".", "_").replace("-", "_")


OLD_UPPER_INPUT_NAMES = (
    "old_r4_receipt",
    "old_r4_toolchain_record",
    "old_r4_raw_manifest",
    *(old_r4_member_key(name) for name in OLD_R4_FORMAL_MEMBERS),
    "old_r4_a004_admission",
    "strict_instance",
)


class RecoveryError(RuntimeError):
    """A provenance, lifecycle, or no-overwrite failure."""


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def strict_json(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise RecoveryError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise RecoveryError(f"{label}: non-integer JSON number {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryError(f"{label}: malformed JSON: {exc}") from exc


def read_regular(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    if not path.is_absolute():
        raise RecoveryError(f"{label}: path is not absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RecoveryError(f"{label}: cannot resolve: {exc}") from exc
    if path != resolved:
        raise RecoveryError(f"{label}: path is not canonical or traverses a symlink")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(resolved, flags)
    except OSError as exc:
        raise RecoveryError(f"{label}: cannot open: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RecoveryError(f"{label}: not a regular file")
        chunks: list[bytes] = []
        while True:
            block = os.read(descriptor, 1 << 20)
            if not block:
                break
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    fields_before = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_nlink,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    fields_after = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_nlink,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if fields_before != fields_after:
        raise RecoveryError(f"{label}: changed during same-fd read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise RecoveryError(f"{label}: short read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
        "device": before.st_dev,
        "inode": before.st_ino,
        "link_count": before.st_nlink,
    }


def identity(path: Path, label: str) -> dict[str, Any]:
    return read_regular(path, label)[1]


def load_json(path: Path, label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, record = read_regular(path, label)
    value = strict_json(raw, label)
    if not isinstance(value, dict):
        raise RecoveryError(f"{label}: root is not an object")
    return value, record


def identity_matches(
    actual: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> bool:
    return all(
        actual.get(field) == expected.get(field)
        for field in (
            "path",
            "size_bytes",
            "sha256",
            "mode_octal",
            "device",
            "inode",
            "link_count",
        )
    )


def write_once(path: Path, raw: bytes, mode: int = 0o644) -> dict[str, Any]:
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise RecoveryError(f"output parent is not a real directory: {path.parent}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, mode)
    except OSError as exc:
        raise RecoveryError(f"cannot create output {path}: {exc}") from exc
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(descriptor, raw[offset:])
            if written <= 0:
                raise RecoveryError(f"short write: {path}")
            offset += written
        os.fchmod(descriptor, mode)
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise RecoveryError(f"output is not a regular file: {path}")
        if metadata.st_size != len(raw):
            raise RecoveryError(f"output size mismatch: {path}")
        if metadata.st_nlink != 1:
            raise RecoveryError(f"output link count is not one: {path}")
        if stat.S_IMODE(metadata.st_mode) != mode:
            raise RecoveryError(f"output mode mismatch: {path}")
        result = {
            "path": os.path.abspath(os.fspath(path)),
            "size_bytes": len(raw),
            "sha256": sha(raw),
            "mode_octal": f"{stat.S_IMODE(metadata.st_mode):04o}",
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "link_count": metadata.st_nlink,
        }
    finally:
        os.close(descriptor)
    return result


def mkdir_once(path: Path) -> None:
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise RecoveryError(f"directory parent is not real: {path.parent}")
    try:
        os.mkdir(path, 0o755)
    except OSError as exc:
        raise RecoveryError(f"cannot create no-overwrite directory {path}: {exc}") from exc
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
            raise RecoveryError(f"created directory mode/type mismatch: {path}")
    except OSError as exc:
        raise RecoveryError(f"cannot finalize no-overwrite directory {path}: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run_record(
    argv: Sequence[str],
    *,
    timeout: int = 30,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    completed = subprocess.run(
        list(argv),
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env=None if env is None else dict(env),
    )
    return {
        "argv": list(argv),
        "exit_code": completed.returncode,
        "stdout": completed.stdout.decode("utf-8", "backslashreplace"),
        "stderr": completed.stderr.decode("utf-8", "backslashreplace"),
    }


def executable_identity(path: Path, label: str) -> dict[str, Any]:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RecoveryError(f"{label}: cannot resolve: {exc}") from exc
    return {
        "path": str(path.absolute()),
        "resolved_path": str(resolved),
        "target": identity(resolved, f"{label} target"),
    }


def current_toolchain_snapshot() -> dict[str, dict[str, Any]]:
    """Recompute every tool identity admitted by the SMM4 authority."""

    tools = {
        "orchestrator": identity(Path(__file__), "orchestrator"),
        "manager_epoch": identity(MANAGER_TOOL, "manager epoch tool"),
        "privileged_attestor": identity(
            PRIVILEGED_ATTESTOR,
            "privileged manager executable attestor",
        ),
        "attempt_runner": identity(
            ATTEMPT_RUNNER,
            "two-stage attempt runner",
        ),
        "formal_payload": identity(FORMAL_PAYLOAD, "formal payload"),
        "independent_verifier": identity(
            INDEPENDENT_VERIFIER,
            "independent verifier",
        ),
        "identity_contract": identity(
            IDENTITY_CONTRACT,
            "canonical content identity contract",
        ),
        "authority_package": identity(
            AUTHORITY_PACKAGE,
            "sealed authority package verifier",
        ),
        "composition_verifier": identity(
            COMPOSITION_VERIFIER,
            "SMM4 composition verifier",
        ),
        "old_upper_verifier": identity(
            OLD_UPPER_VERIFIER,
            "SMM4 frozen old-upper verifier",
        ),
        "resume_authority": identity(
            RESUME_AUTHORITY_TOOL,
            "SMM2 resume authority tool",
        ),
        "translation_gate": identity(
            TRANSLATION_GATE,
            "translation tool",
        ),
    }
    binaries = {
        "fixed_python": executable_identity(FIXED_PYTHON, "fixed Python"),
        "roundingsat": identity(ROUNDINGSAT, "RoundingSat"),
        "veripb": identity(VERIPB, "VeriPB"),
        "systemd_run": identity(SYSTEMD_RUN, "systemd-run"),
        "systemctl": identity(SYSTEMCTL, "systemctl"),
        "busctl": identity(BUSCTL, "busctl"),
        "sudo": executable_identity(SUDO, "sudo"),
        "privileged_python": executable_identity(
            PRIVILEGED_PYTHON,
            "privileged attestor Python",
        ),
    }
    return {
        "tools": tools,
        "binaries": binaries,
    }


def replay_current_toolchain(
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    """Fail closed unless the entire current toolchain equals authority."""

    current = current_toolchain_snapshot()
    for group in ("tools", "binaries"):
        expected_group = authority.get(group)
        actual_group = current[group]
        if not isinstance(expected_group, Mapping):
            raise RecoveryError(f"SMM4 authority lacks {group} toolchain mapping")
        if set(expected_group) != set(actual_group):
            raise RecoveryError(f"SMM4 authority {group} key set drifted")
        for name, actual in actual_group.items():
            if expected_group.get(name) != actual:
                raise RecoveryError(f"SMM4 authority {group}.{name} identity drifted")
    return {
        "schema_version": "b1_sidewise_smm4_current_toolchain_replay_v1",
        "status": "CURRENT_TOOLCHAIN_REPLAY_PASS",
        "tools": current["tools"],
        "binaries": current["binaries"],
    }


def load_module_from_bytes(path: Path, label: str) -> tuple[ModuleType, dict[str, Any]]:
    raw, record = read_regular(path, label)
    module_name = f"_smm4_{path.stem}_{record['sha256'][:12]}"
    module = ModuleType(module_name)
    module.__file__ = str(path)
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        code = compile(raw, str(path), "exec")
        exec(code, module.__dict__)
    except Exception as exc:
        raise RecoveryError(f"{label}: cannot execute pinned bytes: {exc}") from exc
    finally:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
    return module, record


def identity_contract() -> ModuleType:
    module, _ = load_module_from_bytes(
        IDENTITY_CONTRACT,
        "canonical content identity contract",
    )
    required = (
        "IdentityContractError",
        "validate_full_identity",
        "canonical_content_projection",
        "assert_identity_join",
    )
    if any(not hasattr(module, name) for name in required):
        raise RecoveryError("canonical content identity contract API missing")
    return module


def _load_authority_package_verifier(
    expected_tools: Mapping[str, Any] | None = None,
) -> tuple[ModuleType, dict[str, Any]]:
    identity_module, identity_record = load_module_from_bytes(
        IDENTITY_CONTRACT,
        "canonical content identity contract",
    )
    if (
        expected_tools is not None
        and identity_record != expected_tools.get("identity_contract")
    ):
        raise RecoveryError("canonical content identity contract drifted")
    previous = sys.modules.get("identity_contract_v1")
    sys.modules["identity_contract_v1"] = identity_module
    try:
        module, module_record = load_module_from_bytes(
            AUTHORITY_PACKAGE,
            "sealed authority package verifier",
        )
    finally:
        if previous is None:
            sys.modules.pop("identity_contract_v1", None)
        else:
            sys.modules["identity_contract_v1"] = previous
    if (
        expected_tools is not None
        and module_record != expected_tools.get("authority_package")
    ):
        raise RecoveryError("sealed authority package verifier drifted")
    return module, module_record


def verify_authority_package(
    authority_path: Path,
    package_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if authority_path.name != "authority.json":
        raise RecoveryError("SMM4 authority filename is not canonical")
    module, _ = _load_authority_package_verifier()
    try:
        package = module.verify_authority_package(
            authority_path.parent,
            package_id,
        )
    except Exception as exc:
        raise RecoveryError(f"SMM4 authority package verification failed: {exc}") from exc
    if not isinstance(package, dict) or set(package) != {
        "authority_raw",
        "authority",
        "seal",
        "package_id",
    }:
        raise RecoveryError("SMM4 authority package verifier returned malformed output")
    raw = package.get("authority_raw")
    authority_identity = package.get("authority")
    seal_identity = package.get("seal")
    if (
        not isinstance(raw, bytes)
        or not isinstance(authority_identity, dict)
        or not isinstance(seal_identity, dict)
        or authority_identity.get("path") != str(authority_path)
        or package.get("package_id") != package_id
    ):
        raise RecoveryError("SMM4 authority package output identity drifted")
    authority = strict_json(raw, "SMM4 sealed authority")
    if not isinstance(authority, dict):
        raise RecoveryError("SMM4 sealed authority root is not an object")
    tools = authority.get("tools")
    if not isinstance(tools, Mapping):
        raise RecoveryError("SMM4 sealed authority tool set missing")
    _load_authority_package_verifier(tools)
    return authority, authority_identity, seal_identity


def _load_composition_verifier(
    expected_tools: Mapping[str, Any],
) -> ModuleType:
    identity_module, identity_record = load_module_from_bytes(
        IDENTITY_CONTRACT,
        "canonical content identity contract",
    )
    if identity_record != expected_tools.get("identity_contract"):
        raise RecoveryError("canonical content identity contract drifted")
    previous = sys.modules.get("identity_contract_v1")
    sys.modules["identity_contract_v1"] = identity_module
    try:
        module, module_record = load_module_from_bytes(
            COMPOSITION_VERIFIER,
            "SMM4 composition verifier",
        )
    finally:
        if previous is None:
            sys.modules.pop("identity_contract_v1", None)
        else:
            sys.modules["identity_contract_v1"] = previous
    if module_record != expected_tools.get("composition_verifier"):
        raise RecoveryError("SMM4 composition verifier drifted")
    return module


def _load_old_upper_verifier(
    expected_tools: Mapping[str, Any],
) -> ModuleType:
    identity_module, identity_record = load_module_from_bytes(
        IDENTITY_CONTRACT,
        "canonical content identity contract",
    )
    if identity_record != expected_tools.get("identity_contract"):
        raise RecoveryError("canonical content identity contract drifted")
    previous = sys.modules.get("identity_contract_v1")
    sys.modules["identity_contract_v1"] = identity_module
    try:
        module, module_record = load_module_from_bytes(
            OLD_UPPER_VERIFIER,
            "SMM4 frozen old-upper verifier",
        )
    finally:
        if previous is None:
            sys.modules.pop("identity_contract_v1", None)
        else:
            sys.modules["identity_contract_v1"] = previous
    if module_record != expected_tools.get("old_upper_verifier"):
        raise RecoveryError("SMM4 frozen old-upper verifier drifted")
    return module


def _old_upper_pins(
    inputs: Mapping[str, Any],
    module: ModuleType,
) -> tuple[dict[str, Path], dict[str, dict[str, Any]]]:
    required = getattr(module, "REQUIRED_INPUT_KEYS", None)
    if tuple(required or ()) != OLD_UPPER_INPUT_NAMES:
        raise RecoveryError("SMM4 frozen old-upper input-key contract drifted")
    contract = identity_contract()
    snapshot_paths: dict[str, Path] = {}
    pinned_inputs: dict[str, dict[str, Any]] = {}
    for name in OLD_UPPER_INPUT_NAMES:
        expected = inputs.get(name)
        if not isinstance(expected, Mapping):
            raise RecoveryError(f"old-upper snapshot {name} identity missing")
        try:
            full_identity = contract.validate_full_identity(
                dict(expected),
                f"old-upper snapshot {name}",
            )
            projection = contract.canonical_content_projection(
                full_identity,
                f"old-upper snapshot {name}",
            )
        except Exception as exc:
            raise RecoveryError(
                f"old-upper snapshot {name} identity contract failed: {exc}"
            ) from exc
        snapshot_paths[name] = Path(full_identity["path"])
        pinned_inputs[name] = {
            "identity": full_identity,
            "content_projection": projection,
        }
    return snapshot_paths, pinned_inputs


def _replay_old_upper_from_authority_parts(
    inputs: Mapping[str, Any],
    expected_tools: Mapping[str, Any],
    expected_binaries: Mapping[str, Any],
    *,
    verifier_timeout_seconds: int = 300,
) -> dict[str, Any]:
    module = _load_old_upper_verifier(expected_tools)
    snapshot_paths, pinned_inputs = _old_upper_pins(inputs, module)
    veripb = expected_binaries.get("veripb")
    if not isinstance(veripb, Mapping):
        raise RecoveryError("authority VeriPB identity missing")
    try:
        replay = module.verify_old_upper(
            snapshot_paths,
            pinned_inputs,
            Path(str(veripb.get("path"))),
            dict(veripb),
            verifier_timeout_seconds=verifier_timeout_seconds,
        )
    except Exception as exc:
        raise RecoveryError(f"fresh-snapshot old-upper replay failed: {exc}") from exc
    graph = replay.get("receipt_and_manifest_graph") if isinstance(replay, dict) else None
    claim = replay.get("claim_boundary") if isinstance(replay, dict) else None
    if (
        not isinstance(replay, dict)
        or replay.get("schema_version") != "b1_smm4_old_upper_snapshot_verification_v1"
        or replay.get("status") != "PASS"
        or replay.get("decision")
        != "OLD_R4_COMPLETE_BAND_AUTHORITY_RECOVERED_FROM_FRESH_SNAPSHOTS"
        or replay.get("upper_bound_update_authorized") is not False
        or replay.get("inputs") != pinned_inputs
        or not isinstance(graph, Mapping)
        or graph.get("historical_receipt_upper_bound_update_authorized") is not True
        or not isinstance(claim, Mapping)
        or claim.get("ledger_upper_remains") != [1188, 22]
        or claim.get("lower_remains") != "absent"
        or claim.get("production_certified") is not False
    ):
        raise RecoveryError("fresh-snapshot old-upper replay semantics drifted")
    return replay


def capture_epoch() -> tuple[dict[str, Any], dict[str, Any]]:
    module, tool = load_module_from_bytes(MANAGER_TOOL, "manager epoch tool")
    try:
        epoch = module.capture_manager_epoch()
    except Exception as exc:
        raise RecoveryError(f"manager/boot epoch capture failed; no cmdline fallback is permitted: {exc}") from exc
    if not isinstance(epoch, dict):
        raise RecoveryError("manager epoch helper returned a non-object")
    return epoch, tool


def same_epoch(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    module, _ = load_module_from_bytes(MANAGER_TOOL, "manager epoch tool")
    return bool(module.same_epoch(left, right))


def git_snapshot(expected_head: str) -> dict[str, Any]:
    def git(*argv: str) -> bytes:
        run = subprocess.run(
            ["git", "-C", str(ROOT), *argv],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return run.stdout

    head = git("rev-parse", "HEAD").decode("ascii").strip()
    if head != expected_head:
        raise RecoveryError(f"implementation HEAD drifted: {head} != {expected_head}")
    ancestor = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", BASE_HEAD, head],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if ancestor.returncode != 0:
        raise RecoveryError("implementation HEAD does not descend from fixed base HEAD")
    exclusions = (
        ":(exclude).artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727/**",
    )
    diff = git(
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "HEAD",
        "--",
        ".",
        *exclusions,
    )
    status_bytes = git(
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=normal",
        "--",
        ".",
        *exclusions,
    )
    if diff or status_bytes:
        raise RecoveryError("implementation worktree is not exactly clean")
    return {
        "head": head,
        "base_head": BASE_HEAD,
        "tracked_diff_size_bytes": len(diff),
        "tracked_diff_sha256": sha(diff),
        "status_size_bytes": len(status_bytes),
        "status_sha256": sha(status_bytes),
        "excluded_paths": [
            ".artifacts/track_b_b1_sidewise_marked_membrane_fresh_authority_20260727/**",
        ],
    }


def canonical_source_dir(path: Path, label: str) -> Path:
    if not path.is_absolute():
        raise RecoveryError(f"{label}: source root is not absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise RecoveryError(f"{label}: cannot resolve source root: {exc}") from exc
    if path != resolved or not resolved.is_dir() or resolved.is_symlink():
        raise RecoveryError(f"{label}: source root is not a canonical real directory")
    return resolved


def validate_expected_inputs(
    *,
    source_root: Path,
    smm2_run: Path,
    smm3_run: Path,
) -> dict[str, Any]:
    source_root = canonical_source_dir(source_root, "R4 source root")
    smm2_run = canonical_source_dir(smm2_run, "SMM2 source root")
    smm3_run = canonical_source_dir(smm3_run, "SMM3 source root")
    strict_instance = (
        source_root
        / "docs/research/cleanroom_rederivation_20260718"
        / "strict/external/problem_instance.json"
    )
    old_r4_formal = (
        source_root
        / ".artifacts/track_b_b1_r4_1188_22_pb_20260723"
        / "formal-a001-20260723T091800Z-398f8725"
    )
    old_r4_a004 = (
        source_root
        / ".artifacts/track_b_r4_external_brain_handoff_20260722"
        / "responses/run-20260723T023657Z-R4resp-357f260d"
        / "admission/a004/admission.json"
    )
    expected_inputs: dict[str, tuple[Path, int, str, str]] = {
        "old_r4_receipt": (
            old_r4_formal / "authority_receipt.json",
            2613,
            "0b3366a3e1640a13675a28d1408b9b96ede3a0e6403e71a8f9222f1f44e5b5c2",
            "0644",
        ),
        "old_r4_toolchain_record": (
            old_r4_formal / "toolchain_record.json",
            154545,
            "b99c9dd62b9be3c06de93d125bd2feaadc761f9eb541eb3d39a72070f33314f3",
            "0644",
        ),
        "old_r4_raw_manifest": (
            old_r4_formal / "SHA256SUMS",
            1795,
            "8049f487106735c5d133d8c5998bd669eedca46e28dd4bef46714aac88d2c8ca",
            "0644",
        ),
        "old_r4_a004_admission": (
            old_r4_a004,
            10273,
            "2ebceb7bcdf93ad8cffa75e49eef89af679729f64a47a06ae27fa44682c206ff",
            "0644",
        ),
        "strict_instance": (
            strict_instance,
            92201,
            "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
            "0644",
        ),
        "resume_authority": (
            smm2_run / "resume-a001/authority.json",
            3993,
            "24a896999cdea34e3fcde84a1f14be8516f321bbbe3654dd856b1116994b3ca8",
            "0644",
        ),
        "geometry_admission": (
            smm2_run / "geometry-admission-a002/admission.json",
            3075,
            "abb67f2334756a22650457b3a066d32b48b7d5f8918406b53f4f4140ec3fbfdc",
            "0644",
        ),
        "pb_authority": (
            smm2_run / "pb-authority-a001/authority.json",
            6328,
            "8dd1d60e3412e84d73c190f726fa862082907cc0e7a64080cb8c7a218296d37e",
            "0644",
        ),
        "translation_gate": (
            smm2_run / "translation-a001/translation_gate.json",
            5356,
            "e2146c2f1e4ded7bb080e7cb29c55d506a16ba778f69a64e492422ca99b8aa67",
            "0644",
        ),
        "formula": (
            smm2_run / "build-a001/formula.opb",
            283,
            "d4b79cd76c80d23e509ad09b1d2e7fa02fa337049f40459ab803f0fc55a4d865",
            "0644",
        ),
        "old_internal_receipt": (
            smm2_run / "formal-a001/internal_formal_receipt.json",
            13404,
            "1a68ea4cd896e19787b4c2bcf73bf8e87a216c6c318065a4410e89b9c0eda5fc",
            "0644",
        ),
        "old_launch_receipt": (
            smm2_run / "launch-a001/launch_receipt.json",
            8759,
            "3125e43943ed07aeb68f2b28344206679183fcf8a761540d47bf8f9c0831c98c",
            "0644",
        ),
        "old_closeout": (
            smm2_run / "closeout-a001/closeout.json",
            5877,
            "35f87223990b72cf2d77581f2718603cc8f620b97ce044fc502fc368ecec47b9",
            "0644",
        ),
        "smm3_authority": (
            smm3_run / "authority-a001/authority.json",
            30514,
            "4bfa5711c4f9214e7cb6ad1cd0dc5cb647667f5ced42ebf8d4ea786d3e4833e9",
            "0644",
        ),
        "smm3_selection": (
            smm3_run / "formal-attempt-a002/selection.json",
            19714,
            "9603bf3135f8173a9b3c15a59fb5bdf7d7b2d895fa63c839b21406556d33582f",
            "0644",
        ),
        "smm3_failure": (
            smm3_run / "formal-attempt-a002/attempt-failure.json",
            834,
            "5251e0f8c1f48fe910c8c29e09db2b1f954674dc0ca26b43659e457a1afafc5c",
            "0644",
        ),
    }
    for filename, (size, digest, mode_octal) in OLD_R4_FORMAL_MEMBERS.items():
        expected_inputs[old_r4_member_key(filename)] = (
            old_r4_formal / filename,
            size,
            digest,
            mode_octal,
        )
    result: dict[str, Any] = {}
    for name, expected_spec in expected_inputs.items():
        path, size, digest = expected_spec[:3]
        expected_mode = expected_spec[3]
        record = identity(path, name)
        if (
            record["size_bytes"] != size
            or record["sha256"] != digest
            or record["mode_octal"] != expected_mode
        ):
            raise RecoveryError(f"{name}: historical byte identity drifted")
        result[name] = record
    closeout, _ = load_json(expected_inputs["old_closeout"][0], "old closeout")
    if (
        closeout.get("status") != "FORMAL_AUTHORITY_INCOMPLETE"
        or closeout.get("attempt") != "a001_consumed_no_retry"
        or closeout.get("upper_bound_update_authorized") is not False
        or closeout.get("ledger") != {"upper": [1188, 22], "lower": "absent"}
    ):
        raise RecoveryError("SMM2 a001 closeout semantics drifted")
    internal, _ = load_json(
        expected_inputs["old_internal_receipt"][0],
        "old internal receipt",
    )
    if (
        internal.get("status") != "VERIFIED"
        or internal.get("proof_status") != "VERIFIED UNSATISFIABLE"
        or internal.get("upper_bound_update_authorized") is not False
    ):
        raise RecoveryError("SMM2 internal proof history drifted")
    build: dict[str, Any] = {}
    for name in BUILD_FILES:
        record = identity(smm2_run / "build-a001" / name, f"build {name}")
        size, digest, mode_octal = BUILD_FILE_ANCHORS[name]
        if (
            record["size_bytes"] != size
            or record["sha256"] != digest
            or record["mode_octal"] != mode_octal
        ):
            raise RecoveryError(f"build {name}: historical byte identity drifted")
        build[name] = record
    result["build_files"] = build
    result["formula"] = dict(build["formula.opb"])
    result["variable_map"] = dict(build["variable_map.json"])
    result["source_roots"] = {
        "r4": str(source_root),
        "smm2": str(smm2_run),
        "smm3": str(smm3_run),
    }
    return result


def _snapshot_one(
    source_identity: Mapping[str, Any],
    output: Path,
    label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, observed = read_regular(Path(str(source_identity.get("path"))), label)
    if observed != dict(source_identity):
        raise RecoveryError(f"{label}: source identity drifted before snapshot")
    mode_text = observed.get("mode_octal")
    if not isinstance(mode_text, str) or re.fullmatch(r"[0-7]{4}", mode_text) is None:
        raise RecoveryError(f"{label}: source mode is malformed")
    snapshotted = write_once(output, raw, int(mode_text, 8))
    if (
        snapshotted["size_bytes"] != observed["size_bytes"]
        or snapshotted["sha256"] != observed["sha256"]
        or snapshotted["mode_octal"] != observed["mode_octal"]
    ):
        raise RecoveryError(f"{label}: snapshot content identity drifted")
    contract = identity_contract()
    try:
        source_projection = contract.canonical_content_projection(
            dict(observed),
            f"{label} source",
        )
        snapshot_projection = contract.canonical_content_projection(
            dict(snapshotted),
            f"{label} snapshot",
        )
    except Exception as exc:
        raise RecoveryError(f"{label}: identity contract failed: {exc}") from exc
    return (
        {
            "identity": dict(observed),
            "content_projection": source_projection,
        },
        {
            "identity": dict(snapshotted),
            "content_projection": snapshot_projection,
        },
    )


def snapshot_expected_inputs(
    source_inputs: Mapping[str, Any],
    snapshot_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    mkdir_once(snapshot_root)
    build_root = snapshot_root / "build-a001"
    mkdir_once(build_root)
    snapshotted: dict[str, Any] = {}
    sources: dict[str, Any] = {}
    excluded = {"build_files", "formula", "variable_map", "source_roots"}
    for name in sorted(set(source_inputs) - excluded):
        record = source_inputs.get(name)
        if not isinstance(record, Mapping):
            raise RecoveryError(f"{name}: historical source identity missing")
        suffix = Path(str(record.get("path"))).suffix or ".bin"
        source_binding, snapshot_binding = _snapshot_one(
            record,
            snapshot_root / f"{name}{suffix}",
            name,
        )
        sources[name] = source_binding
        snapshotted[name] = snapshot_binding["identity"]
    source_build = source_inputs.get("build_files")
    if not isinstance(source_build, Mapping) or set(source_build) != set(BUILD_FILES):
        raise RecoveryError("historical build file set drifted")
    snapshot_build: dict[str, Any] = {}
    source_build_bindings: dict[str, Any] = {}
    for name in BUILD_FILES:
        record = source_build.get(name)
        if not isinstance(record, Mapping):
            raise RecoveryError(f"build {name}: historical identity missing")
        source_binding, snapshot_binding = _snapshot_one(
            record,
            build_root / name,
            f"build {name}",
        )
        source_build_bindings[name] = source_binding
        snapshot_build[name] = snapshot_binding["identity"]
    sources["build_files"] = source_build_bindings
    snapshotted["build_files"] = snapshot_build
    snapshotted["formula"] = dict(snapshot_build["formula.opb"])
    snapshotted["variable_map"] = dict(snapshot_build["variable_map.json"])
    sources["formula"] = dict(source_build_bindings["formula.opb"])
    sources["variable_map"] = dict(source_build_bindings["variable_map.json"])
    source_roots = source_inputs.get("source_roots")
    if not isinstance(source_roots, Mapping) or set(source_roots) != {"r4", "smm2", "smm3"}:
        raise RecoveryError("historical source-root set drifted")
    sources["source_roots"] = dict(source_roots)
    pins: dict[str, Any] = {}
    contract = identity_contract()
    for name in COMPOSITION_INPUT_NAMES:
        record = snapshotted.get(name)
        if not isinstance(record, Mapping):
            raise RecoveryError(f"composition input {name} snapshot missing")
        try:
            projection = contract.canonical_content_projection(
                dict(record),
                f"composition input {name}",
            )
        except Exception as exc:
            raise RecoveryError(
                f"composition input {name} identity contract failed: {exc}"
            ) from exc
        pins[name] = {
            "identity": dict(record),
            "content_projection": projection,
        }
    return (
        snapshotted,
        sources,
        {
            "schema_version": "b1_smm4_composition_pins_v1",
            "inputs": pins,
        },
    )


def _replay_composition_from_authority_parts(
    inputs: Mapping[str, Any],
    pins: Mapping[str, Any],
    tools: Mapping[str, Any],
) -> dict[str, Any]:
    module = _load_composition_verifier(tools)
    try:
        validated_pins = module.parse_pins(json_bytes(dict(pins)))
    except Exception as exc:
        raise RecoveryError(f"composition pin replay failed: {exc}") from exc
    raw_inputs: dict[str, bytes] = {}
    identities: dict[str, dict[str, Any]] = {}
    for name in COMPOSITION_INPUT_NAMES:
        expected = inputs.get(name)
        if not isinstance(expected, Mapping):
            raise RecoveryError(f"composition input {name} identity missing")
        raw, observed = read_regular(Path(str(expected.get("path"))), name)
        if observed != dict(expected):
            raise RecoveryError(f"composition input {name} snapshot drifted")
        raw_inputs[name] = raw
        identities[name] = observed
    try:
        replay = module.verify_composition(
            raw_inputs,
            identities,
            validated_pins,
        )
    except Exception as exc:
        raise RecoveryError(f"SMM4 composition replay failed: {exc}") from exc
    if (
        not isinstance(replay, dict)
        or replay.get("schema_version") != "b1_smm4_composition_gate_v1"
        or replay.get("status") != "PASS"
        or replay.get("decision") != "LOCAL_UPPER_RECOVERY_INPUT_ADMITTED"
        or replay.get("formal_attempt_admitted") is not True
        or replay.get("upper_bound_update_authorized") is not False
    ):
        raise RecoveryError("SMM4 composition replay semantics drifted")
    return replay


def replay_composition(authority: Mapping[str, Any]) -> dict[str, Any]:
    inputs = authority.get("inputs")
    pins = authority.get("composition_pins")
    tools = authority.get("tools")
    if (
        not isinstance(inputs, Mapping)
        or not isinstance(pins, Mapping)
        or not isinstance(tools, Mapping)
    ):
        raise RecoveryError("SMM4 authority composition closure missing")
    replay = _replay_composition_from_authority_parts(inputs, pins, tools)
    if replay != authority.get("composition_admission"):
        raise RecoveryError("SMM4 composition replay drifted from authority")
    return replay


def replay_old_upper(authority: Mapping[str, Any]) -> dict[str, Any]:
    inputs = authority.get("inputs")
    tools = authority.get("tools")
    binaries = authority.get("binaries")
    if (
        not isinstance(inputs, Mapping)
        or not isinstance(tools, Mapping)
        or not isinstance(binaries, Mapping)
    ):
        raise RecoveryError("SMM4 authority old-upper closure missing")
    replay = _replay_old_upper_from_authority_parts(inputs, tools, binaries)
    if replay != authority.get("old_upper_replay"):
        raise RecoveryError("old R4 replay drifted from SMM4 authority")
    return replay


def bootstrap_payload(
    run_dir: Path,
    snapshot_root: Path,
    nonce: str,
    *,
    source_root: Path,
    smm2_run: Path,
    smm3_run: Path,
    implementation_head: str,
) -> dict[str, Any]:
    if not RUN_RE.fullmatch(run_dir.name):
        raise RecoveryError("SMM4 run basename is not canonical")
    if run_dir.parent != SMM4_ARTIFACT_ROOT:
        raise RecoveryError("SMM4 run must be directly below the fixed artifact root")
    source_inputs = validate_expected_inputs(
        source_root=source_root,
        smm2_run=smm2_run,
        smm3_run=smm3_run,
    )
    inputs, historical_sources, composition_pins = snapshot_expected_inputs(
        source_inputs,
        snapshot_root,
    )
    current_toolchain = current_toolchain_snapshot()
    tools = current_toolchain["tools"]
    binaries = current_toolchain["binaries"]
    old_upper_replay = _replay_old_upper_from_authority_parts(
        inputs,
        tools,
        binaries,
    )
    composition_admission = _replay_composition_from_authority_parts(
        inputs,
        composition_pins,
        tools,
    )
    manager_epoch, manager_tool = capture_epoch()
    if manager_tool != tools["manager_epoch"]:
        raise RecoveryError("manager epoch tool changed across bootstrap")
    attestation_toolchain = manager_epoch.get("attestation_toolchain")
    if not isinstance(attestation_toolchain, dict):
        raise RecoveryError("manager epoch lacks privileged toolchain identity")
    expected_attestation = {
        "attestor": tools["privileged_attestor"],
        "sudo": binaries["sudo"]["target"],
        "python": binaries["privileged_python"]["target"],
    }
    for name, expected in expected_attestation.items():
        actual = attestation_toolchain.get(name)
        if not isinstance(actual, dict) or not identity_matches(actual, expected):
            raise RecoveryError(f"manager epoch privileged {name} identity drifted")
    observation_toolchain = manager_epoch.get("observation_toolchain")
    if not isinstance(observation_toolchain, dict):
        raise RecoveryError("manager epoch lacks observation toolchain identity")
    observation_busctl = observation_toolchain.get("busctl")
    if not isinstance(observation_busctl, dict) or not identity_matches(
        observation_busctl,
        binaries["busctl"],
    ):
        raise RecoveryError("manager epoch observation busctl identity drifted")
    systemd_version = run_record([str(SYSTEMD_RUN), "--version"])
    if systemd_version["exit_code"] != 0:
        raise RecoveryError("systemd-run --version failed")
    return {
        "schema_version": SCHEMA,
        "status": "PRE_RUN_AUTHORITY_PASS",
        "created_utc": utc_now(),
        "run_nonce": nonce,
        "run": str(run_dir.relative_to(ROOT)),
        "base_head": BASE_HEAD,
        "implementation_head": implementation_head,
        "git": git_snapshot(implementation_head),
        "manager_epoch": manager_epoch,
        "inputs": inputs,
        "historical_sources": historical_sources,
        "composition_pins": composition_pins,
        "composition_admission": composition_admission,
        "old_upper_replay": old_upper_replay,
        "tools": tools,
        "binaries": binaries,
        "systemd_client_version": systemd_version,
        "resource_contract": {
            "memory_high_bytes": MEMORY_HIGH,
            "memory_max_bytes": MEMORY_MAX,
            "memory_swap_max_bytes": MEMORY_SWAP_MAX,
            "oom_policy": "continue",
            "kill_mode": "control-group",
            "send_sigkill": "yes",
            "single_worker": True,
            "proof_limit_bytes": PROOF_LIMIT,
            "artifact_low_water_bytes": LOW_WATER,
            "required_free_before_formal_bytes": REQUIRED_FREE,
            "formal_attempt_limit": 1,
            "formal_runtime_max_seconds": 9000,
            "formal_payload_wait_seconds": 8000,
            "formal_keeper_timeout_seconds": 8700,
            "formal_roundingsat_time_limit_seconds": 3600,
            "formal_roundingsat_monitor_limit_seconds": 3900,
            "formal_veripb_time_limit_seconds": 3600,
        },
        "claim_boundary": {
            "old_a001_consumed": True,
            "synthetic_authorized": True,
            "formal_smm4_a004_selected": False,
            "upper": [1188, 22],
            "lower": "absent",
            "upper_update_authorized": False,
            "production_certified": False,
        },
    }


def _publish_sealed_authority(
    authority_dir: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        not authority_dir.is_absolute()
        or authority_dir.name != "authority-a001"
        or authority_dir.is_symlink()
        or not authority_dir.is_dir()
    ):
        raise RecoveryError("authority package directory is not canonical")
    authority_raw = json_bytes(dict(payload))
    authority_path = authority_dir / "authority.json"
    authority_identity = write_once(authority_path, authority_raw, 0o644)
    sums = f"{sha(authority_raw)}  authority.json\n".encode("ascii")
    seal_identity = write_once(authority_dir / "SHA256SUMS", sums, 0o644)
    package_id = sha(sums)
    verified, verified_authority, verified_seal = verify_authority_package(
        authority_path,
        package_id,
    )
    if (
        verified != dict(payload)
        or verified_authority != authority_identity
        or verified_seal != seal_identity
    ):
        raise RecoveryError("fresh authority package self-verification drifted")
    return {
        "status": "PRE_RUN_AUTHORITY_PASS",
        "authority": verified_authority,
        "seal": verified_seal,
        "package_id": package_id,
        "package_self_verified": True,
    }


def publish_bootstrap(
    run_dir: Path,
    nonce: str,
    *,
    source_root: Path,
    smm2_run: Path,
    smm3_run: Path,
    implementation_head: str,
) -> int:
    if SMM4_ARTIFACT_ROOT.is_symlink():
        raise RecoveryError("SMM4 artifact root is a symlink")
    if not SMM4_ARTIFACT_ROOT.exists():
        mkdir_once(SMM4_ARTIFACT_ROOT)
    if run_dir.exists() or run_dir.is_symlink():
        raise RecoveryError("SMM4 run already exists")
    mkdir_once(run_dir)
    authority_dir = run_dir / "authority-a001"
    mkdir_once(authority_dir)
    snapshot_root = run_dir / "historical-inputs-a001"
    try:
        payload = bootstrap_payload(
            run_dir,
            snapshot_root,
            nonce,
            source_root=source_root,
            smm2_run=smm2_run,
            smm3_run=smm3_run,
            implementation_head=implementation_head,
        )
    except Exception as exc:
        failure = {
            "schema_version": "b1_sidewise_smm4_bootstrap_failure_v1",
            "status": "FORMAL_AUTHORITY_INCOMPLETE",
            "stage": "PRE_RUN_MANAGER_BOOT_AUTHORITY",
            "created_utc": utc_now(),
            "run_nonce": nonce,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "formal_smm4_a004_selection_created": False,
            "formal_smm4_a004_consumed": False,
            "synthetic_unit_started": False,
            "upper_bound_update_authorized": False,
            "ledger": {"upper": [1188, 22], "lower": "absent"},
            "next_required_task": "AB16_GATE_B_AND_16_ORGANIC_ARMS",
            "production_certified": False,
        }
        write_once(run_dir / "bootstrap-failure-a001.json", json_bytes(failure))
        print(json.dumps(failure, sort_keys=True))
        return 2
    result = _publish_sealed_authority(authority_dir, payload)
    print(json.dumps(result, sort_keys=True))
    return 0


def load_authority(
    path: Path,
    package_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    authority, record, _ = verify_authority_package(path, package_id)
    if (
        authority.get("schema_version") != SCHEMA
        or authority.get("status") != "PRE_RUN_AUTHORITY_PASS"
        or authority.get("base_head") != BASE_HEAD
        or not isinstance(authority.get("implementation_head"), str)
    ):
        raise RecoveryError("SMM4 authority semantics failed")
    if authority.get("git") != git_snapshot(authority["implementation_head"]):
        raise RecoveryError("repository identity drifted from SMM4 authority")
    replay_current_toolchain(authority)
    replay_old_upper(authority)
    replay_composition(authority)
    current, _ = capture_epoch()
    if not same_epoch(authority.get("manager_epoch", {}), current):
        raise RecoveryError("manager/boot epoch drifted")
    return authority, record


def decode_waitid(info: Any) -> dict[str, Any]:
    result = {
        "si_pid": int(info.si_pid),
        "si_uid": int(info.si_uid),
        "si_signo": int(info.si_signo),
        "si_status": int(info.si_status),
        "si_code": int(info.si_code),
    }
    allowed = {
        int(os.CLD_EXITED),
        int(os.CLD_KILLED),
        int(os.CLD_DUMPED),
    }
    if result["si_code"] not in allowed:
        raise RecoveryError(f"unsupported waitid si_code {result['si_code']}")
    return result


def decode_waitpid(status_value: int) -> dict[str, Any]:
    if os.WIFEXITED(status_value):
        return {
            "kind": "CLD_EXITED",
            "exit_code": os.WEXITSTATUS(status_value),
            "signal": None,
            "core_dumped": False,
        }
    if os.WIFSIGNALED(status_value):
        return {
            "kind": "CLD_DUMPED" if os.WCOREDUMP(status_value) else "CLD_KILLED",
            "exit_code": None,
            "signal": os.WTERMSIG(status_value),
            "core_dumped": bool(os.WCOREDUMP(status_value)),
        }
    raise RecoveryError("payload did not reach an exited or signaled state")


def wait_records_agree(waitid: Mapping[str, Any], waitpid: Mapping[str, Any]) -> bool:
    code = waitid.get("si_code")
    status_value = waitid.get("si_status")
    if code == int(os.CLD_EXITED):
        return waitpid.get("kind") == "CLD_EXITED" and waitpid.get("exit_code") == status_value
    if code == int(os.CLD_KILLED):
        return waitpid.get("kind") == "CLD_KILLED" and waitpid.get("signal") == status_value
    if code == int(os.CLD_DUMPED):
        return waitpid.get("kind") == "CLD_DUMPED" and waitpid.get("signal") == status_value
    return False


def wait_for_path(path: Path, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.is_file() and not path.is_symlink():
            return
        time.sleep(0.05)
    raise RecoveryError(f"timed out waiting for {path}")


def supervisor_mode(args: argparse.Namespace) -> int:
    state_dir = args.state_dir
    if state_dir is None or state_dir.is_symlink() or not state_dir.is_dir():
        raise RecoveryError("supervisor state directory is not real")
    spec, spec_identity = load_json(args.payload_spec, "payload spec")
    if spec_identity["sha256"] != args.payload_spec_sha256:
        raise RecoveryError("payload spec SHA drifted")
    if (
        spec.get("schema_version") != "b1_sidewise_smm4_payload_spec_v1"
        or spec.get("run_nonce") != args.run_nonce
        or spec.get("unit") != args.unit
        or spec.get("attempt") != args.attempt
    ):
        raise RecoveryError("payload spec semantics drifted")
    argv = spec.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(value, str) and value for value in argv):
        raise RecoveryError("payload argv is malformed")
    timing_contract = spec.get("timing_contract")
    if (
        not isinstance(timing_contract, dict)
        or type(timing_contract.get("keeper_timeout_seconds")) is not int
        or args.keeper_timeout != timing_contract["keeper_timeout_seconds"]
    ):
        raise RecoveryError("supervisor keeper timeout differs from payload spec")
    invocation_id = os.environ.get("INVOCATION_ID", "")
    if not invocation_id:
        raise RecoveryError("supervisor lacks INVOCATION_ID")
    child_pid = os.fork()
    if child_pid == 0:
        try:
            wait_for_path(args.start_token, 300)
            token, _ = load_json(args.start_token, "payload start token")
            if (
                token.get("schema_version") != "b1_sidewise_smm4_payload_start_token_v1"
                or token.get("status") != "PAYLOAD_START_AUTHORIZED"
                or token.get("run_nonce") != args.run_nonce
                or token.get("attempt") != args.attempt
                or token.get("unit") != args.unit
                or token.get("invocation_id") != invocation_id
            ):
                os._exit(125)
            os.execve(argv[0], argv, os.environ.copy())
        except BaseException:
            os._exit(126)
    start = {
        "schema_version": SUPERVISOR_SCHEMA,
        "run_nonce": args.run_nonce,
        "attempt": args.attempt,
        "purpose": spec.get("purpose"),
        "unit": args.unit,
        "invocation_id": invocation_id,
        "supervisor_pid": os.getpid(),
        "payload_pid": child_pid,
        "payload_spec": spec_identity,
        "authority": spec.get("authority"),
        "manager_epoch": spec.get("manager_epoch"),
        "resource_contract": spec.get("resource_contract"),
        "timing_contract": spec.get("timing_contract"),
        "started_monotonic_ns": time.monotonic_ns(),
    }
    write_once(state_dir / "supervisor-start.json", json_bytes(start))
    info = os.waitid(os.P_PID, child_pid, os.WEXITED | os.WNOWAIT)
    if info is None:
        raise RecoveryError("waitid returned no payload status")
    waitid_record = decode_waitid(info)
    reaped_pid, raw_status = os.waitpid(child_pid, 0)
    if reaped_pid != child_pid:
        raise RecoveryError("waitpid reaped an unexpected child")
    waitpid_record = decode_waitpid(raw_status)
    if not wait_records_agree(waitid_record, waitpid_record):
        raise RecoveryError("waitid and waitpid disagree")
    start_token, start_token_identity = load_json(
        args.start_token,
        "payload start token",
    )
    if (
        start_token.get("schema_version") != "b1_sidewise_smm4_payload_start_token_v1"
        or start_token.get("status") != "PAYLOAD_START_AUTHORIZED"
        or start_token.get("run_nonce") != args.run_nonce
        or start_token.get("attempt") != args.attempt
        or start_token.get("unit") != args.unit
        or start_token.get("invocation_id") != invocation_id
    ):
        raise RecoveryError("payload start token semantics failed")
    completion_seal_value = start_token.get("completion_seal")
    if (
        not isinstance(completion_seal_value, str)
        or not os.path.isabs(completion_seal_value)
        or spec.get("completion_seal") != completion_seal_value
    ):
        raise RecoveryError("payload completion seal path mismatch")
    completion_seal = Path(completion_seal_value)
    seal_written = completion_seal.is_file() and not completion_seal.is_symlink()
    seal_identity = identity(completion_seal, "payload completion seal") if seal_written else None
    if waitpid_record["kind"] == "CLD_EXITED":
        wait_status = {
            "code": "CLD_EXITED",
            "status": waitpid_record["exit_code"],
        }
    else:
        wait_status = {
            "code": waitpid_record["kind"],
            "status": waitpid_record["signal"],
        }
    terminal = {
        "schema_version": PAYLOAD_TERMINAL_SCHEMA,
        "run_nonce": args.run_nonce,
        "attempt": args.attempt,
        "purpose": spec.get("purpose"),
        "unit": args.unit,
        "invocation_id": invocation_id,
        "supervisor_pid": os.getpid(),
        "payload_pid": child_pid,
        "keeper_pid": os.getpid(),
        "supervisor_role": "keeper",
        "waitid": waitid_record,
        "waitpid": waitpid_record,
        "wait_status": wait_status,
        "payload_reaped": True,
        "seal_written": seal_written,
        "completion_seal": seal_identity,
        "authority": start_token.get("authority"),
        "selection": start_token.get("selection"),
        "launch": start_token.get("launch"),
        "manager_epoch": start_token.get("manager_epoch"),
        "resource_contract": start_token.get("resource_contract"),
        "timing_contract": start_token.get("timing_contract"),
        "start_token": start_token_identity,
        "payload_spec": spec_identity,
        "reaped_monotonic_ns": time.monotonic_ns(),
    }
    write_once(state_dir / "payload-terminal.json", json_bytes(terminal))
    wait_for_path(args.release_token, args.keeper_timeout)
    release, _ = load_json(args.release_token, "release token")
    if (
        release.get("schema_version") != TOKEN_SCHEMA
        or release.get("status") != "RESOURCE_VERIFIED_RELEASE"
        or release.get("run_nonce") != args.run_nonce
        or release.get("attempt") != args.attempt
        or release.get("unit") != args.unit
        or release.get("invocation_id") != invocation_id
    ):
        raise RecoveryError("release token semantics failed")
    if waitpid_record["kind"] == "CLD_EXITED":
        return int(waitpid_record["exit_code"])
    signum = int(waitpid_record["signal"])
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)
    time.sleep(1)
    return 127


def synthetic_payload_mode(args: argparse.Namespace) -> int:
    if args.synthetic_exit_code not in {0, 7}:
        raise RecoveryError("synthetic exit code must be 0 or 7")
    if args.synthetic_purpose not in {
        "synthetic_success",
        "synthetic_postseal_failure",
    }:
        raise RecoveryError("synthetic purpose is invalid")
    if not isinstance(args.synthetic_unit, str) or not args.synthetic_unit.endswith(".service"):
        raise RecoveryError("synthetic unit is invalid")
    expected_exit = 0 if args.synthetic_purpose == "synthetic_success" else 7
    if args.synthetic_exit_code != expected_exit:
        raise RecoveryError("synthetic purpose/exit code mismatch")
    seal = {
        "schema_version": "b1_sidewise_smm4_synthetic_payload_seal_v1",
        "run_nonce": args.run_nonce,
        "attempt": args.attempt,
        "purpose": args.synthetic_purpose,
        "unit": args.synthetic_unit,
        "exit_after_seal": args.synthetic_exit_code,
        "sealed_monotonic_ns": time.monotonic_ns(),
    }
    write_once(args.synthetic_seal, json_bytes(seal))
    return int(args.synthetic_exit_code)


def publish_selection(
    path: Path,
    *,
    authority_path: Path,
    authority_package_id: str,
    attempt: str,
    purpose: str,
    unit: str,
    worker_argv: list[str],
    payload_spec: Mapping[str, Any],
) -> dict[str, Any]:
    authority, authority_identity = load_authority(
        authority_path,
        authority_package_id,
    )
    contract = identity_contract()
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
        raise RecoveryError(f"authority identity contract failed: {exc}") from exc
    current_epoch, _ = capture_epoch()
    if not same_epoch(authority["manager_epoch"], current_epoch):
        raise RecoveryError("manager epoch drifted before selection")
    payload = {
        "schema_version": SELECTION_SCHEMA,
        "status": "SELECTED_CONSUMED",
        "created_utc": utc_now(),
        "attempt": attempt,
        "purpose": purpose,
        "run_nonce": authority["run_nonce"],
        "unit": unit,
        "authority": full_identity,
        "authority_content_identity": content_identity,
        "authority_package_id": authority_package_id,
        "manager_epoch": current_epoch,
        "worker_argv": worker_argv,
        "payload_spec": payload_spec,
        "resource_contract": authority["resource_contract"],
        "upper_bound_update_authorized": False,
    }
    raw = json_bytes(payload)
    write_once(path, raw)
    after, _ = capture_epoch()
    if not same_epoch(current_epoch, after):
        raise RecoveryError("manager epoch drifted after selection; selection is consumed")
    return {
        "payload": payload,
        "identity": identity(path, "selection"),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    modes = result.add_mutually_exclusive_group(required=True)
    modes.add_argument("--bootstrap", action="store_true")
    modes.add_argument("--supervisor", action="store_true")
    modes.add_argument("--synthetic-payload", action="store_true")
    result.add_argument("--run-dir", type=Path)
    result.add_argument("--run-nonce")
    result.add_argument("--source-root", type=Path)
    result.add_argument("--smm2-run", type=Path)
    result.add_argument("--smm3-run", type=Path)
    result.add_argument("--implementation-head")
    result.add_argument("--state-dir", type=Path)
    result.add_argument("--payload-spec", type=Path)
    result.add_argument("--payload-spec-sha256")
    result.add_argument("--unit")
    result.add_argument("--attempt")
    result.add_argument("--start-token", type=Path)
    result.add_argument("--release-token", type=Path)
    result.add_argument("--keeper-timeout", type=int)
    result.add_argument("--synthetic-seal", type=Path)
    result.add_argument("--synthetic-exit-code", type=int)
    result.add_argument("--synthetic-purpose")
    result.add_argument("--synthetic-unit")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.bootstrap:
            if (
                args.run_dir is None
                or not args.run_nonce
                or args.source_root is None
                or args.smm2_run is None
                or args.smm3_run is None
                or not args.implementation_head
            ):
                raise RecoveryError(
                    "bootstrap requires run-dir, run-nonce, source-root, "
                    "smm2-run, smm3-run, and implementation-head"
                )
            return publish_bootstrap(
                args.run_dir.absolute(),
                args.run_nonce,
                source_root=args.source_root,
                smm2_run=args.smm2_run,
                smm3_run=args.smm3_run,
                implementation_head=args.implementation_head,
            )
        if args.supervisor:
            required = (
                args.state_dir,
                args.payload_spec,
                args.payload_spec_sha256,
                args.unit,
                args.attempt,
                args.run_nonce,
                args.start_token,
                args.release_token,
                args.keeper_timeout,
            )
            if any(value is None for value in required):
                raise RecoveryError("supervisor arguments incomplete")
            return supervisor_mode(args)
        if args.synthetic_payload:
            if (
                args.synthetic_seal is None
                or args.synthetic_exit_code is None
                or not args.run_nonce
                or not args.attempt
            ):
                raise RecoveryError("synthetic payload arguments incomplete")
            return synthetic_payload_mode(args)
        raise RecoveryError("no mode selected")
    except (
        OSError,
        RecoveryError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL_CLOSED",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "upper_bound_update_authorized": False,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
