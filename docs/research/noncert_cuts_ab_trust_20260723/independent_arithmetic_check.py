#!/usr/bin/env python3
"""Stdlib-only arithmetic replay for the injected positive-control sample.

The checker deliberately knows nothing about cut generation or geometry.  It
only confirms that the captured linear arithmetic is internally canonical and
that at least one applied cut is active and violated by the frozen incumbent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


EXPECTED_HEAD = "398f8725c770f3c36408adebe9448a890ed886fe"
ALLOWED_OPERATIONS = {
    "region_capacity_le",
    "shape_packing_hall_le",
    "power_pose_exclusion",
}


def _is_sha256(value: object) -> bool:
    if type(value) is not str or len(value) != 64 or value != value.lower():
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _read_input(path: Path) -> tuple[dict[str, Any], str]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("input must be a regular non-symlink file")
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"input is not valid UTF-8 JSON: {exc}") from exc
    if type(payload) is not dict:
        raise ValueError("input root must be an object")
    return payload, hashlib.sha256(raw).hexdigest()


def _write_exclusive(path: Path, payload: object) -> None:
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite receipt: {path}")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise ValueError("receipt parent must be an existing non-symlink directory")
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


def _check_sample(sample: object) -> dict[str, object]:
    if type(sample) is not dict:
        raise ValueError("sample must be an object")
    operation = sample.get("operation")
    if operation not in ALLOWED_OPERATIONS:
        raise ValueError(f"unsupported operation: {operation!r}")
    for field in ("cut_id", "family"):
        if type(sample.get(field)) is not str or not sample[field]:
            raise ValueError(f"{field} must be a non-empty string")
    for field in ("plan_digest", "compiled_digest"):
        if not _is_sha256(sample.get(field)):
            raise ValueError(f"{field} must be a lowercase SHA-256")
    enforcement_values = sample.get("enforcement_values")
    if type(enforcement_values) is not list or any(
        type(value) is not int or value not in {0, 1} for value in enforcement_values
    ):
        raise ValueError("enforcement_values must contain exact 0/1 integers")
    contributions = sample.get("contributions")
    if type(contributions) is not list or not contributions:
        raise ValueError("contributions must be a non-empty list")
    recomputed_lhs = 0
    for index, contribution in enumerate(contributions):
        if type(contribution) is not dict:
            raise ValueError(f"contribution {index} must be an object")
        selected_count = contribution.get("selected_count")
        weight = contribution.get("weight")
        value = contribution.get("value")
        if (
            type(selected_count) is not int
            or selected_count < 0
            or type(weight) is not int
            or weight <= 0
            or type(value) is not int
        ):
            raise ValueError(f"contribution {index} has invalid exact integers")
        expected_value = selected_count * weight
        if value != expected_value:
            raise ValueError(f"contribution {index} value mismatch: {value} != {expected_value}")
        recomputed_lhs += expected_value
    rhs = sample.get("rhs")
    if type(rhs) is not int:
        raise ValueError("rhs must be an exact integer")
    active = all(value == 1 for value in enforcement_values)
    violated = bool(active and recomputed_lhs > rhs)
    if sample.get("lhs") != recomputed_lhs:
        raise ValueError("captured lhs does not match recomputed contributions")
    if sample.get("active") is not active:
        raise ValueError("captured active flag does not match enforcement values")
    if sample.get("violated") is not violated:
        raise ValueError("captured violated flag does not match arithmetic")
    if operation == "power_pose_exclusion" and rhs != 0:
        raise ValueError("power_pose_exclusion must have rhs=0")
    return {
        "cut_id": sample["cut_id"],
        "family": sample["family"],
        "operation": operation,
        "recomputed_lhs": recomputed_lhs,
        "rhs": rhs,
        "active": active,
        "violated": violated,
    }


def verify(payload: dict[str, Any], *, expected_head: str = EXPECTED_HEAD) -> dict[str, object]:
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version must be exact integer 1")
    authority = payload.get("authority")
    if type(authority) is not dict or authority.get("head") != expected_head:
        raise ValueError("authority HEAD mismatch")
    if payload.get("arm") != "treatment":
        raise ValueError("arithmetic admission accepts treatment samples only")
    if not _is_sha256(payload.get("prestate_sha256")):
        raise ValueError("prestate_sha256 must be a lowercase SHA-256")
    samples = payload.get("samples")
    if type(samples) is not list or not samples:
        raise ValueError("treatment sample corpus must be non-empty")
    checked = [_check_sample(sample) for sample in samples]
    keys = [(str(row["family"]), str(row["cut_id"])) for row in checked]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate (family, cut_id) sample")
    violated = sorted(
        (row for row in checked if row["violated"]),
        key=lambda row: (str(row["family"]), str(row["cut_id"])),
    )
    if not violated:
        raise ValueError("no active violated cut was independently reproduced")
    selected = violated[0]
    return {
        "status": "PASS",
        "checked_sample_count": len(checked),
        "violated_sample_count": len(violated),
        "selected_cut_id": selected["cut_id"],
        "selected_family": selected["family"],
        "selected_operation": selected["operation"],
        "recomputed_lhs": selected["recomputed_lhs"],
        "rhs": selected["rhs"],
        "active": selected["active"],
        "violated": selected["violated"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-head", default=EXPECTED_HEAD)
    args = parser.parse_args()
    input_sha256 = ""
    try:
        payload, input_sha256 = _read_input(args.input)
        receipt = verify(payload, expected_head=args.expected_head)
        receipt["input_path"] = str(args.input)
        receipt["input_sha256"] = input_sha256
        exit_code = 0
    except Exception as exc:  # noqa: BLE001 - fail-closed receipt
        receipt = {
            "status": "FAIL",
            "input_path": str(args.input),
            "input_sha256": input_sha256,
            "error": f"{type(exc).__name__}: {exc}",
        }
        exit_code = 2
    _write_exclusive(args.output, receipt)
    print(json.dumps(receipt, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
