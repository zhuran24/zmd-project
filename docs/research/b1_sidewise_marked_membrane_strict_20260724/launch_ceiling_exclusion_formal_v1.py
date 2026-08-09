#!/usr/bin/env python3
"""Preflight and externally observe the unique formal systemd attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time
from typing import Any


HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
AUTHORITY_SCHEMA = "b1_sidewise_pb_pre_run_authority_v1"
MEMORY_HIGH = 35 * 1024**3
MEMORY_MAX = 39 * 1024**3
MEMORY_SWAP_MAX = 16 * 1024**3
PROOF_LIMIT = 5_000_000_000
LOW_WATER = 10 * 1024**3
REQUIRED_FREE = LOW_WATER + PROOF_LIMIT


class LaunchError(RuntimeError):
    """Raised when preflight or the unique launch must fail closed."""


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def snapshot(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    fd = os.open(
        path.absolute(),
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise LaunchError(f"{label}: not regular")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise LaunchError(f"{label}: changed during read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise LaunchError(f"{label}: short read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
    }


def resolved_executable(path: Path, label: str) -> dict[str, Any]:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise LaunchError(f"{label}: cannot resolve: {exc}") from exc
    raw, target = snapshot(resolved, f"{label} target")
    del raw
    return {
        "path": str(path.absolute()),
        "resolved_path": str(resolved),
        "target": target,
    }


def parse_json(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise LaunchError(f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise LaunchError(f"{label}: non-integer JSON {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LaunchError(f"{label}: malformed JSON: {exc}") from exc


def require(ok: bool, message: str) -> None:
    if not ok:
        raise LaunchError(message)


def identity_match(
    actual: dict[str, Any],
    expected: dict[str, Any],
    label: str,
) -> None:
    require(
        all(
            actual.get(field) == expected.get(field)
            for field in ("size_bytes", "sha256", "mode_octal")
        ),
        f"{label}: byte identity drifted",
    )


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode()


def write_once(path: Path, raw: bytes) -> None:
    fd = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o644,
    )
    try:
        offset = 0
        while offset < len(raw):
            count = os.write(fd, raw[offset:])
            if count <= 0:
                raise LaunchError("short output write")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)


def free_bytes(path: Path) -> int:
    stats = os.statvfs(path)
    return stats.f_bavail * stats.f_frsize


def load_authority(
    authority_path: Path,
    self_identity: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, identity = snapshot(authority_path, "PB authority")
    authority = parse_json(raw, "PB authority")
    require(
        isinstance(authority, dict)
        and authority.get("schema_version") == AUTHORITY_SCHEMA
        and authority.get("status") == "PB_PRE_RUN_AUTHORITY_PASS"
        and authority.get("head") == HEAD,
        "PB authority failed",
    )
    tools = authority.get("tools")
    require(isinstance(tools, dict), "authority tools missing")
    identity_match(self_identity, tools.get("formal_launcher", {}), "launcher")
    return authority, identity


def validate_common(
    args: argparse.Namespace,
    authority: dict[str, Any],
) -> dict[str, Any]:
    tools = authority.get("tools")
    binaries = authority.get("binaries")
    require(
        isinstance(tools, dict) and isinstance(binaries, dict),
        "authority tools/binaries missing",
    )
    _, worker_identity = snapshot(args.worker, "formal worker")
    _, roundingsat_identity = snapshot(args.roundingsat, "RoundingSat")
    _, veripb_identity = snapshot(args.veripb, "VeriPB")
    _, translation_tool_identity = snapshot(
        args.translation_tool, "translation tool"
    )
    identity_match(
        worker_identity, tools.get("formal_worker", {}), "formal worker"
    )
    identity_match(
        translation_tool_identity,
        tools.get("translation_gate", {}),
        "translation tool",
    )
    identity_match(
        roundingsat_identity,
        binaries.get("roundingsat", {}),
        "RoundingSat",
    )
    identity_match(veripb_identity, binaries.get("veripb", {}), "VeriPB")
    python_identity = resolved_executable(args.fixed_python, "fixed Python")
    require(
        python_identity == binaries.get("fixed_python"),
        "fixed Python resolution/bytes drifted",
    )
    _, geometry_identity = snapshot(
        args.geometry_admission, "geometry admission"
    )
    identity_match(
        geometry_identity,
        authority.get("geometry_admission", {}),
        "geometry admission",
    )
    _, strict_identity = snapshot(args.instance, "strict instance")
    identity_match(
        strict_identity,
        authority.get("strict_instance", {}),
        "strict instance",
    )
    translation_raw, translation_identity = snapshot(
        args.translation_gate, "translation gate"
    )
    translation = parse_json(translation_raw, "translation gate")
    require(
        isinstance(translation, dict)
        and translation.get("status") == "PASS"
        and translation.get("decision") == "FORMAL_RUN_AUTHORIZED"
        and translation.get("formal_run_authorized") is True
        and translation.get("corpus_errors") == []
        and all(translation.get("checks", {}).values()),
        "translation gate failed",
    )
    build_files: dict[str, Any] = {}
    for name in (
        "formula.opb",
        "variable_map.json",
        "encoder.meta.json",
        "build_record.json",
        "estimate.json",
        "SHA256SUMS",
    ):
        _, identity = snapshot(args.build_dir / name, name)
        build_files[name] = identity
    require(
        translation.get("build_inputs") == build_files,
        "translation gate does not bind current build bytes",
    )
    return {
        "worker": worker_identity,
        "roundingsat": roundingsat_identity,
        "veripb": veripb_identity,
        "translation_tool": translation_tool_identity,
        "fixed_python": python_identity,
        "geometry_admission": geometry_identity,
        "strict_instance": strict_identity,
        "translation_gate": translation_identity,
        "build_files": build_files,
    }


def publish_preflight(
    args: argparse.Namespace,
    authority_identity: dict[str, Any],
    identities: dict[str, Any],
    self_identity: dict[str, Any],
) -> dict[str, Any]:
    output = args.preflight_output
    require(output is not None, "preflight output missing")
    require(not output.exists() and not output.is_symlink(), "preflight exists")
    require(
        output.parent.is_dir() and not output.parent.is_symlink(),
        "preflight parent is not a real directory",
    )
    available = free_bytes(args.build_dir)
    user_manager = subprocess.run(
        ["systemctl", "--user", "is-system-running"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    systemd_run = subprocess.run(
        ["systemd-run", "--user", "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    require(
        available >= REQUIRED_FREE,
        f"disk gate failed: {available} < {REQUIRED_FREE}",
    )
    require(
        user_manager.returncode in {0, 1}
        and user_manager.stdout.strip() in {"running", "degraded"},
        "user systemd manager unavailable",
    )
    require(systemd_run.returncode == 0, "systemd-run unavailable")
    payload = {
        "schema_version": "b1_sidewise_formal_preflight_v1",
        "status": "PASS",
        "pb_authority": authority_identity,
        "launcher": self_identity,
        "identities": identities,
        "disk": {
            "available_bytes": available,
            "proof_limit_bytes": PROOF_LIMIT,
            "low_water_bytes": LOW_WATER,
            "required_free_bytes": REQUIRED_FREE,
        },
        "resource_contract": {
            "memory_high_bytes": MEMORY_HIGH,
            "memory_max_bytes": MEMORY_MAX,
            "memory_swap_max_bytes": MEMORY_SWAP_MAX,
            "oom_policy": "continue",
            "kill_mode": "control-group",
            "send_sigkill": "yes",
            "single_worker": True,
        },
        "systemd": {
            "manager_exit_code": user_manager.returncode,
            "manager_stdout": user_manager.stdout,
            "manager_stderr": user_manager.stderr,
            "systemd_run_exit_code": systemd_run.returncode,
            "systemd_run_stdout": systemd_run.stdout,
            "systemd_run_stderr": systemd_run.stderr,
        },
        "formal_launch_permitted": True,
        "upper_bound_update_authorized": False,
        "ledger": {"upper": [1188, 22], "lower": "absent"},
    }
    raw = json_bytes(payload)
    write_once(output, raw)
    return {
        "status": payload["status"],
        "formal_launch_permitted": True,
        "output": str(output),
        "size_bytes": len(raw),
        "sha256": sha(raw),
        "available_bytes": available,
    }


def systemd_show(unit: str, properties: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in properties:
        argv = [
            "systemctl",
            "--user",
            "show",
            unit,
            f"--property={name}",
            "--value",
        ]
        run = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        result[name] = {
            "argv": argv,
            "exit_code": run.returncode,
            "stdout": run.stdout,
            "stderr": run.stderr,
            "value": run.stdout.strip(),
        }
    return result


def publish_launch(
    args: argparse.Namespace,
    authority_identity: dict[str, Any],
    identities: dict[str, Any],
    self_identity: dict[str, Any],
) -> dict[str, Any]:
    require(args.preflight is not None, "launch requires preflight")
    preflight_raw, preflight_identity = snapshot(args.preflight, "preflight")
    preflight = parse_json(preflight_raw, "preflight")
    require(
        isinstance(preflight, dict)
        and preflight.get("schema_version")
        == "b1_sidewise_formal_preflight_v1"
        and preflight.get("status") == "PASS"
        and preflight.get("formal_launch_permitted") is True
        and preflight.get("pb_authority") == authority_identity
        and preflight.get("identities") == identities,
        "preflight replay failed",
    )
    require(
        free_bytes(args.build_dir) >= REQUIRED_FREE,
        "disk gate drifted after preflight",
    )
    require(args.launch_dir is not None, "launch directory missing")
    require(
        not args.launch_dir.exists() and not args.launch_dir.is_symlink(),
        "launch directory exists",
    )
    require(
        not args.output_dir.exists() and not args.output_dir.is_symlink(),
        "formal output exists",
    )
    require(
        not args.reservation.exists() and not args.reservation.is_symlink(),
        "formal attempt already reserved",
    )
    args.launch_dir.mkdir(mode=0o755)
    worker_argv = [
        str(args.worker),
        "--pb-authority",
        str(args.pb_authority),
        "--geometry-admission",
        str(args.geometry_admission),
        "--instance",
        str(args.instance),
        "--build-dir",
        str(args.build_dir),
        "--translation-gate",
        str(args.translation_gate),
        "--preflight",
        str(args.preflight),
        "--reservation",
        str(args.reservation),
        "--output-dir",
        str(args.output_dir),
        "--expected-systemd-unit",
        args.unit,
        "--roundingsat",
        str(args.roundingsat),
        "--veripb",
        str(args.veripb),
        "--fixed-python",
        str(args.fixed_python),
        "--translation-tool",
        str(args.translation_tool),
    ]
    unit_argv = [
        "systemd-run",
        "--user",
        "--wait",
        f"--unit={args.unit}",
        "--property=Type=exec",
        f"--property=MemoryHigh={MEMORY_HIGH}",
        f"--property=MemoryMax={MEMORY_MAX}",
        f"--property=MemorySwapMax={MEMORY_SWAP_MAX}",
        "--property=OOMPolicy=continue",
        "--property=KillMode=control-group",
        "--property=SendSIGKILL=yes",
        str(args.fixed_python),
        *worker_argv,
    ]
    reservation = {
        "schema_version": "b1_sidewise_formal_attempt_reservation_v1",
        "attempt": "a001",
        "unit": args.unit,
        "pb_authority": authority_identity,
        "preflight": preflight_identity,
        "launcher": self_identity,
        "worker_argv": worker_argv,
        "systemd_argv": unit_argv,
        "resource_contract": preflight["resource_contract"],
        "upper_bound_update_authorized": False,
    }
    reservation_raw = json_bytes(reservation)
    write_once(args.reservation, reservation_raw)
    started = time.monotonic()
    run = subprocess.run(
        unit_argv,
        check=False,
        capture_output=True,
        timeout=4200,
    )
    elapsed_ms = round((time.monotonic() - started) * 1000)
    write_once(args.launch_dir / "systemd-run.stdout.txt", run.stdout)
    write_once(args.launch_dir / "systemd-run.stderr.txt", run.stderr)
    terminal = systemd_show(
        args.unit,
        [
            "ActiveState",
            "SubState",
            "Result",
            "ExecMainCode",
            "ExecMainStatus",
            "MemoryHigh",
            "MemoryMax",
            "MemorySwapMax",
            "OOMPolicy",
            "KillMode",
            "SendSIGKILL",
            "ControlGroup",
        ],
    )
    expected = {
        "ActiveState": "inactive",
        "SubState": "dead",
        "Result": "success",
        "ExecMainStatus": "0",
        "MemoryHigh": str(MEMORY_HIGH),
        "MemoryMax": str(MEMORY_MAX),
        "MemorySwapMax": str(MEMORY_SWAP_MAX),
        "OOMPolicy": "continue",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
    }
    terminal_pass = run.returncode == 0 and all(
        terminal[name]["exit_code"] == 0
        and terminal[name]["value"] == value
        for name, value in expected.items()
    )
    control_group = terminal["ControlGroup"]["value"]
    cgroup_procs: list[int] = []
    if control_group:
        procs_path = Path("/sys/fs/cgroup") / control_group.lstrip("/") / "cgroup.procs"
        if procs_path.is_file():
            cgroup_procs = [
                int(line)
                for line in procs_path.read_text().splitlines()
                if line.strip()
            ]
    terminal_pass = terminal_pass and not cgroup_procs
    internal_path = args.output_dir / "internal_formal_receipt.json"
    internal_identity = None
    if internal_path.is_file() and not internal_path.is_symlink():
        _, internal_identity = snapshot(internal_path, "internal receipt")
    payload = {
        "schema_version": "b1_sidewise_formal_launch_receipt_v1",
        "status": "PASS" if terminal_pass and internal_identity else "FAIL_CLOSED",
        "pb_authority": authority_identity,
        "preflight": preflight_identity,
        "reservation": {
            "path": str(args.reservation.absolute()),
            "size_bytes": len(reservation_raw),
            "sha256": sha(reservation_raw),
            "mode_octal": "0644",
        },
        "launcher": self_identity,
        "systemd_argv": unit_argv,
        "systemd_run_exit_code": run.returncode,
        "elapsed_milliseconds": elapsed_ms,
        "terminal": terminal,
        "cgroup_procs_after_terminal": cgroup_procs,
        "internal_formal_receipt": internal_identity,
        "upper_bound_update_authorized": False,
        "ledger": {"upper": [1188, 22], "lower": "absent"},
        "production_certified": False,
    }
    receipt_raw = json_bytes(payload)
    write_once(args.launch_dir / "launch_receipt.json", receipt_raw)
    if payload["status"] != "PASS":
        raise LaunchError("systemd terminal envelope or internal receipt failed")
    return {
        "status": "PASS",
        "output": str(args.launch_dir / "launch_receipt.json"),
        "size_bytes": len(receipt_raw),
        "sha256": sha(receipt_raw),
        "internal_receipt": internal_identity,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pb-authority", type=Path, required=True)
    parser.add_argument("--geometry-admission", type=Path, required=True)
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--translation-gate", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--roundingsat", type=Path, required=True)
    parser.add_argument("--veripb", type=Path, required=True)
    parser.add_argument("--fixed-python", type=Path, required=True)
    parser.add_argument("--translation-tool", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight-output", type=Path)
    modes.add_argument("--launch", action="store_true")
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--reservation", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--launch-dir", type=Path)
    parser.add_argument("--unit")
    args = parser.parse_args()
    try:
        _, self_identity = snapshot(Path(__file__), "formal launcher")
        authority, authority_identity = load_authority(
            args.pb_authority,
            self_identity,
        )
        identities = validate_common(args, authority)
        if args.preflight_output is not None:
            result = publish_preflight(
                args,
                authority_identity,
                identities,
                self_identity,
            )
        else:
            require(
                all(
                    value is not None
                    for value in (
                        args.preflight,
                        args.reservation,
                        args.output_dir,
                        args.launch_dir,
                        args.unit,
                    )
                ),
                "launch arguments incomplete",
            )
            result = publish_launch(
                args,
                authority_identity,
                identities,
                self_identity,
            )
    except (
        OSError,
        LaunchError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL_CLOSED",
                    "error": str(exc),
                    "upper_bound_update_authorized": False,
                },
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
