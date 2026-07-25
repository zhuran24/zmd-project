#!/usr/bin/env python3
"""Select one exact PASS receipt and bind READY to its detached byte identity."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from types import ModuleType
from typing import Any
import uuid


SCHEMA = "r4_ready_selected_receipt_v1"
SELECTION_RELATIVE_PATH = "ready/selected-receipt.json"
VERIFIER_PATH = Path(__file__).with_name("verify_r4_handoff_package_v1.py")


class SelectionError(RuntimeError):
    """READY selection or selected-receipt provenance failed closed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: bytes, label: str) -> Mapping[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise SelectionError("INVALID_JSON", f"{label}: duplicate key {key!r}")
            result[key] = value
        return result

    def reject(value: str) -> Any:
        raise SelectionError("INVALID_JSON", f"{label}: non-finite number {value}")

    try:
        value = json.loads(data.decode(), object_pairs_hook=pairs, parse_constant=reject)
    except SelectionError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SelectionError("INVALID_JSON", f"{label}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise SelectionError("INVALID_JSON", f"{label}: root is not an object")
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _read_regular(path: Path, label: str) -> bytes:
    try:
        mode = path.lstat().st_mode
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise SelectionError("MISSING_OR_NONREGULAR", f"{label}: {exc}") from exc
    if path.absolute() != resolved or stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise SelectionError("MISSING_OR_NONREGULAR", f"{label}: not a canonical regular file")
    return path.read_bytes()


def _safe_receipt_path(run_dir: Path, raw: str) -> Path:
    pure = PurePosixPath(raw)
    if (
        pure.is_absolute()
        or raw != pure.as_posix()
        or len(pure.parts) != 3
        or pure.parts[0] != "verifications"
        or pure.parts[2] != "receipt.json"
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", pure.parts[1])
        or any(part in {"", ".", ".."} for part in pure.parts)
        or "\\" in raw
    ):
        raise SelectionError("RECEIPT_PATH", f"unsafe selected receipt path: {raw!r}")
    candidate = run_dir.joinpath(*pure.parts)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise SelectionError("RECEIPT_PATH", f"cannot resolve selected receipt: {exc}") from exc
    if not resolved.is_relative_to(run_dir) or resolved != candidate.absolute():
        raise SelectionError("RECEIPT_PATH", "selected receipt escapes authority run or uses a symlink")
    return candidate


def _load_verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("r4_handoff_verifier_for_selector", VERIFIER_PATH)
    if spec is None or spec.loader is None:
        raise SelectionError("VERIFIER_UNAVAILABLE", f"cannot load verifier: {VERIFIER_PATH}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise SelectionError("VERIFIER_UNAVAILABLE", f"cannot import verifier: {exc}") from exc
    return module


def _semantic_replay(receipt: Path) -> Mapping[str, Any]:
    verifier = _load_verifier()
    try:
        payload = verifier.check_receipt_semantics(receipt)
    except Exception as exc:
        raise SelectionError("RECEIPT_SEMANTIC_REPLAY", str(exc)) from exc
    if not isinstance(payload, Mapping) or payload.get("status") != "PASS":
        raise SelectionError("RECEIPT_SEMANTIC_REPLAY", "verifier did not return a PASS mapping")
    return payload


def _identity(run_dir: Path, receipt: Path) -> dict[str, Any]:
    data = _read_regular(receipt, "selected receipt")
    return {
        "relative_path": receipt.relative_to(run_dir).as_posix(),
        "sha256": _sha(data),
        "size_bytes": len(data),
    }


def _publish(path: Path, data: bytes) -> None:
    run_dir = path.parent.parent
    if run_dir.is_symlink() or run_dir.resolve() != run_dir.absolute():
        raise SelectionError("NO_OVERWRITE_COLLISION", "authority run root is not canonical")
    try:
        path.parent.mkdir()
    except FileExistsError as exc:
        raise SelectionError("NO_OVERWRITE_COLLISION", f"READY directory exists: {path.parent}") from exc
    pending = path.parent / f".pending-{os.getpid()}-{uuid.uuid4().hex}"
    try:
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(pending, path)
    except FileExistsError as exc:
        raise SelectionError("NO_OVERWRITE_COLLISION", f"READY selection exists: {path}") from exc
    finally:
        pending.unlink(missing_ok=True)


def select_receipt(authority_run: Path, receipt_path: Path) -> dict[str, Any]:
    run = authority_run.resolve(strict=True)
    receipt = receipt_path.absolute()
    _read_regular(receipt, "selected receipt")
    if not receipt.is_relative_to(run):
        raise SelectionError("RECEIPT_PATH", "receipt is outside authority run")
    relative = receipt.relative_to(run).as_posix()
    receipt = _safe_receipt_path(run, relative)
    first_bytes = _read_regular(receipt, "selected receipt")
    replay = _semantic_replay(receipt)
    second_bytes = _read_regular(receipt, "selected receipt")
    if first_bytes != second_bytes:
        raise SelectionError("RECEIPT_BYTE_DRIFT", "receipt changed during selection")
    identity = _identity(run, receipt)
    selector_data = _read_regular(Path(__file__).resolve(), "selector tool")
    payload = {
        "claim_boundary": "manual external submission readiness only; no mathematical claim upgrade",
        "manifest_sha256": replay.get("manifest_sha256"),
        "package_id": replay.get("package_id"),
        "receipt_byte_identity_match": True,
        "receipt_semantic_replay": True,
        "schema_version": SCHEMA,
        "selected_receipt_identity": identity,
        "selector_tool_sha256": _sha(selector_data),
        "status": "READY_FOR_MANUAL_EXTERNAL_SUBMISSION",
    }
    _publish(run / SELECTION_RELATIVE_PATH, _canonical(payload))
    return check_selected_receipt(run, expected_identity=identity)


def check_selected_receipt(
    authority_run: Path,
    *,
    expected_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Read-only semantic and detached-byte validation of the READY selection."""

    run = authority_run.resolve(strict=True)
    selected = _json(_read_regular(run / SELECTION_RELATIVE_PATH, "READY selection"), "READY selection")
    required_keys = {
        "claim_boundary",
        "manifest_sha256",
        "package_id",
        "receipt_byte_identity_match",
        "receipt_semantic_replay",
        "schema_version",
        "selected_receipt_identity",
        "selector_tool_sha256",
        "status",
    }
    if set(selected) != required_keys or selected.get("schema_version") != SCHEMA:
        raise SelectionError("SELECTION_SCHEMA", "READY selection has an unexpected field set or schema")
    identity = selected.get("selected_receipt_identity")
    if not isinstance(identity, Mapping) or set(identity) != {"relative_path", "sha256", "size_bytes"}:
        raise SelectionError("RECEIPT_IDENTITY", "selected receipt identity is not the exact three-field record")
    if expected_identity is not None and dict(identity) != dict(expected_identity):
        raise SelectionError("RECEIPT_IDENTITY", "selected identity differs from downstream bound identity")
    raw_relative = identity.get("relative_path")
    if not isinstance(raw_relative, str):
        raise SelectionError("RECEIPT_IDENTITY", "selected receipt relative path is not a string")
    receipt = _safe_receipt_path(run, raw_relative)
    actual_identity = _identity(run, receipt)
    if actual_identity != dict(identity):
        raise SelectionError("RECEIPT_BYTE_IDENTITY", "current receipt bytes differ from detached identity")
    replay = _semantic_replay(receipt)
    selector_data = _read_regular(Path(__file__).resolve(), "selector tool")
    if (
        selected.get("receipt_byte_identity_match") is not True
        or selected.get("receipt_semantic_replay") is not True
        or selected.get("status") != "READY_FOR_MANUAL_EXTERNAL_SUBMISSION"
        or selected.get("selector_tool_sha256") != _sha(selector_data)
        or selected.get("package_id") != replay.get("package_id")
        or selected.get("manifest_sha256") != replay.get("manifest_sha256")
    ):
        raise SelectionError("SELECTION_REPLAY", "READY fields differ from current replay")
    return dict(selected)


def _check_readme(readme: Path, identity: Mapping[str, Any]) -> None:
    text = _read_regular(readme, "README").decode("utf-8")
    required = (str(identity["relative_path"]), str(identity["size_bytes"]), str(identity["sha256"]))
    if any(value not in text for value in required):
        raise SelectionError("README_IDENTITY", "README does not carry the selected receipt exact-byte identity")


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    select = subparsers.add_parser("select")
    select.add_argument("--run-dir", required=True, type=Path)
    select.add_argument("--receipt", required=True, type=Path)
    check = subparsers.add_parser("check")
    check.add_argument("--run-dir", required=True, type=Path)
    check.add_argument("--expected-identity", help="JSON object with relative_path,size_bytes,sha256")
    check.add_argument("--readme", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        if args.command == "select":
            result = select_receipt(args.run_dir, args.receipt)
        else:
            expected = (
                None if args.expected_identity is None else _json(args.expected_identity.encode(), "expected identity")
            )
            result = check_selected_receipt(args.run_dir, expected_identity=expected)
            if args.readme is not None:
                _check_readme(args.readme, result["selected_receipt_identity"])
    except (OSError, UnicodeError, SelectionError) as exc:
        print(
            json.dumps(
                {"error_code": getattr(exc, "code", type(exc).__name__), "message": str(exc), "status": "FAIL"},
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
