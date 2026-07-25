#!/usr/bin/env python3
"""Single-worker RoundingSat to VeriPB worker for the ceiling OPB."""

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


HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
AUTHORITY_SCHEMA = "b1_sidewise_pb_pre_run_authority_v1"
MEMORY_HIGH = 35 * 1024**3
MEMORY_MAX = 39 * 1024**3
MEMORY_SWAP_MAX = 16 * 1024**3
PROOF_LIMIT = 5_000_000_000
LOW_WATER = 10 * 1024**3
REQUIRED_FREE = LOW_WATER + PROOF_LIMIT
ROUNDINGSAT_STATUS = re.compile(r"^s (UNSATISFIABLE|SATISFIABLE|UNKNOWN)\s*$")
VERIPB_SUCCESS = re.compile(r"^s VERIFIED UNSATISFIABLE\s*$")
ERROR_MARKERS = (
    "Error:",
    "Checking error",
    "panic",
    "failed",
    "unsupported",
)


class FormalError(RuntimeError):
    """Raised when the internal formal worker must fail closed."""


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
            raise FormalError(f"{label}: not regular")
        chunks: list[bytes] = []
        while True:
            block = os.read(fd, 1 << 20)
            if not block:
                break
            chunks.append(block)
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
        raise FormalError(f"{label}: changed during read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise FormalError(f"{label}: short read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
    }


def parse_json(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise FormalError(f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise FormalError(f"{label}: non-integer JSON {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FormalError(f"{label}: malformed JSON: {exc}") from exc


def require(ok: bool, message: str) -> None:
    if not ok:
        raise FormalError(message)


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
                raise FormalError("short output write")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode()


def systemd_value(unit: str, property_name: str) -> dict[str, Any]:
    argv = [
        "systemctl",
        "--user",
        "show",
        unit,
        f"--property={property_name}",
        "--value",
    ]
    run = subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "argv": argv,
        "exit_code": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
        "value": run.stdout.strip(),
    }


def cgroup_state() -> dict[str, Any]:
    lines = Path("/proc/self/cgroup").read_text().splitlines()
    unified = [line.split("::", 1)[1] for line in lines if "::" in line]
    require(len(unified) == 1, "cannot resolve unified cgroup")
    relative = unified[0].lstrip("/")
    root = Path("/sys/fs/cgroup") / relative
    require(root.is_dir(), "current cgroup directory missing")

    def read_text(name: str) -> str | None:
        path = root / name
        return path.read_text().strip() if path.is_file() else None

    events_raw = read_text("memory.events")
    events: dict[str, int] = {}
    if events_raw is not None:
        for line in events_raw.splitlines():
            key, value = line.split()
            events[key] = int(value)
    return {
        "relative_path": "/" + relative,
        "absolute_path": str(root),
        "memory_current": read_text("memory.current"),
        "memory_peak": read_text("memory.peak"),
        "memory_swap_current": read_text("memory.swap.current"),
        "memory_events": events,
    }


def verify_contract(unit: str) -> dict[str, Any]:
    expected = {
        "MemoryHigh": str(MEMORY_HIGH),
        "MemoryMax": str(MEMORY_MAX),
        "MemorySwapMax": str(MEMORY_SWAP_MAX),
        "OOMPolicy": "continue",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
    }
    properties = {
        key: systemd_value(unit, key) for key in expected
    }
    require(
        all(
            properties[key]["exit_code"] == 0
            and properties[key]["value"] == value
            for key, value in expected.items()
        ),
        "systemd resource contract mismatch",
    )
    cgroup = cgroup_state()
    require(unit in cgroup["relative_path"], "worker is outside expected unit")
    return {"expected": expected, "properties": properties, "cgroup": cgroup}


def free_bytes(path: Path) -> int:
    stats = os.statvfs(path)
    return stats.f_bavail * stats.f_frsize


def run_monitored(
    argv: list[str],
    proof: Path,
    timeout_seconds: int,
) -> tuple[int, bytes, bytes, float, str | None]:
    started = time.monotonic()
    process = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    reason: str | None = None
    while process.poll() is None:
        elapsed = time.monotonic() - started
        if elapsed > timeout_seconds:
            reason = "wall_timeout"
        elif proof.exists() and proof.stat().st_size > PROOF_LIMIT:
            reason = "proof_size_limit_exceeded"
        if reason is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            break
        time.sleep(0.05)
    stdout, stderr = process.communicate()
    return (
        process.returncode,
        stdout,
        stderr,
        time.monotonic() - started,
        reason,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pb-authority", type=Path, required=True)
    parser.add_argument("--geometry-admission", type=Path, required=True)
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--translation-gate", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--reservation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-systemd-unit", required=True)
    parser.add_argument("--roundingsat", type=Path, required=True)
    parser.add_argument("--veripb", type=Path, required=True)
    parser.add_argument("--fixed-python", type=Path, required=True)
    parser.add_argument("--translation-tool", type=Path, required=True)
    args = parser.parse_args()
    output_created = False
    failure_context: dict[str, Any] = {}
    try:
        authority_raw, authority_identity = snapshot(
            args.pb_authority, "PB authority"
        )
        authority = parse_json(authority_raw, "PB authority")
        require(
            isinstance(authority, dict)
            and authority.get("schema_version") == AUTHORITY_SCHEMA
            and authority.get("status") == "PB_PRE_RUN_AUTHORITY_PASS"
            and authority.get("head") == HEAD,
            "PB authority failed",
        )
        tools = authority.get("tools")
        binaries = authority.get("binaries")
        require(
            isinstance(tools, dict) and isinstance(binaries, dict),
            "PB authority tools/binaries missing",
        )
        _, self_identity = snapshot(Path(__file__), "formal worker")
        identity_match(
            self_identity, tools.get("formal_worker", {}), "formal worker"
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
        _, rounding_identity = snapshot(args.roundingsat, "RoundingSat")
        _, veripb_identity = snapshot(args.veripb, "VeriPB")
        identity_match(
            rounding_identity, binaries.get("roundingsat", {}), "RoundingSat"
        )
        identity_match(veripb_identity, binaries.get("veripb", {}), "VeriPB")
        _, translation_tool_identity = snapshot(
            args.translation_tool, "translation tool"
        )
        identity_match(
            translation_tool_identity,
            tools.get("translation_gate", {}),
            "translation tool",
        )
        preflight_raw, preflight_identity = snapshot(
            args.preflight, "formal preflight"
        )
        preflight = parse_json(preflight_raw, "formal preflight")
        require(
            isinstance(preflight, dict)
            and preflight.get("schema_version")
            == "b1_sidewise_formal_preflight_v1"
            and preflight.get("status") == "PASS"
            and preflight.get("formal_launch_permitted") is True,
            "formal preflight failed",
        )
        reservation_raw, reservation_identity = snapshot(
            args.reservation, "formal reservation"
        )
        reservation = parse_json(reservation_raw, "formal reservation")
        require(
            isinstance(reservation, dict)
            and reservation.get("schema_version")
            == "b1_sidewise_formal_attempt_reservation_v1"
            and reservation.get("attempt") == "a001"
            and reservation.get("unit") == args.expected_systemd_unit
            and reservation.get("worker_argv") == sys.argv,
            "formal reservation/argv mismatch",
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
            and translation.get("corpus_errors") == [],
            "translation gate failed",
        )
        formula_raw, formula_build_identity = snapshot(
            args.build_dir / "formula.opb", "formula"
        )
        current_free = free_bytes(args.build_dir)
        require(
            current_free >= REQUIRED_FREE,
            f"disk preflight failed: {current_free} < {REQUIRED_FREE}",
        )
        contract_start = verify_contract(args.expected_systemd_unit)
        start_events = contract_start["cgroup"]["memory_events"]
        require(
            start_events.get("oom", 0) == 0
            and start_events.get("oom_kill", 0) == 0,
            "cgroup already records OOM",
        )
        if args.output_dir.exists() or args.output_dir.is_symlink():
            raise FormalError("formal output exists")
        require(
            args.output_dir.parent.is_dir()
            and not args.output_dir.parent.is_symlink(),
            "formal output parent is not a real directory",
        )
        args.output_dir.mkdir(mode=0o755)
        output_created = True
        formula_path = args.output_dir / "formula.opb"
        write_once(formula_path, formula_raw)

        replay_path = args.output_dir / "translation_gate.recheck.json"
        replay_argv = [
            str(args.fixed_python),
            str(args.translation_tool),
            "--pb-authority",
            str(args.pb_authority),
            "--geometry-admission",
            str(args.geometry_admission),
            "--instance",
            str(args.instance),
            "--build-dir",
            str(args.build_dir),
            "--output",
            str(replay_path),
        ]
        replay_run = subprocess.run(
            replay_argv,
            check=False,
            capture_output=True,
            timeout=300,
        )
        write_once(
            args.output_dir / "translation_recheck.stdout.txt",
            replay_run.stdout,
        )
        write_once(
            args.output_dir / "translation_recheck.stderr.txt",
            replay_run.stderr,
        )
        require(replay_run.returncode == 0, "translation recheck failed")
        replay_raw, replay_identity = snapshot(
            replay_path, "translation recheck"
        )
        replay = parse_json(replay_raw, "translation recheck")
        require(
            isinstance(replay, dict)
            and replay.get("status") == "PASS"
            and replay.get("decision") == "FORMAL_RUN_AUTHORIZED",
            "translation recheck semantics failed",
        )

        version_records: dict[str, Any] = {}
        for name, argv in (
            ("roundingsat", [str(args.roundingsat), "--version"]),
            ("veripb", [str(args.veripb), "--version"]),
        ):
            run = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                timeout=30,
            )
            version_records[name] = {
                "argv": argv,
                "exit_code": run.returncode,
                "stdout": run.stdout.decode("utf-8", errors="replace"),
                "stderr": run.stderr.decode("utf-8", errors="replace"),
            }

        proof_path = args.output_dir / "roundingsat.proof.pbp"
        solver_argv = [
            str(args.roundingsat),
            f"--proof-log={proof_path}",
            "--time-limit=3600",
            str(formula_path),
        ]
        solver_exit, solver_stdout, solver_stderr, solver_elapsed, stop_reason = (
            run_monitored(solver_argv, proof_path, 3900)
        )
        write_once(args.output_dir / "roundingsat.stdout.txt", solver_stdout)
        write_once(args.output_dir / "roundingsat.stderr.txt", solver_stderr)
        require(stop_reason is None, f"solver stopped: {stop_reason}")
        statuses = [
            match.group(1)
            for line in solver_stdout.decode(
                "utf-8", errors="replace"
            ).splitlines()
            if (match := ROUNDINGSAT_STATUS.fullmatch(line)) is not None
        ]
        require(statuses == ["UNSATISFIABLE"], "RoundingSat status protocol failed")
        proof_raw, proof_identity = snapshot(proof_path, "proof")
        require(
            0 < len(proof_raw) <= PROOF_LIMIT,
            "proof empty or over cap at completion",
        )
        require(free_bytes(args.output_dir) >= LOW_WATER, "disk low-water crossed")

        verifier_argv = [
            str(args.veripb),
            "--opb",
            "--stats",
            str(formula_path),
            str(proof_path),
        ]
        verifier_started = time.monotonic()
        verifier_run = subprocess.run(
            verifier_argv,
            check=False,
            capture_output=True,
            timeout=3600,
        )
        verifier_elapsed = time.monotonic() - verifier_started
        write_once(args.output_dir / "veripb.stdout.txt", verifier_run.stdout)
        write_once(args.output_dir / "veripb.stderr.txt", verifier_run.stderr)
        verifier_text = verifier_run.stdout.decode("utf-8", errors="replace")
        verifier_lines = [
            line for line in verifier_text.splitlines() if line.startswith("s ")
        ]
        require(
            len(verifier_lines) == 1
            and VERIPB_SUCCESS.fullmatch(verifier_lines[0]) is not None,
            "VeriPB did not uniquely verify UNSAT",
        )
        combined_verifier = (
            verifier_text
            + "\n"
            + verifier_run.stderr.decode("utf-8", errors="replace")
        )
        require(
            not any(marker in combined_verifier for marker in ERROR_MARKERS),
            "VeriPB output contains an error marker",
        )
        contract_end = verify_contract(args.expected_systemd_unit)
        end_events = contract_end["cgroup"]["memory_events"]
        require(
            end_events.get("oom", 0) == start_events.get("oom", 0)
            and end_events.get("oom_kill", 0)
            == start_events.get("oom_kill", 0),
            "cgroup OOM counters increased",
        )
        formula_identity = {
            "path": str(formula_path),
            "size_bytes": len(formula_raw),
            "sha256": sha(formula_raw),
            "mode_octal": "0644",
        }
        receipt = {
            "schema_version": "b1_sidewise_internal_formal_receipt_v1",
            "status": "VERIFIED",
            "proof_status": "VERIFIED UNSATISFIABLE",
            "claim": (
                "machine_verified_two_oriented_ceiling_selectors_unsat_"
                "given_admitted_smm209"
            ),
            "inputs": {
                "pb_authority": authority_identity,
                "geometry_admission": geometry_identity,
                "strict_instance": strict_identity,
                "translation_gate": translation_identity,
                "translation_recheck": replay_identity,
                "preflight": preflight_identity,
                "reservation": reservation_identity,
                "build_formula": formula_build_identity,
            },
            "tools": {
                "worker": self_identity,
                "roundingsat": rounding_identity,
                "veripb": veripb_identity,
                "versions": version_records,
            },
            "formula": formula_identity,
            "proof": proof_identity,
            "solver": {
                "argv": solver_argv,
                "exit_code": solver_exit,
                "elapsed_milliseconds": round(solver_elapsed * 1000),
                "status_lines": statuses,
            },
            "verifier": {
                "argv": verifier_argv,
                "exit_code": verifier_run.returncode,
                "elapsed_milliseconds": round(verifier_elapsed * 1000),
                "status_lines": verifier_lines,
            },
            "resource_contract": {
                "start": contract_start,
                "end": contract_end,
                "proof_limit_bytes": PROOF_LIMIT,
                "low_water_bytes": LOW_WATER,
                "required_free_before_formal_bytes": REQUIRED_FREE,
                "free_before_solver_bytes": current_free,
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
        write_once(args.output_dir / "internal_formal_receipt.json", receipt_raw)
        members = {}
        for path in sorted(args.output_dir.iterdir()):
            if path.name == "SHA256SUMS":
                continue
            raw, _ = snapshot(path, path.name)
            members[path.name] = sha(raw)
        sums = "".join(
            f"{digest}  {name}\n" for name, digest in sorted(members.items())
        ).encode()
        write_once(args.output_dir / "SHA256SUMS", sums)
        result = {
            "status": "VERIFIED",
            "proof_status": receipt["proof_status"],
            "internal_receipt": {
                "path": str(args.output_dir / "internal_formal_receipt.json"),
                "size_bytes": len(receipt_raw),
                "sha256": sha(receipt_raw),
            },
            "upper_bound_update_authorized": False,
            "awaiting_terminal_envelope": True,
        }
    except (
        OSError,
        FormalError,
        subprocess.SubprocessError,
    ) as exc:
        failure_context = {
            "schema_version": "b1_sidewise_internal_formal_failure_v1",
            "status": "FAIL_CLOSED",
            "error": str(exc),
            "upper_bound_update_authorized": False,
            "ledger": {"upper": [1188, 22], "lower": "absent"},
            "production_certified": False,
        }
        if output_created:
            failure_path = args.output_dir / "formal_failure.json"
            if not failure_path.exists() and not failure_path.is_symlink():
                write_once(failure_path, json_bytes(failure_context))
        print(json.dumps(failure_context, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
