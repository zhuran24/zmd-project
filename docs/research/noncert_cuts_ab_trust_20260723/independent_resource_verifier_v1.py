#!/usr/bin/env python3
"""Independently verify a Gate 1 paired-arm resource receipt.

The verifier consumes only inert JSON and the two immutable arm results.  It
does not query a live cgroup or reconstruct observations that were not captured
when the arms ran.  A PASS therefore means that a complete, byte-bound receipt
records the approved contract and clean terminal resource state for both arms;
absence of such a receipt remains unverified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
EXPECTED_CONTRACT = {
    "memory_high_bytes": 35 * 1024**3,
    "memory_max_bytes": 39 * 1024**3,
    "memory_swap_max_bytes": 16 * 1024**3,
    "oom_policy": "continue",
    "wall_timeout_seconds": 25 * 60,
}
EXPECTED_MEMORY_EVENT_KEYS = frozenset(
    {
        "low",
        "high",
        "max",
        "oom",
        "oom_kill",
        "oom_group_kill",
    }
)
REQUIRED_ARM_FIELDS = frozenset(
    {
        "result_identity",
        "unit_name",
        "exit_code",
        "termination_reason",
        "wall_seconds",
        "memory_peak_bytes",
        "swap_at_completion_bytes",
        "memory_events_delta",
        "kill_count",
        "timeout_count",
        "limit_violation_count",
    }
)


def _is_sha256(value: object) -> bool:
    if type(value) is not str or len(value) != 64 or value != value.lower():
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _reject_symlink_chain(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"symlink path component rejected: {current}")


def _identity(path: Path) -> dict[str, object]:
    absolute = path.absolute()
    _reject_symlink_chain(absolute)
    if not absolute.is_file() or absolute.is_symlink():
        raise ValueError(f"input must be a regular non-symlink file: {path}")
    raw = absolute.read_bytes()
    return {
        "path": str(absolute),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _read_json(path: Path) -> tuple[dict[str, Any], dict[str, object]]:
    identity = _identity(path)
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON input {path}: {exc}") from exc
    if type(payload) is not dict:
        raise ValueError(f"input root must be an object: {path}")
    return payload, identity


def _write_exclusive(path: Path, payload: object) -> None:
    _reject_symlink_chain(path.parent)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite resource-verifier receipt: {path}")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("output parent must be an existing non-symlink directory")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(data)
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)


def _same_identity(recorded: object, actual: dict[str, object]) -> bool:
    if type(recorded) is not dict:
        return False
    return (
        type(recorded.get("path")) is str
        and str(Path(recorded["path"]).absolute()) == str(Path(str(actual["path"])).absolute())
        and recorded.get("size") == actual["size"]
        and recorded.get("sha256") == actual["sha256"]
    )


def _verify_source_identities(raw: object) -> tuple[bool, list[dict[str, object]]]:
    if type(raw) is not list or not raw:
        return False, []
    replayed: list[dict[str, object]] = []
    seen_paths: set[str] = set()
    for index, recorded in enumerate(raw):
        if type(recorded) is not dict:
            raise ValueError(f"source identity {index} must be an object")
        source_path = recorded.get("path")
        if type(source_path) is not str or not source_path or source_path in seen_paths:
            raise ValueError(f"source identity {index} has an invalid or duplicate path")
        seen_paths.add(source_path)
        actual = _identity(Path(source_path))
        replayed.append(actual)
        if not _same_identity(recorded, actual):
            return False, replayed
    return True, replayed


def _check_arm(
    label: str,
    record: object,
    actual_result_identity: dict[str, object],
) -> tuple[bool, list[dict[str, object]]]:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"name": f"{label}.{name}", "passed": bool(passed), "detail": detail})

    if type(record) is not dict:
        check("schema", False, "arm resource record must be an object")
        return False, checks

    missing = sorted(REQUIRED_ARM_FIELDS - set(record))
    check("required_fields", not missing, missing)
    check(
        "result_identity",
        _same_identity(record.get("result_identity"), actual_result_identity),
        record.get("result_identity"),
    )
    unit_name = record.get("unit_name")
    check("unit_name", type(unit_name) is str and bool(unit_name), unit_name)
    check("exit_code", record.get("exit_code") == 0, record.get("exit_code"))
    check(
        "termination_reason",
        record.get("termination_reason") == "normal_exit",
        record.get("termination_reason"),
    )

    wall_seconds = record.get("wall_seconds")
    wall_ok = (
        type(wall_seconds) in {int, float}
        and not isinstance(wall_seconds, bool)
        and 0 <= wall_seconds <= EXPECTED_CONTRACT["wall_timeout_seconds"]
    )
    check("wall_seconds", wall_ok, wall_seconds)

    peak = record.get("memory_peak_bytes")
    peak_ok = type(peak) is int and peak >= 0 and peak < EXPECTED_CONTRACT["memory_high_bytes"]
    check("memory_peak_below_high", peak_ok, peak)
    check(
        "swap_zero_at_completion",
        record.get("swap_at_completion_bytes") == 0,
        record.get("swap_at_completion_bytes"),
    )

    events = record.get("memory_events_delta")
    events_ok = (
        type(events) is dict
        and set(events) == EXPECTED_MEMORY_EVENT_KEYS
        and all(type(value) is int and value == 0 for value in events.values())
    )
    check("memory_events_zero", events_ok, events)
    for field in ("kill_count", "timeout_count", "limit_violation_count"):
        check(field, record.get(field) == 0, record.get(field))
    return all(bool(row["passed"]) for row in checks), checks


def verify_resource_receipt(
    receipt: dict[str, Any],
    *,
    receipt_identity: dict[str, object],
    control_identity: dict[str, object],
    treatment_identity: dict[str, object],
    verifier_identity: dict[str, object],
    expected_head: str = EXPECTED_HEAD,
) -> dict[str, object]:
    """Return a deterministic PASS/FAIL replay record for one resource receipt."""

    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check("schema_version", receipt.get("schema_version") == 1, receipt.get("schema_version"))
    check(
        "schema",
        receipt.get("schema") == "noncert-cuts-positive-control-resource-receipt-v1",
        receipt.get("schema"),
    )
    check("repository_head", receipt.get("repository_head") == expected_head, receipt.get("repository_head"))
    check("contract_exact", receipt.get("contract") == EXPECTED_CONTRACT, receipt.get("contract"))

    arm_results = receipt.get("arm_results")
    arm_results_ok = (
        type(arm_results) is dict
        and set(arm_results) == {"control", "treatment"}
        and _same_identity(arm_results.get("control"), control_identity)
        and _same_identity(arm_results.get("treatment"), treatment_identity)
    )
    check("arm_result_identities", arm_results_ok, arm_results)

    try:
        source_ok, replayed_sources = _verify_source_identities(receipt.get("source_identities"))
    except Exception as exc:  # noqa: BLE001 - convert malformed source evidence into a failed receipt
        source_ok = False
        replayed_sources = []
        source_detail: object = f"{type(exc).__name__}: {exc}"
    else:
        source_detail = replayed_sources
    check("source_identities_replay", source_ok, source_detail)

    arms = receipt.get("arms")
    if type(arms) is dict and set(arms) == {"control", "treatment"}:
        control_ok, control_checks = _check_arm("control", arms["control"], control_identity)
        treatment_ok, treatment_checks = _check_arm("treatment", arms["treatment"], treatment_identity)
        checks.extend(control_checks)
        checks.extend(treatment_checks)
        unit_names = [arms["control"].get("unit_name"), arms["treatment"].get("unit_name")]
        check(
            "distinct_unit_names",
            all(type(name) is str and bool(name) for name in unit_names) and len(set(unit_names)) == 2,
            unit_names,
        )
        arms_ok = control_ok and treatment_ok
    else:
        arms_ok = False
        check("arms_schema", False, arms)

    passed = arms_ok and source_ok and all(bool(row["passed"]) for row in checks)
    return {
        "schema_version": 1,
        "verifier": "independent_resource_verifier_v1",
        "status": "PASS" if passed else "FAIL",
        "repository_head": expected_head,
        "input_identities": {
            "resource_receipt": receipt_identity,
            "control": control_identity,
            "treatment": treatment_identity,
        },
        "verifier_identity": verifier_identity,
        "contract": EXPECTED_CONTRACT,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource-receipt", type=Path, required=True)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--treatment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-head", default=EXPECTED_HEAD)
    args = parser.parse_args()

    inputs: dict[str, object] = {}
    try:
        receipt, receipt_identity = _read_json(args.resource_receipt)
        inputs["resource_receipt"] = receipt_identity
        _control, control_identity = _read_json(args.control)
        inputs["control"] = control_identity
        _treatment, treatment_identity = _read_json(args.treatment)
        inputs["treatment"] = treatment_identity
        verifier_identity = _identity(Path(__file__).resolve())
        result = verify_resource_receipt(
            receipt,
            receipt_identity=receipt_identity,
            control_identity=control_identity,
            treatment_identity=treatment_identity,
            verifier_identity=verifier_identity,
            expected_head=args.expected_head,
        )
        exit_code = 0 if result["status"] == "PASS" else 2
    except Exception as exc:  # noqa: BLE001 - fail-closed verifier record
        result = {
            "schema_version": 1,
            "verifier": "independent_resource_verifier_v1",
            "status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
            "input_identities": inputs,
        }
        exit_code = 2

    _write_exclusive(args.output, result)
    print(json.dumps(result, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
