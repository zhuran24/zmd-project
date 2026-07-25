#!/usr/bin/env python3
"""Publish the immutable closeout for the consumed, non-admitted attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any


MEMORY_HIGH = str(35 * 1024**3)
MEMORY_MAX = str(39 * 1024**3)
MEMORY_SWAP_MAX = str(16 * 1024**3)


class CloseoutError(RuntimeError):
    """Raised when the failed-attempt history does not replay exactly."""


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
            raise CloseoutError(f"{label}: not regular")
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
        raise CloseoutError(f"{label}: changed during read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise CloseoutError(f"{label}: short read")
    return raw, {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": sha(raw),
        "mode_octal": f"{stat.S_IMODE(before.st_mode):04o}",
    }


def parse(raw: bytes, label: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise CloseoutError(f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise CloseoutError(f"{label}: non-integer JSON {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CloseoutError(f"{label}: malformed JSON: {exc}") from exc


def require(ok: bool, message: str) -> None:
    if not ok:
        raise CloseoutError(message)


def load(path: Path, label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, identity = snapshot(path, label)
    value = parse(raw, label)
    require(isinstance(value, dict), f"{label}: not an object")
    return value, identity


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
                raise CloseoutError("short output write")
            offset += count
        os.fsync(fd)
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pb-authority", type=Path, required=True)
    parser.add_argument("--geometry-admission", type=Path, required=True)
    parser.add_argument("--translation-gate", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--reservation", type=Path, required=True)
    parser.add_argument("--internal-receipt", type=Path, required=True)
    parser.add_argument("--launch-receipt", type=Path, required=True)
    parser.add_argument("--formal-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        pb, pb_id = load(args.pb_authority, "PB authority")
        geometry, geometry_id = load(
            args.geometry_admission, "geometry admission"
        )
        translation, translation_id = load(
            args.translation_gate, "translation gate"
        )
        preflight, preflight_id = load(args.preflight, "preflight")
        reservation, reservation_id = load(args.reservation, "reservation")
        internal, internal_id = load(
            args.internal_receipt, "internal receipt"
        )
        launch, launch_id = load(args.launch_receipt, "launch receipt")
        _, manifest_id = snapshot(args.formal_manifest, "formal manifest")
        require(
            pb.get("status") == "PB_PRE_RUN_AUTHORITY_PASS"
            and geometry.get("decision") == "ADMITTED_FOR_PB_ENCODER"
            and translation.get("decision") == "FORMAL_RUN_AUTHORIZED"
            and preflight.get("formal_launch_permitted") is True,
            "pre-formal gates did not all pass",
        )
        require(
            reservation.get("attempt") == "a001"
            and internal.get("status") == "VERIFIED"
            and internal.get("proof_status") == "VERIFIED UNSATISFIABLE"
            and internal.get("upper_bound_update_authorized") is False
            and internal.get("awaiting_terminal_envelope") is True,
            "internal proof/reservation history drifted",
        )
        require(
            launch.get("status") == "FAIL_CLOSED"
            and launch.get("systemd_run_exit_code") == 0
            and launch.get("internal_formal_receipt") == internal_id
            and launch.get("cgroup_procs_after_terminal") == [],
            "launch failure envelope drifted",
        )
        terminal = launch.get("terminal")
        require(isinstance(terminal, dict), "terminal record missing")
        observed = {
            key: terminal.get(key, {}).get("value")
            for key in (
                "ActiveState",
                "SubState",
                "Result",
                "ExecMainStatus",
                "MemoryHigh",
                "MemoryMax",
                "MemorySwapMax",
                "OOMPolicy",
                "KillMode",
                "SendSIGKILL",
            )
        }
        require(
            observed
            == {
                "ActiveState": "inactive",
                "SubState": "dead",
                "Result": "success",
                "ExecMainStatus": "0",
                "MemoryHigh": "infinity",
                "MemoryMax": "infinity",
                "MemorySwapMax": "infinity",
                "OOMPolicy": "",
                "KillMode": "control-group",
                "SendSIGKILL": "yes",
            },
            "terminal failure shape changed",
        )
        start_values = {
            key: value.get("value")
            for key, value in internal.get("resource_contract", {})
            .get("start", {})
            .get("properties", {})
            .items()
        }
        end_values = {
            key: value.get("value")
            for key, value in internal.get("resource_contract", {})
            .get("end", {})
            .get("properties", {})
            .items()
        }
        expected_inside = {
            "MemoryHigh": MEMORY_HIGH,
            "MemoryMax": MEMORY_MAX,
            "MemorySwapMax": MEMORY_SWAP_MAX,
            "OOMPolicy": "continue",
            "KillMode": "control-group",
            "SendSIGKILL": "yes",
        }
        require(
            start_values == end_values == expected_inside,
            "inside-unit resource observation drifted",
        )
        start_events = (
            internal["resource_contract"]["start"]["cgroup"]["memory_events"]
        )
        end_events = (
            internal["resource_contract"]["end"]["cgroup"]["memory_events"]
        )
        require(
            end_events.get("oom", 0) == start_events.get("oom", 0) == 0
            and end_events.get("oom_kill", 0)
            == start_events.get("oom_kill", 0)
            == 0,
            "inside-unit OOM counters drifted",
        )
        formula_id = internal.get("formula")
        proof_id = internal.get("proof")
        require(
            isinstance(formula_id, dict)
            and formula_id.get("sha256")
            == "d4b79cd76c80d23e509ad09b1d2e7fa02fa337049f40459ab803f0fc55a4d865"
            and isinstance(proof_id, dict)
            and proof_id.get("size_bytes") == 137
            and proof_id.get("sha256")
            == "48dec7cbb9ee0aebd8bc6f1a34b1e2b4024f85c80159d5fb82207bc6bf0286aa"
            and internal.get("verifier", {}).get("status_lines")
            == ["s VERIFIED UNSATISFIABLE"],
            "formula/proof/verifier identity drifted",
        )
        _, self_id = snapshot(Path(__file__), "closeout tool")
        require(
            not args.output_dir.exists() and not args.output_dir.is_symlink(),
            "closeout output exists",
        )
        require(
            args.output_dir.parent.is_dir()
            and not args.output_dir.parent.is_symlink(),
            "closeout parent is not a real directory",
        )
        args.output_dir.mkdir(mode=0o755)
        payload = {
            "schema_version": "b1_sidewise_formal_incomplete_closeout_v1",
            "status": "FORMAL_AUTHORITY_INCOMPLETE",
            "primary_reason": (
                "terminal_resource_properties_unavailable_after_unit_unload"
            ),
            "attempt": "a001_consumed_no_retry",
            "inputs": {
                "pb_authority": pb_id,
                "geometry_admission": geometry_id,
                "translation_gate": translation_id,
                "preflight": preflight_id,
                "reservation": reservation_id,
                "internal_receipt": internal_id,
                "launch_receipt": launch_id,
                "formal_manifest": manifest_id,
            },
            "tool": self_id,
            "established": {
                "geometry_admission_pass": True,
                "translation_gate_pass": True,
                "resource_preflight_pass": True,
                "roundingsat_unsat_status": True,
                "veripb_verified_unsatisfiable": True,
                "formula": formula_id,
                "proof": proof_id,
                "inside_unit_contract_observed_start_and_end": True,
                "inside_unit_oom_or_swap": False,
                "systemd_terminal_result_success": True,
            },
            "not_established": {
                "terminal_resource_contract_authority": True,
                "formal_authority_closure": True,
                "upper_update_to_1188_18": True,
                "witness_or_attainability": True,
                "optimality": True,
                "production_certified": True,
            },
            "observed_terminal_properties": observed,
            "required_terminal_properties": expected_inside
            | {"ActiveState": "inactive", "SubState": "dead", "Result": "success"},
            "upper_bound_update_authorized": False,
            "ledger": {"upper": [1188, 22], "lower": "absent"},
            "next_action": (
                "STOP; a new formal attempt requires a separately authorized "
                "task and cannot reuse or overwrite a001"
            ),
        }
        raw = (
            json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False)
            + "\n"
        ).encode()
        write_once(args.output_dir / "closeout.json", raw)
        write_once(
            args.output_dir / "SHA256SUMS",
            f"{sha(raw)}  closeout.json\n".encode(),
        )
    except (OSError, CloseoutError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}))
        return 2
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": str(args.output_dir / "closeout.json"),
                "size_bytes": len(raw),
                "sha256": sha(raw),
                "upper_bound_update_authorized": False,
                "ledger": payload["ledger"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
