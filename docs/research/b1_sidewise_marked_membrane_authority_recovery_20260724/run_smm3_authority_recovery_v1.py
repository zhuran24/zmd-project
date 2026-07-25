#!/usr/bin/env python3
"""Fail-closed SMM3 authority bootstrap and two-stage unit supervisor.

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


HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
SCHEMA = "b1_sidewise_smm3_pre_run_authority_v1"
SELECTION_SCHEMA = "b1_sidewise_smm3_attempt_selection_v1"
SUPERVISOR_SCHEMA = "b1_sidewise_smm3_supervisor_state_v1"
PAYLOAD_TERMINAL_SCHEMA = "b1_sidewise_smm3_payload_terminal_v1"
TOKEN_SCHEMA = "b1_sidewise_smm3_release_token_v1"

ROOT = Path(__file__).resolve().parents[3]
RESEARCH = Path(__file__).resolve().parent
SOURCE_ROOT = Path("/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721")
SMM2_RUN = ROOT / ".artifacts/track_b_b1_sidewise_marked_membrane_strict_20260724" / "run-20260723T161302Z-SMM2"
SMM3_ARTIFACT_ROOT = ROOT / ".artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724"
STRICT_INSTANCE = (
    SOURCE_ROOT / "docs/research/cleanroom_rederivation_20260718" / "strict/external/problem_instance.json"
)
FIXED_PYTHON = Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13")
ROUNDINGSAT = Path("/home/zhuran24/tools/roundingsat/build/roundingsat")
VERIPB = Path("/home/zhuran24/.cargo/bin/veripb")
SYSTEMD_RUN = Path("/usr/bin/systemd-run")
SYSTEMCTL = Path("/usr/bin/systemctl")
BUSCTL = Path("/usr/bin/busctl")
SUDO = Path("/usr/bin/sudo")
PRIVILEGED_PYTHON = Path("/usr/bin/python3.14")

MANAGER_TOOL = RESEARCH / "manager_epoch_authority_v1.py"
PRIVILEGED_ATTESTOR = RESEARCH / "privileged_manager_exe_attestor_v1.py"
ATTEMPT_RUNNER = RESEARCH / "run_smm3_two_stage_attempt_v1.py"
FORMAL_PAYLOAD = RESEARCH / "run_smm3_formal_payload_v1.py"
INDEPENDENT_VERIFIER = RESEARCH / "verify_smm3_two_stage_v1.py"
TRANSLATION_GATE = (
    RESEARCH.parent / "b1_sidewise_marked_membrane_strict_20260724" / "verify_ceiling_exclusion_translation_v1.py"
)

MEMORY_HIGH = 35 * 1024**3
MEMORY_MAX = 39 * 1024**3
MEMORY_SWAP_MAX = 16 * 1024**3
PROOF_LIMIT = 5_000_000_000
LOW_WATER = 10 * 1024**3
REQUIRED_FREE = LOW_WATER + PROOF_LIMIT

RUN_RE = re.compile(r"run-[0-9]{8}T[0-9]{6}Z-SMM3-[A-Za-z0-9_-]{4,16}\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")

EXPECTED_INPUTS: dict[str, tuple[Path, int, str]] = {
    "strict_instance": (
        STRICT_INSTANCE,
        92201,
        "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c",
    ),
    "resume_authority": (
        SMM2_RUN / "resume-a001/authority.json",
        3993,
        "24a896999cdea34e3fcde84a1f14be8516f321bbbe3654dd856b1116994b3ca8",
    ),
    "geometry_admission": (
        SMM2_RUN / "geometry-admission-a002/admission.json",
        3075,
        "abb67f2334756a22650457b3a066d32b48b7d5f8918406b53f4f4140ec3fbfdc",
    ),
    "pb_authority": (
        SMM2_RUN / "pb-authority-a001/authority.json",
        6328,
        "8dd1d60e3412e84d73c190f726fa862082907cc0e7a64080cb8c7a218296d37e",
    ),
    "translation_gate": (
        SMM2_RUN / "translation-a001/translation_gate.json",
        5356,
        "e2146c2f1e4ded7bb080e7cb29c55d506a16ba778f69a64e492422ca99b8aa67",
    ),
    "formula": (
        SMM2_RUN / "build-a001/formula.opb",
        283,
        "d4b79cd76c80d23e509ad09b1d2e7fa02fa337049f40459ab803f0fc55a4d865",
    ),
    "old_internal_receipt": (
        SMM2_RUN / "formal-a001/internal_formal_receipt.json",
        13404,
        "1a68ea4cd896e19787b4c2bcf73bf8e87a216c6c318065a4410e89b9c0eda5fc",
    ),
    "old_launch_receipt": (
        SMM2_RUN / "launch-a001/launch_receipt.json",
        8759,
        "3125e43943ed07aeb68f2b28344206679183fcf8a761540d47bf8f9c0831c98c",
    ),
    "old_closeout": (
        SMM2_RUN / "closeout-a001/closeout.json",
        5877,
        "35f87223990b72cf2d77581f2718603cc8f620b97ce044fc502fc368ecec47b9",
    ),
}

BUILD_FILES = (
    "formula.opb",
    "variable_map.json",
    "encoder.meta.json",
    "build_record.json",
    "estimate.json",
    "SHA256SUMS",
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
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path.absolute(), flags)
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
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    fields_after = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
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
        )
    )


def write_once(path: Path, raw: bytes, mode: int = 0o644) -> None:
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
        os.fsync(descriptor)
        if os.fstat(descriptor).st_size != len(raw):
            raise RecoveryError(f"output size mismatch: {path}")
    finally:
        os.close(descriptor)


def mkdir_once(path: Path) -> None:
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise RecoveryError(f"directory parent is not real: {path.parent}")
    try:
        os.mkdir(path, 0o755)
    except OSError as exc:
        raise RecoveryError(f"cannot create no-overwrite directory {path}: {exc}") from exc


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
    """Recompute every tool identity admitted by the SMM3 authority."""

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
            raise RecoveryError(f"SMM3 authority lacks {group} toolchain mapping")
        if set(expected_group) != set(actual_group):
            raise RecoveryError(f"SMM3 authority {group} key set drifted")
        for name, actual in actual_group.items():
            if expected_group.get(name) != actual:
                raise RecoveryError(f"SMM3 authority {group}.{name} identity drifted")
    return {
        "schema_version": "b1_sidewise_smm3_current_toolchain_replay_v1",
        "status": "CURRENT_TOOLCHAIN_REPLAY_PASS",
        "tools": current["tools"],
        "binaries": current["binaries"],
    }


def load_module_from_bytes(path: Path, label: str) -> tuple[ModuleType, dict[str, Any]]:
    raw, record = read_regular(path, label)
    module = ModuleType(f"_smm3_{path.stem}_{record['sha256'][:12]}")
    module.__file__ = str(path)
    try:
        code = compile(raw, str(path), "exec")
        exec(code, module.__dict__)
    except Exception as exc:
        raise RecoveryError(f"{label}: cannot execute pinned bytes: {exc}") from exc
    return module, record


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


def git_snapshot() -> dict[str, Any]:
    def git(*argv: str) -> bytes:
        run = subprocess.run(
            ["git", "-C", str(ROOT), *argv],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return run.stdout

    head = git("rev-parse", "HEAD").decode("ascii").strip()
    if head != HEAD:
        raise RecoveryError(f"HEAD drifted: {head}")
    exclusions = (
        ":(exclude).artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/**",
        ":(exclude)docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724/README.md",
        ":(exclude)docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724/03_execution_record.md",
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
    return {
        "head": head,
        "tracked_diff_size_bytes": len(diff),
        "tracked_diff_sha256": sha(diff),
        "status_size_bytes": len(status_bytes),
        "status_sha256": sha(status_bytes),
        "excluded_paths": [
            ".artifacts/track_b_b1_sidewise_marked_membrane_authority_recovery_20260724/**",
            "docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724/README.md",
            "docs/research/b1_sidewise_marked_membrane_authority_recovery_20260724/03_execution_record.md",
        ],
    }


def validate_expected_inputs() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, (path, size, digest) in EXPECTED_INPUTS.items():
        record = identity(path, name)
        if record["size_bytes"] != size or record["sha256"] != digest:
            raise RecoveryError(f"{name}: SMM2 byte identity drifted")
        result[name] = record
    closeout, _ = load_json(EXPECTED_INPUTS["old_closeout"][0], "old closeout")
    if (
        closeout.get("status") != "FORMAL_AUTHORITY_INCOMPLETE"
        or closeout.get("attempt") != "a001_consumed_no_retry"
        or closeout.get("upper_bound_update_authorized") is not False
        or closeout.get("ledger") != {"upper": [1188, 22], "lower": "absent"}
    ):
        raise RecoveryError("SMM2 a001 closeout semantics drifted")
    internal, _ = load_json(
        EXPECTED_INPUTS["old_internal_receipt"][0],
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
        build[name] = identity(SMM2_RUN / "build-a001" / name, f"build {name}")
    result["build_files"] = build
    result["formula"] = dict(build["formula.opb"])
    return result


def bootstrap_payload(run_dir: Path, nonce: str) -> dict[str, Any]:
    if not RUN_RE.fullmatch(run_dir.name):
        raise RecoveryError("SMM3 run basename is not canonical")
    if run_dir.parent != SMM3_ARTIFACT_ROOT:
        raise RecoveryError("SMM3 run must be directly below the fixed artifact root")
    inputs = validate_expected_inputs()
    current_toolchain = current_toolchain_snapshot()
    tools = current_toolchain["tools"]
    binaries = current_toolchain["binaries"]
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
        "head": HEAD,
        "git": git_snapshot(),
        "manager_epoch": manager_epoch,
        "inputs": inputs,
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
            "formal_a002_selected": False,
            "upper": [1188, 22],
            "lower": "absent",
            "upper_update_authorized": False,
            "production_certified": False,
        },
    }


def publish_bootstrap(run_dir: Path, nonce: str) -> int:
    if SMM3_ARTIFACT_ROOT.is_symlink():
        raise RecoveryError("SMM3 artifact root is a symlink")
    if not SMM3_ARTIFACT_ROOT.exists():
        mkdir_once(SMM3_ARTIFACT_ROOT)
    if run_dir.exists() or run_dir.is_symlink():
        raise RecoveryError("SMM3 run already exists")
    mkdir_once(run_dir)
    try:
        payload = bootstrap_payload(run_dir, nonce)
    except Exception as exc:
        failure = {
            "schema_version": "b1_sidewise_smm3_bootstrap_failure_v1",
            "status": "FORMAL_AUTHORITY_INCOMPLETE",
            "stage": "PRE_RUN_MANAGER_BOOT_AUTHORITY",
            "created_utc": utc_now(),
            "run_nonce": nonce,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "formal_a002_selection_created": False,
            "formal_a002_consumed": False,
            "synthetic_unit_started": False,
            "upper_bound_update_authorized": False,
            "ledger": {"upper": [1188, 22], "lower": "absent"},
            "next_required_task": "CUTS_GATE1_V4_AUTHORITY_COMPLETION",
            "production_certified": False,
        }
        write_once(run_dir / "bootstrap-failure-a001.json", json_bytes(failure))
        print(json.dumps(failure, sort_keys=True))
        return 2
    authority_dir = run_dir / "authority-a001"
    mkdir_once(authority_dir)
    authority_raw = json_bytes(payload)
    write_once(authority_dir / "authority.json", authority_raw)
    sums = f"{sha(authority_raw)}  authority.json\n".encode("ascii")
    write_once(authority_dir / "SHA256SUMS", sums)
    result = {
        "status": "PRE_RUN_AUTHORITY_PASS",
        "authority": identity(authority_dir / "authority.json", "authority"),
        "seal": identity(authority_dir / "SHA256SUMS", "authority seal"),
        "package_id": sha(sums),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


def load_authority(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    authority, record = load_json(path, "SMM3 authority")
    if (
        authority.get("schema_version") != SCHEMA
        or authority.get("status") != "PRE_RUN_AUTHORITY_PASS"
        or authority.get("head") != HEAD
    ):
        raise RecoveryError("SMM3 authority semantics failed")
    if authority.get("git") != git_snapshot():
        raise RecoveryError("repository identity drifted from SMM3 authority")
    replay_current_toolchain(authority)
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
        spec.get("schema_version") != "b1_sidewise_smm3_payload_spec_v1"
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
                token.get("schema_version") != "b1_sidewise_smm3_payload_start_token_v1"
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
        start_token.get("schema_version") != "b1_sidewise_smm3_payload_start_token_v1"
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
        "schema_version": "b1_sidewise_smm3_synthetic_payload_seal_v1",
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
    attempt: str,
    purpose: str,
    unit: str,
    worker_argv: list[str],
    payload_spec: Mapping[str, Any],
) -> dict[str, Any]:
    authority, authority_identity = load_authority(authority_path)
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
        "authority": authority_identity,
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
            if args.run_dir is None or not args.run_nonce:
                raise RecoveryError("bootstrap requires run-dir and run-nonce")
            return publish_bootstrap(args.run_dir.absolute(), args.run_nonce)
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
