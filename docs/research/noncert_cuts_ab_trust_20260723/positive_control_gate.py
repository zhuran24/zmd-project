#!/usr/bin/env python3
"""Fail-closed admission gate for the injected positive-control A/B pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
ARM_CONFIG_DIFFERENCES = frozenset()


def _read_json(path: Path) -> tuple[dict[str, Any], dict[str, object]]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"input must be a regular non-symlink file: {path}")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON input {path}: {exc}") from exc
    if type(value) is not dict:
        raise ValueError(f"input root must be an object: {path}")
    return value, {
        "path": str(path),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _write_exclusive(path: Path, payload: object) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite gate result: {path}")
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


def _head(result: dict[str, Any]) -> object:
    authority = result.get("authority")
    return authority.get("repository_head") if type(authority) is dict else None


def _counts(result: dict[str, Any]) -> tuple[int, int, int]:
    ledger = result.get("ledger")
    injection = result.get("injection")
    if type(ledger) is not dict or type(injection) is not dict:
        raise ValueError("arm result lacks ledger or injection evidence")
    generated = ledger.get("generated")
    compiled = injection.get("compiled_observed")
    applied = ledger.get("applied")
    if any(type(value) is not int or value < 0 for value in (generated, compiled, applied)):
        raise ValueError("arm counts must be non-negative exact integers")
    return generated, compiled, applied


def evaluate(
    control: dict[str, Any],
    treatment: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    check(
        "arm_labels",
        control.get("arm") == "control" and treatment.get("arm") == "treatment",
        [control.get("arm"), treatment.get("arm")],
    )
    check(
        "terminal_status",
        control.get("terminal_status") == "ARM_COMPLETE" and treatment.get("terminal_status") == "ARM_COMPLETE",
        [control.get("terminal_status"), treatment.get("terminal_status")],
    )
    check(
        "authority_head",
        _head(control) == EXPECTED_HEAD and _head(treatment) == EXPECTED_HEAD,
        [_head(control), _head(treatment)],
    )
    check(
        "authority_identity_equality",
        control.get("authority") == treatment.get("authority"),
        None,
    )
    check(
        "config_equality",
        control.get("config") == treatment.get("config")
        and control.get("config_digest") == treatment.get("config_digest"),
        [control.get("config_digest"), treatment.get("config_digest")],
    )
    control_prestate = control.get("prestate")
    treatment_prestate = treatment.get("prestate")
    prestate_equal = (
        type(control_prestate) is dict
        and type(treatment_prestate) is dict
        and control_prestate.get("incumbent_sha256") == treatment_prestate.get("incumbent_sha256")
        and control_prestate.get("model_proto_sha256") == treatment_prestate.get("model_proto_sha256")
        and control_prestate.get("ghost_pick") == treatment_prestate.get("ghost_pick")
    )
    check("fresh_replica_prestate", prestate_equal, None)
    check(
        "ledger_complete",
        control.get("ledger", {}).get("status") == "complete"
        and treatment.get("ledger", {}).get("status") == "complete",
        [
            control.get("ledger", {}).get("status"),
            treatment.get("ledger", {}).get("status"),
        ],
    )
    try:
        control_counts = _counts(control)
        treatment_counts = _counts(treatment)
    except ValueError as exc:
        control_counts = (-1, -1, -1)
        treatment_counts = (-1, -1, -1)
        check("count_schema", False, str(exc))
    else:
        check("count_schema", True, None)
    check("control_applied_zero", control_counts[2] == 0, control_counts)
    check(
        "treatment_chain_positive",
        all(value > 0 for value in treatment_counts),
        treatment_counts,
    )
    check(
        "arithmetic_receipt",
        receipt.get("status") == "PASS" and receipt.get("active") is True and receipt.get("violated") is True,
        {
            "status": receipt.get("status"),
            "selected_cut_id": receipt.get("selected_cut_id"),
            "active": receipt.get("active"),
            "violated": receipt.get("violated"),
        },
    )
    treatment_prestate_sha = treatment_prestate.get("incumbent_sha256") if type(treatment_prestate) is dict else None
    sample_corpus = treatment.get("arithmetic_sample_corpus")
    if type(sample_corpus) is dict:
        receipt_binding = sample_corpus.get("prestate_sha256") == treatment_prestate_sha and receipt.get(
            "input_sha256"
        ) == sample_corpus.get("sha256")
    else:
        receipt_binding = False
    check("receipt_binding", receipt_binding, sample_corpus)

    passed = all(bool(row["passed"]) for row in checks)
    status = "INJECTED_MECHANISM_POSITIVE_CONTROL" if passed else "CREDIBILITY_INCOMPLETE"
    return {
        "schema_version": 1,
        "status": status,
        "admitted": passed,
        "claim_boundary": {
            "established": [
                "post_fix_typed_path_reachable",
                "audit_ledger_observed_applied",
                "one_applied_inequality_excludes_frozen_incumbent",
            ]
            if passed
            else [],
            "not_established": [
                "cut_global_soundness",
                "organic_runtime_usefulness",
                "single_family_usefulness",
                "pic4_or_pic5_closed",
                "b6_authorized",
                "unsat_or_infeasibility_proof",
                "witness_or_lower_bound",
            ],
        },
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--treatment", type=Path, required=True)
    parser.add_argument("--arithmetic-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs: dict[str, object] = {}
    try:
        control, inputs["control"] = _read_json(args.control)
        treatment, inputs["treatment"] = _read_json(args.treatment)
        receipt, inputs["arithmetic_receipt"] = _read_json(args.arithmetic_receipt)
        result = evaluate(control, treatment, receipt)
        result["inputs"] = inputs
        exit_code = 0 if result["admitted"] else 2
    except Exception as exc:  # noqa: BLE001 - fail-closed gate record
        result = {
            "schema_version": 1,
            "status": "CREDIBILITY_INCOMPLETE",
            "admitted": False,
            "error": f"{type(exc).__name__}: {exc}",
            "inputs": inputs,
        }
        exit_code = 2
    _write_exclusive(args.output, result)
    print(json.dumps(result, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
