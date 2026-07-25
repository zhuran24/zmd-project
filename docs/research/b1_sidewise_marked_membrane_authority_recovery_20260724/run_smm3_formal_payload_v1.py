#!/usr/bin/env python3
"""Run the SMM3 a002 formal payload without granting terminal authority."""

from __future__ import annotations

import argparse
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
from typing import Any


AUTHORITY_SCHEMA = "b1_sidewise_smm3_pre_run_authority_v1"
SELECTION_SCHEMA = "b1_sidewise_smm3_attempt_selection_v1"
RECEIPT_SCHEMA = "b1_sidewise_smm3_internal_formal_receipt_v1"
ATTEMPT = "a002"
FORMULA_SIZE = 283
FORMULA_SHA256 = "d4b79cd76c80d23e509ad09b1d2e7fa02fa337049f40459ab803f0fc55a4d865"
PROOF_LIMIT = 5_000_000_000
LOW_WATER = 10 * 1024**3
REQUIRED_FREE = LOW_WATER + PROOF_LIMIT
ROUNDINGSAT_SECONDS = 3600
ROUNDINGSAT_MONITOR_SECONDS = 3900
VERIPB_SECONDS = 3600
TRANSLATION_SECONDS = 300
RUNTIME_MAX_SECONDS = 9000
PAYLOAD_WAIT_SECONDS = 8000
KEEPER_TIMEOUT_SECONDS = 8700
JSON_LIMIT = 64 * 1024 * 1024
TEXT_LIMIT = 64 * 1024 * 1024
BUILD_MEMBERS = (
    "formula.opb",
    "variable_map.json",
    "encoder.meta.json",
    "build_record.json",
    "estimate.json",
    "SHA256SUMS",
)
ROUNDINGSAT_STATUS = re.compile(r"^s (UNSATISFIABLE|SATISFIABLE|UNKNOWN)\s*$")
VERIPB_SUCCESS = re.compile(r"^s VERIFIED UNSATISFIABLE\s*$")
VERIPB_ERROR_MARKERS = (
    "Error:",
    "Checking error",
    "panic",
    "failed",
    "unsupported",
)
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


class PayloadError(RuntimeError):
    """Raised when the SMM3 payload must fail closed."""


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise PayloadError(message)


def path_exists(path: Path) -> bool:
    return os.path.lexists(path)


def require_absent(path: Path, label: str) -> None:
    require(not path_exists(path), f"{label}: output already exists")


def stable(before: os.stat_result, after: os.stat_result) -> bool:
    return all(getattr(before, field) == getattr(after, field) for field in STABLE_STAT_FIELDS)


def snapshot_regular(
    path: Path,
    label: str,
    *,
    collect: bool = True,
    max_bytes: int | None = None,
) -> tuple[bytes | None, dict[str, Any]]:
    absolute = path.absolute()
    descriptor = os.open(
        absolute,
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode), f"{label}: not a regular file")
        if max_bytes is not None:
            require(
                before.st_size <= max_bytes,
                f"{label}: exceeds {max_bytes} byte read limit",
            )
        digest = hashlib.sha256()
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, 1 << 20)
            if not block:
                break
            total += len(block)
            if max_bytes is not None:
                require(
                    total <= max_bytes,
                    f"{label}: grew beyond {max_bytes} byte read limit",
                )
            digest.update(block)
            if collect:
                chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require(stable(before, after), f"{label}: changed during same-fd read")
    require(total == before.st_size, f"{label}: short or extended read")
    return (
        b"".join(chunks) if collect else None,
        {
            "path": str(absolute),
            "size_bytes": total,
            "sha256": digest.hexdigest(),
            "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
        },
    )


def strict_json(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PayloadError(f"{label}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise PayloadError(f"{label}: non-integer JSON number {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PayloadError(f"{label}: malformed strict JSON: {exc}") from exc


def load_json(
    path: Path,
    label: str,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    raw, identity = snapshot_regular(
        path,
        label,
        max_bytes=JSON_LIMIT,
    )
    require(raw is not None, f"{label}: internal snapshot failure")
    payload = strict_json(raw, label)
    require(isinstance(payload, dict), f"{label}: root is not an object")
    return payload, identity, raw


def identity_path(value: Any, label: str) -> Path:
    require(isinstance(value, dict), f"{label}: identity is not an object")
    path = value.get("path")
    require(
        isinstance(path, str) and path.startswith("/"),
        f"{label}: absolute path missing",
    )
    return Path(path)


def match_identity(
    actual: dict[str, Any],
    expected: Any,
    label: str,
) -> None:
    require(isinstance(expected, dict), f"{label}: pinned identity missing")
    for field in ("path", "size_bytes", "sha256", "mode_octal"):
        require(field in expected, f"{label}: pinned {field} missing")
        require(
            actual.get(field) == expected.get(field),
            f"{label}: {field} drifted",
        )


def snapshot_pinned(
    expected: Any,
    label: str,
    *,
    collect: bool = True,
    max_bytes: int | None = None,
) -> tuple[bytes | None, dict[str, Any]]:
    path = identity_path(expected, label)
    raw, actual = snapshot_regular(
        path,
        label,
        collect=collect,
        max_bytes=max_bytes,
    )
    match_identity(actual, expected, label)
    return raw, actual


def mode_from_identity(identity: dict[str, Any], label: str) -> int:
    value = identity.get("mode_octal")
    require(
        isinstance(value, str) and re.fullmatch(r"0[0-7]{3}", value) is not None,
        f"{label}: invalid mode",
    )
    return int(value, 8)


def write_once(path: Path, raw: bytes, *, mode: int = 0o644) -> dict[str, Any]:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(descriptor, raw[offset:])
            require(count > 0, f"{path}: short output write")
            offset += count
        os.fsync(descriptor)
        record = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    require(stat.S_ISREG(record.st_mode), f"{path}: output is not regular")
    return {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": sha256(raw),
        "mode_octal": f"{stat.S_IMODE(record.st_mode):04o}",
    }


def make_directory(path: Path, label: str) -> None:
    require_absent(path, label)
    os.mkdir(path, 0o755)
    record = os.lstat(path)
    require(stat.S_ISDIR(record.st_mode), f"{label}: mkdir did not make directory")
    require(not stat.S_ISLNK(record.st_mode), f"{label}: directory is symlink")


def free_bytes(path: Path) -> int:
    result = os.statvfs(path)
    return result.f_bavail * result.f_frsize


def read_proc_bounded(path: Path, label: str, limit: int = 64 * 1024) -> bytes:
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(descriptor)
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, 4096)
            if not block:
                break
            total += len(block)
            require(total <= limit, f"{label}: proc payload exceeds limit")
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    for field in ("st_dev", "st_ino", "st_mode"):
        require(
            getattr(before, field) == getattr(after, field),
            f"{label}: proc identity changed during read",
        )
    return b"".join(chunks)


def verify_current_cgroup(expected_unit: str) -> dict[str, Any]:
    raw = read_proc_bounded(Path("/proc/self/cgroup"), "payload cgroup")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise PayloadError("payload cgroup: non-ASCII bytes") from exc
    unified = [line.split("::", 1)[1] for line in lines if "::" in line]
    require(len(unified) == 1, "payload cgroup: unified path is ambiguous")
    relative = unified[0]
    require(
        expected_unit in relative,
        "payload is outside selected systemd unit",
    )
    return {
        "proc_path": "/proc/self/cgroup",
        "sha256": sha256(raw),
        "size_bytes": len(raw),
        "unified_path": relative,
        "expected_unit_present": True,
    }


def executable_record(
    value: Any,
    label: str,
) -> tuple[Path, dict[str, Any], str]:
    require(isinstance(value, dict), f"{label}: binary identity missing")
    if "target" in value:
        logical = value.get("path")
        resolved = value.get("resolved_path")
        target = value.get("target")
        require(
            isinstance(logical, str) and logical.startswith("/"),
            f"{label}: logical path missing",
        )
        require(
            isinstance(resolved, str) and resolved.startswith("/"),
            f"{label}: resolved path missing",
        )
        try:
            current_resolved = Path(logical).resolve(strict=True)
        except OSError as exc:
            raise PayloadError(f"{label}: cannot resolve logical path: {exc}") from exc
        require(
            str(current_resolved) == resolved,
            f"{label}: logical path resolution drifted",
        )
        return Path(resolved), target, logical
    path = identity_path(value, label)
    return path, value, str(path)


def pin_executable(value: Any, label: str) -> dict[str, Any]:
    path, expected, logical_path = executable_record(value, label)
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode), f"{label}: not a regular file")
        digest = hashlib.sha256()
        total = 0
        while True:
            block = os.read(descriptor, 1 << 20)
            if not block:
                break
            total += len(block)
            digest.update(block)
        after = os.fstat(descriptor)
        require(stable(before, after), f"{label}: changed while pinning")
        require(total == before.st_size, f"{label}: short read while pinning")
        actual = {
            "path": str(path.absolute()),
            "size_bytes": total,
            "sha256": digest.hexdigest(),
            "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
        }
        match_identity(actual, expected, label)
        require(
            stat.S_IMODE(before.st_mode) & 0o111 != 0,
            f"{label}: executable bit missing",
        )
        return {
            "fd": descriptor,
            "before": before,
            "identity": actual,
            "logical_path": logical_path,
            "fd_path": f"/proc/self/fd/{descriptor}",
        }
    except BaseException:
        os.close(descriptor)
        raise


def verify_pinned_executable(record: dict[str, Any], label: str) -> None:
    after = os.fstat(record["fd"])
    require(
        stable(record["before"], after),
        f"{label}: pinned executable changed during use",
    )


def close_pinned_executable(record: dict[str, Any] | None) -> None:
    if record is not None:
        os.close(record["fd"])


def open_exclusive_output(path: Path) -> int:
    return os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )


def terminate_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=30)


def run_timed(
    argv: list[str],
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
    *,
    pass_fds: tuple[int, ...],
) -> tuple[int, int]:
    stdout_fd = open_exclusive_output(stdout_path)
    try:
        stderr_fd = open_exclusive_output(stderr_path)
    except BaseException:
        os.close(stdout_fd)
        raise
    started = time.monotonic()
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            argv,
            stdout=stdout_fd,
            stderr=stderr_fd,
            start_new_session=True,
            pass_fds=pass_fds,
        )
        try:
            exit_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            terminate_group(process)
            raise PayloadError(f"subprocess exceeded {timeout_seconds} seconds") from exc
    finally:
        if process is not None and process.poll() is None:
            terminate_group(process)
        os.close(stdout_fd)
        os.close(stderr_fd)
    return exit_code, round((time.monotonic() - started) * 1000)


def proof_anchor(path: Path) -> tuple[int, int, int]:
    record = os.stat(path, follow_symlinks=False)
    require(stat.S_ISREG(record.st_mode), "proof target is not regular")
    return record.st_dev, record.st_ino, record.st_mode


def proof_size(path: Path, anchor: tuple[int, int, int]) -> int:
    record = os.stat(path, follow_symlinks=False)
    require(stat.S_ISREG(record.st_mode), "proof target stopped being regular")
    require(
        (record.st_dev, record.st_ino, record.st_mode) == anchor,
        "proof target identity changed",
    )
    return record.st_size


def run_roundingsat(
    argv: list[str],
    stdout_path: Path,
    stderr_path: Path,
    proof_path: Path,
    *,
    pass_fds: tuple[int, ...],
) -> tuple[int, int, str | None]:
    stdout_fd = open_exclusive_output(stdout_path)
    try:
        stderr_fd = open_exclusive_output(stderr_path)
    except BaseException:
        os.close(stdout_fd)
        raise
    anchor = proof_anchor(proof_path)
    started = time.monotonic()
    process: subprocess.Popen[bytes] | None = None
    stop_reason: str | None = None
    try:
        process = subprocess.Popen(
            argv,
            stdout=stdout_fd,
            stderr=stderr_fd,
            start_new_session=True,
            pass_fds=pass_fds,
        )
        while process.poll() is None:
            elapsed = time.monotonic() - started
            if elapsed > ROUNDINGSAT_MONITOR_SECONDS:
                stop_reason = "roundingsat_monitor_timeout"
            else:
                try:
                    if proof_size(proof_path, anchor) > PROOF_LIMIT:
                        stop_reason = "proof_size_limit_exceeded"
                except (OSError, PayloadError):
                    stop_reason = "proof_target_identity_failed"
            if stop_reason is not None:
                terminate_group(process)
                break
            time.sleep(0.05)
        exit_code = process.wait(timeout=30)
    finally:
        if process is not None and process.poll() is None:
            terminate_group(process)
        os.close(stdout_fd)
        os.close(stderr_fd)
    return (
        exit_code,
        round((time.monotonic() - started) * 1000),
        stop_reason,
    )


def add_member(
    members: dict[str, dict[str, Any]],
    output_dir: Path,
    identity: dict[str, Any],
) -> None:
    path = Path(identity["path"])
    try:
        relative = path.relative_to(output_dir)
    except ValueError as exc:
        raise PayloadError("manifest member escaped output directory") from exc
    name = relative.as_posix()
    require(name not in members, f"duplicate manifest member {name}")
    members[name] = identity


def validate_historical_semantics(
    pb_authority: dict[str, Any],
    geometry: dict[str, Any],
    translation: dict[str, Any],
    strict_instance: dict[str, Any],
) -> None:
    require(
        pb_authority.get("schema_version") == "b1_sidewise_pb_pre_run_authority_v1"
        and pb_authority.get("status") == "PB_PRE_RUN_AUTHORITY_PASS",
        "historical PB authority semantics failed",
    )
    require(
        geometry.get("schema_version") == "b1_sidewise_geometry_admission_v1"
        and geometry.get("status") == "PASS"
        and geometry.get("decision") == "ADMITTED_FOR_PB_ENCODER",
        "historical geometry admission semantics failed",
    )
    require(
        translation.get("schema_version") == "b1_sidewise_ceiling_translation_gate_v1"
        and translation.get("status") == "PASS"
        and translation.get("decision") == "FORMAL_RUN_AUTHORIZED"
        and translation.get("formal_run_authorized") is True
        and translation.get("corpus_errors") == []
        and all(translation.get("checks", {}).values()),
        "historical translation gate semantics failed",
    )
    require(bool(strict_instance), "strict instance is empty")


def formal_timing_contract() -> dict[str, int]:
    return {
        "runtime_max_seconds": RUNTIME_MAX_SECONDS,
        "payload_wait_seconds": PAYLOAD_WAIT_SECONDS,
        "keeper_timeout_seconds": KEEPER_TIMEOUT_SECONDS,
        "roundingsat_time_limit_seconds": ROUNDINGSAT_SECONDS,
        "roundingsat_monitor_limit_seconds": ROUNDINGSAT_MONITOR_SECONDS,
        "veripb_time_limit_seconds": VERIPB_SECONDS,
    }


def validate_resource_contract(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict), "SMM3 authority resource contract missing")
    expected = {
        "memory_high_bytes": 35 * 1024**3,
        "memory_max_bytes": 39 * 1024**3,
        "memory_swap_max_bytes": 16 * 1024**3,
        "oom_policy": "continue",
        "kill_mode": "control-group",
        "send_sigkill": "yes",
        "single_worker": True,
        "proof_limit_bytes": PROOF_LIMIT,
        "artifact_low_water_bytes": LOW_WATER,
        "required_free_before_formal_bytes": REQUIRED_FREE,
        "formal_attempt_limit": 1,
        "formal_runtime_max_seconds": RUNTIME_MAX_SECONDS,
        "formal_payload_wait_seconds": PAYLOAD_WAIT_SECONDS,
        "formal_keeper_timeout_seconds": KEEPER_TIMEOUT_SECONDS,
        "formal_roundingsat_time_limit_seconds": ROUNDINGSAT_SECONDS,
        "formal_roundingsat_monitor_limit_seconds": ROUNDINGSAT_MONITOR_SECONDS,
        "formal_veripb_time_limit_seconds": VERIPB_SECONDS,
    }
    for name, expected_value in expected.items():
        require(value.get(name) == expected_value, f"resource contract drifted: {name}")
    return dict(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-systemd-unit", required=True)
    args = parser.parse_args()
    args.output_dir = args.output_dir.absolute()

    output_created = False
    python_pin: dict[str, Any] | None = None
    roundingsat_pin: dict[str, Any] | None = None
    veripb_pin: dict[str, Any] | None = None
    try:
        authority, authority_identity, authority_raw = load_json(
            args.authority,
            "SMM3 authority",
        )
        require(
            authority.get("schema_version") == AUTHORITY_SCHEMA,
            "SMM3 authority schema mismatch",
        )
        run_nonce = authority.get("run_nonce")
        require(
            isinstance(run_nonce, str) and bool(run_nonce),
            "SMM3 authority run nonce missing",
        )
        resource_contract = validate_resource_contract(authority.get("resource_contract"))
        timing_contract = formal_timing_contract()
        selection, selection_identity, selection_raw = load_json(
            args.selection,
            "SMM3 selection",
        )
        require(
            selection.get("schema_version") == SELECTION_SCHEMA
            and selection.get("status") == "SELECTED_CONSUMED"
            and selection.get("attempt") == ATTEMPT
            and selection.get("purpose") == "formal"
            and selection.get("run_nonce") == run_nonce
            and selection.get("unit") == args.expected_systemd_unit
            and selection.get("worker_argv") == sys.argv
            and selection.get("authority") == authority_identity,
            "SMM3 selection semantics or argv mismatch",
        )
        require(
            isinstance(selection.get("formal_admission"), dict),
            "SMM3 formal selection lacks admission identity",
        )
        require(
            selection.get("resource_contract") == resource_contract
            and selection.get("timing_contract") == timing_contract,
            "SMM3 selection budget contract mismatch",
        )
        inputs = authority.get("inputs")
        tools = authority.get("tools")
        binaries = authority.get("binaries")
        require(isinstance(inputs, dict), "authority inputs missing")
        require(isinstance(tools, dict), "authority tools missing")
        require(isinstance(binaries, dict), "authority binaries missing")

        _, self_identity = snapshot_regular(
            Path(__file__),
            "formal payload",
            max_bytes=JSON_LIMIT,
        )
        match_identity(
            self_identity,
            tools.get("formal_payload"),
            "formal payload",
        )

        pb_raw, pb_identity = snapshot_pinned(
            inputs.get("pb_authority"),
            "historical PB authority",
            max_bytes=JSON_LIMIT,
        )
        geometry_raw, geometry_identity = snapshot_pinned(
            inputs.get("geometry_admission"),
            "historical geometry admission",
            max_bytes=JSON_LIMIT,
        )
        strict_raw, strict_identity = snapshot_pinned(
            inputs.get("strict_instance"),
            "strict instance",
            max_bytes=JSON_LIMIT,
        )
        translation_raw, translation_identity = snapshot_pinned(
            inputs.get("translation_gate"),
            "historical translation gate",
            max_bytes=JSON_LIMIT,
        )
        require(
            all(
                raw is not None
                for raw in (
                    pb_raw,
                    geometry_raw,
                    strict_raw,
                    translation_raw,
                )
            ),
            "historical input snapshot failed",
        )
        pb_payload = strict_json(pb_raw, "historical PB authority")
        geometry_payload = strict_json(
            geometry_raw,
            "historical geometry admission",
        )
        strict_payload = strict_json(strict_raw, "strict instance")
        translation_payload = strict_json(
            translation_raw,
            "historical translation gate",
        )
        require(
            all(
                isinstance(value, dict)
                for value in (
                    pb_payload,
                    geometry_payload,
                    strict_payload,
                    translation_payload,
                )
            ),
            "historical JSON root type failed",
        )
        validate_historical_semantics(
            pb_payload,
            geometry_payload,
            translation_payload,
            strict_payload,
        )

        build_expected = inputs.get("build_files")
        require(
            isinstance(build_expected, dict) and set(build_expected) == set(BUILD_MEMBERS),
            "authority build file set mismatch",
        )
        build_raw: dict[str, bytes] = {}
        build_identities: dict[str, dict[str, Any]] = {}
        build_parents: set[Path] = set()
        for name in BUILD_MEMBERS:
            raw, identity = snapshot_pinned(
                build_expected[name],
                f"historical build {name}",
                max_bytes=JSON_LIMIT,
            )
            require(raw is not None, f"historical build {name}: snapshot failed")
            build_raw[name] = raw
            build_identities[name] = identity
            build_parents.add(Path(identity["path"]).parent)
        require(len(build_parents) == 1, "historical build files are split")
        require(
            len(build_raw["formula.opb"]) == FORMULA_SIZE and sha256(build_raw["formula.opb"]) == FORMULA_SHA256,
            "historical formula identity mismatch",
        )

        translation_tool_raw, translation_tool_identity = snapshot_pinned(
            tools.get("translation_gate"),
            "translation gate tool",
            max_bytes=JSON_LIMIT,
        )
        require(
            translation_tool_raw is not None,
            "translation gate tool snapshot failed",
        )
        python_pin = pin_executable(
            binaries.get("fixed_python"),
            "fixed Python",
        )
        roundingsat_pin = pin_executable(
            binaries.get("roundingsat"),
            "RoundingSat",
        )
        veripb_pin = pin_executable(
            binaries.get("veripb"),
            "VeriPB",
        )

        require(
            args.output_dir.parent.is_dir() and not args.output_dir.parent.is_symlink(),
            "formal output parent is not a real directory",
        )
        make_directory(args.output_dir, "formal output directory")
        output_created = True
        snapshot_dir = args.output_dir / "inputs.snapshot"
        build_snapshot_dir = snapshot_dir / "build"
        make_directory(snapshot_dir, "input snapshot directory")
        make_directory(build_snapshot_dir, "build snapshot directory")
        members: dict[str, dict[str, Any]] = {}

        snapshot_identities: dict[str, Any] = {}
        for name, raw, identity in (
            ("pb_authority.json", pb_raw, pb_identity),
            ("geometry_admission.json", geometry_raw, geometry_identity),
            ("strict_instance.json", strict_raw, strict_identity),
            (
                "translation_gate.previous.json",
                translation_raw,
                translation_identity,
            ),
            (
                "translation_gate.py",
                translation_tool_raw,
                translation_tool_identity,
            ),
        ):
            output_identity = write_once(
                snapshot_dir / name,
                raw,
                mode=mode_from_identity(identity, name),
            )
            snapshot_identities[name] = output_identity
            add_member(members, args.output_dir, output_identity)
        snapshot_identities["build"] = {}
        for name in BUILD_MEMBERS:
            output_identity = write_once(
                build_snapshot_dir / name,
                build_raw[name],
                mode=mode_from_identity(build_identities[name], name),
            )
            snapshot_identities["build"][name] = output_identity
            add_member(members, args.output_dir, output_identity)

        authority_snapshot_identity = write_once(
            snapshot_dir / "smm3_authority.json",
            authority_raw,
        )
        selection_snapshot_identity = write_once(
            snapshot_dir / "a002_selection.json",
            selection_raw,
        )
        add_member(members, args.output_dir, authority_snapshot_identity)
        add_member(members, args.output_dir, selection_snapshot_identity)

        formula_path = args.output_dir / "formula.opb"
        formula_identity = write_once(
            formula_path,
            build_raw["formula.opb"],
        )
        add_member(members, args.output_dir, formula_identity)

        cgroup_receipt = verify_current_cgroup(args.expected_systemd_unit)

        translation_output = args.output_dir / "translation_gate.recheck.json"
        translation_stdout = args.output_dir / "translation_recheck.stdout.txt"
        translation_stderr = args.output_dir / "translation_recheck.stderr.txt"
        translation_argv = [
            python_pin["fd_path"],
            "-I",
            str(snapshot_dir / "translation_gate.py"),
            "--pb-authority",
            str(snapshot_dir / "pb_authority.json"),
            "--geometry-admission",
            str(snapshot_dir / "geometry_admission.json"),
            "--instance",
            str(snapshot_dir / "strict_instance.json"),
            "--build-dir",
            str(build_snapshot_dir),
            "--output",
            str(translation_output),
        ]
        translation_exit, translation_elapsed = run_timed(
            translation_argv,
            translation_stdout,
            translation_stderr,
            TRANSLATION_SECONDS,
            pass_fds=(python_pin["fd"],),
        )
        require(translation_exit == 0, "translation replay exited nonzero")
        translation_recheck, translation_recheck_identity, _ = load_json(
            translation_output,
            "translation replay",
        )
        require(
            translation_recheck.get("schema_version") == "b1_sidewise_ceiling_translation_gate_v1"
            and translation_recheck.get("status") == "PASS"
            and translation_recheck.get("decision") == "FORMAL_RUN_AUTHORIZED"
            and translation_recheck.get("formal_run_authorized") is True
            and translation_recheck.get("corpus_errors") == []
            and all(translation_recheck.get("checks", {}).values()),
            "translation replay semantics failed",
        )
        add_member(members, args.output_dir, translation_recheck_identity)
        for path, label in (
            (translation_stdout, "translation stdout"),
            (translation_stderr, "translation stderr"),
        ):
            _, identity = snapshot_regular(
                path,
                label,
                collect=False,
            )
            add_member(members, args.output_dir, identity)
        verify_pinned_executable(python_pin, "fixed Python")

        available_before_solver = free_bytes(args.output_dir)
        require(
            available_before_solver >= REQUIRED_FREE,
            "disk gate failed before RoundingSat",
        )
        proof_path = args.output_dir / "roundingsat.proof.pbp"
        proof_seed_identity = write_once(proof_path, b"")
        del proof_seed_identity
        solver_stdout = args.output_dir / "roundingsat.stdout.txt"
        solver_stderr = args.output_dir / "roundingsat.stderr.txt"
        solver_logical_argv = [
            roundingsat_pin["logical_path"],
            f"--proof-log={proof_path}",
            f"--time-limit={ROUNDINGSAT_SECONDS}",
            str(formula_path),
        ]
        solver_argv = [
            roundingsat_pin["fd_path"],
            *solver_logical_argv[1:],
        ]
        solver_exit, solver_elapsed, solver_stop = run_roundingsat(
            solver_argv,
            solver_stdout,
            solver_stderr,
            proof_path,
            pass_fds=(roundingsat_pin["fd"],),
        )
        require(solver_stop is None, f"RoundingSat stopped: {solver_stop}")
        require(solver_exit == 0, "RoundingSat exited nonzero")
        solver_stdout_raw, solver_stdout_identity = snapshot_regular(
            solver_stdout,
            "RoundingSat stdout",
            max_bytes=TEXT_LIMIT,
        )
        _, solver_stderr_identity = snapshot_regular(
            solver_stderr,
            "RoundingSat stderr",
            collect=False,
        )
        require(
            solver_stdout_raw is not None,
            "RoundingSat stdout snapshot failed",
        )
        solver_statuses = [
            match.group(1)
            for line in solver_stdout_raw.decode(
                "utf-8",
                errors="replace",
            ).splitlines()
            if (match := ROUNDINGSAT_STATUS.fullmatch(line)) is not None
        ]
        require(
            solver_statuses == ["UNSATISFIABLE"],
            "RoundingSat status protocol failed",
        )
        _, proof_identity = snapshot_regular(
            proof_path,
            "RoundingSat proof",
            collect=False,
            max_bytes=PROOF_LIMIT,
        )
        require(
            0 < proof_identity["size_bytes"] <= PROOF_LIMIT,
            "RoundingSat proof is empty or over cap",
        )
        add_member(members, args.output_dir, solver_stdout_identity)
        add_member(members, args.output_dir, solver_stderr_identity)
        add_member(members, args.output_dir, proof_identity)
        verify_pinned_executable(roundingsat_pin, "RoundingSat")
        require(
            free_bytes(args.output_dir) >= LOW_WATER,
            "artifact low-water crossed after RoundingSat",
        )

        verifier_stdout = args.output_dir / "veripb.stdout.txt"
        verifier_stderr = args.output_dir / "veripb.stderr.txt"
        verifier_logical_argv = [
            veripb_pin["logical_path"],
            "--opb",
            "--stats",
            str(formula_path),
            str(proof_path),
        ]
        verifier_argv = [
            veripb_pin["fd_path"],
            *verifier_logical_argv[1:],
        ]
        verifier_exit, verifier_elapsed = run_timed(
            verifier_argv,
            verifier_stdout,
            verifier_stderr,
            VERIPB_SECONDS,
            pass_fds=(veripb_pin["fd"],),
        )
        verifier_stdout_raw, verifier_stdout_identity = snapshot_regular(
            verifier_stdout,
            "VeriPB stdout",
            max_bytes=TEXT_LIMIT,
        )
        verifier_stderr_raw, verifier_stderr_identity = snapshot_regular(
            verifier_stderr,
            "VeriPB stderr",
            max_bytes=TEXT_LIMIT,
        )
        require(
            verifier_stdout_raw is not None and verifier_stderr_raw is not None,
            "VeriPB output snapshot failed",
        )
        verifier_text = verifier_stdout_raw.decode(
            "utf-8",
            errors="replace",
        )
        verifier_lines = [line for line in verifier_text.splitlines() if line.startswith("s ")]
        require(verifier_exit == 0, "VeriPB exited nonzero")
        require(
            len(verifier_lines) == 1 and VERIPB_SUCCESS.fullmatch(verifier_lines[0]) is not None,
            "VeriPB did not uniquely verify UNSAT",
        )
        combined_verifier = verifier_text + "\n" + verifier_stderr_raw.decode("utf-8", errors="replace")
        require(
            not any(marker in combined_verifier for marker in VERIPB_ERROR_MARKERS),
            "VeriPB output contains an error marker",
        )
        add_member(members, args.output_dir, verifier_stdout_identity)
        add_member(members, args.output_dir, verifier_stderr_identity)
        verify_pinned_executable(veripb_pin, "VeriPB")
        require(
            free_bytes(args.output_dir) >= LOW_WATER,
            "artifact low-water crossed after VeriPB",
        )

        _, current_authority_identity = snapshot_regular(
            args.authority,
            "SMM3 authority final replay",
            collect=False,
        )
        _, current_selection_identity = snapshot_regular(
            args.selection,
            "SMM3 selection final replay",
            collect=False,
        )
        require(
            current_authority_identity == authority_identity,
            "SMM3 authority drifted during payload",
        )
        require(
            current_selection_identity == selection_identity,
            "SMM3 selection drifted during payload",
        )
        for name in BUILD_MEMBERS:
            _, current = snapshot_pinned(
                build_expected[name],
                f"historical build {name} final replay",
                collect=False,
            )
            require(
                current == build_identities[name],
                f"historical build {name} drifted during payload",
            )

        receipt = {
            "schema_version": RECEIPT_SCHEMA,
            "status": "VERIFIED",
            "attempt": ATTEMPT,
            "purpose": "formal",
            "run_nonce": run_nonce,
            "proof_status": "VERIFIED UNSATISFIABLE",
            "claim": ("machine_verified_two_oriented_ceiling_selectors_unsat_given_admitted_smm209"),
            "expected_systemd_unit": args.expected_systemd_unit,
            "completed_monotonic_ns": time.monotonic_ns(),
            "resource_contract": resource_contract,
            "timing_contract": timing_contract,
            "cgroup_membership": cgroup_receipt,
            "inputs": {
                "authority": authority_identity,
                "selection": selection_identity,
                "historical_pb_authority": pb_identity,
                "historical_geometry_admission": geometry_identity,
                "strict_instance": strict_identity,
                "historical_translation_gate": translation_identity,
                "historical_build_files": build_identities,
                "execution_snapshots": snapshot_identities,
                "translation_recheck": translation_recheck_identity,
            },
            "tools": {
                "formal_payload": self_identity,
                "translation_gate": translation_tool_identity,
                "fixed_python": {
                    "logical_path": python_pin["logical_path"],
                    "target": python_pin["identity"],
                    "execution": "pinned_fd",
                },
                "roundingsat": {
                    "logical_path": roundingsat_pin["logical_path"],
                    "target": roundingsat_pin["identity"],
                    "execution": "pinned_fd",
                },
                "veripb": {
                    "logical_path": veripb_pin["logical_path"],
                    "target": veripb_pin["identity"],
                    "execution": "pinned_fd",
                },
            },
            "formula": formula_identity,
            "proof": proof_identity,
            "translation_replay": {
                "logical_argv": [
                    python_pin["logical_path"],
                    "-I",
                    str(snapshot_dir / "translation_gate.py"),
                    *translation_argv[3:],
                ],
                "executed_from_pinned_fd": True,
                "exit_code": translation_exit,
                "elapsed_milliseconds": translation_elapsed,
                "status": "PASS",
            },
            "solver": {
                "logical_argv": solver_logical_argv,
                "executed_from_pinned_fd": True,
                "exit_code": solver_exit,
                "elapsed_milliseconds": solver_elapsed,
                "status_lines": solver_statuses,
                "time_limit_seconds": ROUNDINGSAT_SECONDS,
                "monitor_limit_seconds": ROUNDINGSAT_MONITOR_SECONDS,
            },
            "verifier": {
                "logical_argv": verifier_logical_argv,
                "executed_from_pinned_fd": True,
                "exit_code": verifier_exit,
                "elapsed_milliseconds": verifier_elapsed,
                "status_lines": verifier_lines,
                "time_limit_seconds": VERIPB_SECONDS,
            },
            "artifact_contract": {
                "proof_limit_bytes": PROOF_LIMIT,
                "low_water_bytes": LOW_WATER,
                "required_free_before_formal_bytes": REQUIRED_FREE,
                "free_before_solver_bytes": available_before_solver,
                "free_after_verifier_bytes": free_bytes(args.output_dir),
            },
            "ledger_candidate": {
                "old_upper": [1188, 22],
                "new_upper": [1188, 18],
                "lower": "absent",
            },
            "upper_bound_update_authorized": False,
            "awaiting_terminal_envelope": True,
            "production_certified": False,
        }
        receipt_raw = json_bytes(receipt)
        receipt_identity = write_once(
            args.output_dir / "internal_formal_receipt.json",
            receipt_raw,
        )
        add_member(members, args.output_dir, receipt_identity)
        manifest_raw = "".join(f"{members[name]['sha256']}  {name}\n" for name in sorted(members)).encode("ascii")
        write_once(args.output_dir / "SHA256SUMS", manifest_raw)
        result = {
            "status": "VERIFIED",
            "attempt": ATTEMPT,
            "proof_status": receipt["proof_status"],
            "internal_receipt": receipt_identity,
            "upper_bound_update_authorized": False,
            "awaiting_terminal_envelope": True,
        }
    except Exception as exc:
        failure = {
            "schema_version": "b1_sidewise_smm3_internal_formal_failure_v1",
            "status": "FAIL_CLOSED",
            "attempt": ATTEMPT,
            "error": str(exc),
            "upper_bound_update_authorized": False,
            "awaiting_terminal_envelope": False,
            "ledger": {"upper": [1188, 22], "lower": "absent"},
            "production_certified": False,
        }
        if output_created:
            failure_path = args.output_dir / "formal_failure.json"
            if not path_exists(failure_path):
                try:
                    write_once(failure_path, json_bytes(failure))
                except Exception:
                    pass
        print(json.dumps(failure, sort_keys=True))
        return 2
    finally:
        close_pinned_executable(veripb_pin)
        close_pinned_executable(roundingsat_pin)
        close_pinned_executable(python_pin)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
