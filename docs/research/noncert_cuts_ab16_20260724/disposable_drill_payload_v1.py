#!/usr/bin/env python3
"""Write one inert success observation for the AB16 disposable live drill.

The payload performs no solve, cut generation, model construction, or project
mutation.  It only replays the immutable drill selection and exclusively
publishes the minimal result consumed by the two-stage resource lifecycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any, Sequence


SELECTION_SCHEMA = "noncert-cuts-ab16-organic-drill-selection-v1"
SELECTION_PURPOSE = "noncert_cuts_ab16_disposable_live_drill"
RESULT_SCHEMA = "noncert-cuts-ab16-organic-arm-result-v1"
RESULT_PURPOSE = "noncert_cuts_ab16_disposable_live_drill_payload"


class DrillPayloadError(RuntimeError):
    """The disposable selection or no-overwrite output is invalid."""


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DrillPayloadError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _snapshot(path: Path | str) -> tuple[bytes, dict[str, object]]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(absolute, flags)
    except OSError as exc:
        raise DrillPayloadError(f"selection open failed: {absolute}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise DrillPayloadError("selection is not a singly linked regular file")
        chunks: list[bytes] = []
        while block := os.read(descriptor, 1024 * 1024):
            chunks.append(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    compared = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_nlink",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    raw = b"".join(chunks)
    if any(getattr(before, field) != getattr(after, field) for field in compared) or len(raw) != after.st_size:
        raise DrillPayloadError("selection changed during same-FD replay")
    return raw, {
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _selection(path: Path | str) -> tuple[dict[str, Any], dict[str, object]]:
    raw, identity = _snapshot(path)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda token: (_ for _ in ()).throw(DrillPayloadError(f"invalid JSON constant: {token}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DrillPayloadError("selection is not strict JSON") from exc
    if type(value) is not dict or canonical_json(value) != raw:
        raise DrillPayloadError("selection is not a canonical JSON object")
    if (
        value.get("schema_version") != SELECTION_SCHEMA
        or value.get("purpose") != SELECTION_PURPOSE
        or value.get("execution_class") != "DISPOSABLE_LIVE_DRILL"
        or value.get("arm") != "control"
        or value.get("enabled_families") != []
        or value.get("authorizations")
        != {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_arm_launch_authorized": False,
            "production_certified_authorized": False,
            "solver_run_authorized": False,
        }
    ):
        raise DrillPayloadError("selection is not an inert disposable drill")
    return value, identity


def _write_exclusive(path: Path | str, raw: bytes) -> dict[str, object]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    parent = absolute.parent
    parent_descriptor = os.open(
        parent,
        os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        descriptor = os.open(
            absolute.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o444,
            dir_fd=parent_descriptor,
        )
    except OSError as exc:
        os.close(parent_descriptor)
        raise DrillPayloadError("result no-overwrite publication failed") from exc
    os.close(parent_descriptor)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise DrillPayloadError("short result write")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, 0o444)
        metadata = os.fstat(descriptor)
        if metadata.st_size != len(raw):
            raise DrillPayloadError("result size differs after write")
    finally:
        os.close(descriptor)
    return {
        "path": str(absolute),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def run(selection_path: Path | str, output_path: Path | str) -> dict[str, object]:
    selection, selection_identity = _selection(selection_path)
    result = {
        "arm": "control",
        "authorizations": {
            "global_claim_authorized": False,
            "mathematical_claim_authorized": False,
            "organic_runtime_effect_authorized": False,
            "production_certified_authorized": False,
        },
        "purpose": RESULT_PURPOSE,
        "schema_version": RESULT_SCHEMA,
        "selection_identity": selection_identity,
        "slot": selection["slot"],
        "status": "DISPOSABLE_DRILL_PAYLOAD_COMPLETE",
    }
    identity = _write_exclusive(output_path, canonical_json(result))
    return {
        "result": result,
        "result_identity": identity,
        "status": "PASS",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        result = run(arguments.selection, arguments.output)
    except DrillPayloadError as exc:
        print(
            json.dumps(
                {"detail": str(exc), "status": "FAIL_CLOSED"},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
