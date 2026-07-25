#!/usr/bin/env python3
"""Close the internal proof and external terminal envelope into authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any


HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
AUTHORITY_SCHEMA = "b1_sidewise_pb_pre_run_authority_v1"
PROOF_LIMIT = 5_000_000_000
MEMORY_HIGH = 35 * 1024**3
MEMORY_MAX = 39 * 1024**3
MEMORY_SWAP_MAX = 16 * 1024**3


class CloseError(RuntimeError):
    """Raised when the final research authority must remain closed."""


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
            raise CloseError(f"{label}: not regular")
        blocks: list[bytes] = []
        while True:
            block = os.read(fd, 1 << 20)
            if not block:
                break
            blocks.append(block)
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
        raise CloseError(f"{label}: changed during read")
    raw = b"".join(blocks)
    if len(raw) != before.st_size:
        raise CloseError(f"{label}: short read")
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
                raise CloseError(f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise CloseError(f"{label}: non-integer JSON {value!r}")

    try:
        return json.loads(
            raw,
            object_pairs_hook=unique,
            parse_float=reject,
            parse_constant=reject,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CloseError(f"{label}: malformed JSON: {exc}") from exc


def require(ok: bool, message: str) -> None:
    if not ok:
        raise CloseError(message)


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


def manifest(raw: bytes) -> dict[str, str]:
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise CloseError("formal manifest is not ASCII") from exc
    result: dict[str, str] = {}
    for line in lines:
        parts = line.split("  ")
        require(
            len(parts) == 2
            and re.fullmatch(r"[0-9a-f]{64}", parts[0]) is not None,
            "formal manifest line malformed",
        )
        require(parts[1] not in result, "duplicate formal manifest member")
        result[parts[1]] = parts[0]
    return result


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
                raise CloseError("short output write")
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
    parser.add_argument("--formal-dir", type=Path, required=True)
    parser.add_argument("--launch-receipt", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
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
            "authority tools/binaries missing",
        )
        _, self_identity = snapshot(Path(__file__), "formal closer")
        identity_match(
            self_identity, tools.get("formal_closer", {}), "formal closer"
        )
        geometry_raw, geometry_identity = snapshot(
            args.geometry_admission, "geometry admission"
        )
        identity_match(
            geometry_identity,
            authority.get("geometry_admission", {}),
            "geometry admission",
        )
        geometry = parse_json(geometry_raw, "geometry admission")
        require(
            isinstance(geometry, dict)
            and geometry.get("status") == "PASS"
            and geometry.get("decision") == "ADMITTED_FOR_PB_ENCODER",
            "geometry admission failed",
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
            "translation gate replay failed",
        )
        preflight_raw, preflight_identity = snapshot(
            args.preflight, "preflight"
        )
        preflight = parse_json(preflight_raw, "preflight")
        require(
            isinstance(preflight, dict)
            and preflight.get("status") == "PASS"
            and preflight.get("formal_launch_permitted") is True,
            "preflight failed",
        )
        reservation_raw, reservation_identity = snapshot(
            args.reservation, "reservation"
        )
        reservation = parse_json(reservation_raw, "reservation")
        require(
            isinstance(reservation, dict)
            and reservation.get("attempt") == "a001"
            and reservation.get("pb_authority") == authority_identity
            and reservation.get("preflight") == preflight_identity,
            "formal reservation failed",
        )
        launch_raw, launch_identity = snapshot(
            args.launch_receipt, "launch receipt"
        )
        launch = parse_json(launch_raw, "launch receipt")
        require(
            isinstance(launch, dict)
            and launch.get("schema_version")
            == "b1_sidewise_formal_launch_receipt_v1"
            and launch.get("status") == "PASS"
            and launch.get("systemd_run_exit_code") == 0
            and launch.get("cgroup_procs_after_terminal") == []
            and launch.get("upper_bound_update_authorized") is False,
            "terminal launch envelope failed",
        )
        terminal = launch.get("terminal")
        expected_terminal = {
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
        require(isinstance(terminal, dict), "terminal properties missing")
        require(
            all(
                isinstance(terminal.get(name), dict)
                and terminal[name].get("exit_code") == 0
                and terminal[name].get("value") == value
                for name, value in expected_terminal.items()
            ),
            "terminal property mismatch",
        )
        internal_raw, internal_identity = snapshot(
            args.formal_dir / "internal_formal_receipt.json",
            "internal formal receipt",
        )
        require(
            launch.get("internal_formal_receipt") == internal_identity,
            "launch envelope does not bind current internal receipt",
        )
        internal = parse_json(internal_raw, "internal formal receipt")
        require(
            isinstance(internal, dict)
            and internal.get("schema_version")
            == "b1_sidewise_internal_formal_receipt_v1"
            and internal.get("status") == "VERIFIED"
            and internal.get("proof_status") == "VERIFIED UNSATISFIABLE"
            and internal.get("upper_bound_update_authorized") is False
            and internal.get("awaiting_terminal_envelope") is True
            and internal.get("production_certified") is False,
            "internal formal semantics failed",
        )
        require(
            internal.get("inputs", {}).get("pb_authority")
            == authority_identity
            and internal.get("inputs", {}).get("geometry_admission")
            == geometry_identity
            and internal.get("inputs", {}).get("translation_gate")
            == translation_identity
            and internal.get("inputs", {}).get("preflight")
            == preflight_identity
            and internal.get("inputs", {}).get("reservation")
            == reservation_identity,
            "internal provenance mismatch",
        )
        identity_match(
            internal.get("tools", {}).get("worker", {}),
            tools.get("formal_worker", {}),
            "formal worker",
        )
        identity_match(
            internal.get("tools", {}).get("roundingsat", {}),
            binaries.get("roundingsat", {}),
            "RoundingSat",
        )
        identity_match(
            internal.get("tools", {}).get("veripb", {}),
            binaries.get("veripb", {}),
            "VeriPB",
        )
        require(
            internal.get("solver", {}).get("status_lines")
            == ["UNSATISFIABLE"]
            and internal.get("verifier", {}).get("status_lines")
            == ["s VERIFIED UNSATISFIABLE"],
            "solver/verifier status protocol mismatch",
        )
        formula_raw, formula_identity = snapshot(
            args.formal_dir / "formula.opb", "formal formula"
        )
        proof_raw, proof_identity = snapshot(
            args.formal_dir / "roundingsat.proof.pbp", "formal proof"
        )
        require(
            internal.get("formula") == formula_identity
            and internal.get("proof") == proof_identity
            and 0 < len(proof_raw) <= PROOF_LIMIT,
            "formula/proof identity or cap mismatch",
        )
        del formula_raw, proof_raw
        resources = internal.get("resource_contract")
        require(isinstance(resources, dict), "resource telemetry missing")
        start = resources.get("start", {}).get("cgroup", {}).get(
            "memory_events", {}
        )
        end = resources.get("end", {}).get("cgroup", {}).get(
            "memory_events", {}
        )
        require(
            isinstance(start, dict)
            and isinstance(end, dict)
            and end.get("oom", 0) == start.get("oom", 0)
            and end.get("oom_kill", 0) == start.get("oom_kill", 0),
            "resource OOM counters drifted",
        )
        sums_raw, sums_identity = snapshot(
            args.formal_dir / "SHA256SUMS", "formal manifest"
        )
        entries = manifest(sums_raw)
        actual_names = {
            path.name
            for path in args.formal_dir.iterdir()
            if path.is_file() and not path.is_symlink() and path.name != "SHA256SUMS"
        }
        require(set(entries) == actual_names, "formal manifest member set drifted")
        for name in sorted(actual_names):
            raw, _ = snapshot(args.formal_dir / name, name)
            require(entries[name] == sha(raw), f"formal member hash drift: {name}")
        require(
            not args.output_dir.exists() and not args.output_dir.is_symlink(),
            "final output exists",
        )
        require(
            args.output_dir.parent.is_dir()
            and not args.output_dir.parent.is_symlink(),
            "final output parent is not a real directory",
        )
        args.output_dir.mkdir(mode=0o755)
        receipt = {
            "schema_version": "b1_sidewise_final_authority_receipt_v1",
            "status": "VERIFIED",
            "proof_status": "VERIFIED UNSATISFIABLE",
            "claim": (
                "machine_verified_complete_lex_better_band_unsat_"
                "for_research_upper_1188_18_given_admitted_geometric_lemmas"
            ),
            "inputs": {
                "pb_authority": authority_identity,
                "geometry_admission": geometry_identity,
                "translation_gate": translation_identity,
                "preflight": preflight_identity,
                "reservation": reservation_identity,
                "internal_formal_receipt": internal_identity,
                "launch_receipt": launch_identity,
                "formal_manifest": sums_identity,
            },
            "formula": formula_identity,
            "proof": proof_identity,
            "tools": {
                "roundingsat": internal["tools"]["roundingsat"],
                "veripb": internal["tools"]["veripb"],
                "formal_worker": internal["tools"]["worker"],
                "formal_closer": self_identity,
            },
            "band_composition": {
                "old_verified_band_count": 2084,
                "new_ceiling_orientations": [[22, 54], [54, 22]],
                "complete_candidate_band_count": 2086,
                "old_authority_replayed": True,
            },
            "ledger": {
                "old_upper": [1188, 22],
                "new_upper": [1188, 18],
                "lower": "absent",
            },
            "upper_bound_update_authorized": True,
            "witness_or_attainability": False,
            "optimality": False,
            "global_infeasibility": False,
            "production_certified": False,
        }
        receipt_raw = json_bytes(receipt)
        write_once(args.output_dir / "authority_receipt.json", receipt_raw)
        write_once(
            args.output_dir / "SHA256SUMS",
            f"{sha(receipt_raw)}  authority_receipt.json\n".encode(),
        )
    except (OSError, CloseError) as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL_CLOSED",
                    "error": str(exc),
                    "upper_bound_update_authorized": False,
                    "ledger": {"upper": [1188, 22], "lower": "absent"},
                },
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": "VERIFIED",
                "proof_status": receipt["proof_status"],
                "output": str(args.output_dir / "authority_receipt.json"),
                "size_bytes": len(receipt_raw),
                "sha256": sha(receipt_raw),
                "upper_bound_update_authorized": True,
                "new_upper": [1188, 18],
                "lower": "absent",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
