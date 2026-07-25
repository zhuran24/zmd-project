#!/usr/bin/env python3
"""Independently verify and receipt a Gate-1 qualification package.

A PASS receipt is derived evidence only.  It is never an arm-launch or
experiment-classification authority root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


PACKAGE_SCHEMA = "noncert-cuts-gate1-qualification-package-v1"
SOURCE_SCHEMA = "noncert-cuts-gate1-source-identities-v1"
BUILD_SCHEMA = "noncert-cuts-gate1-qualification-build-v1"
RECEIPT_SCHEMA = "noncert-cuts-gate1-qualification-receipt-v1"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
VERIFICATION_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
EXPECTED_PACKAGE_DIRS = frozenset({"control", "payload"})


class QualificationVerificationError(RuntimeError):
    """Fail-closed package verification error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Snapshot:
    path: Path
    data: bytes
    sha256: str
    size: int
    stat_result: os.stat_result


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _reject_symlink_chain(path: Path, *, allow_missing_leaf: bool = False) -> None:
    absolute = _absolute(path)
    current = Path(absolute.anchor)
    parts = absolute.parts[1:]
    for index, part in enumerate(parts):
        current /= part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            if allow_missing_leaf and index == len(parts) - 1:
                return
            raise
        if stat.S_ISLNK(mode):
            raise QualificationVerificationError("SYMLINK_REJECTED", f"symlink path component rejected: {current}")


def _same_stat(left: os.stat_result, right: os.stat_result) -> bool:
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def snapshot_regular(
    path: Path,
    *,
    after_read: Callable[[Path], None] | None = None,
) -> Snapshot:
    """Read/hash/parse callers from one stable O_NOFOLLOW descriptor snapshot."""

    absolute = _absolute(path)
    _reject_symlink_chain(absolute)
    if not hasattr(os, "O_NOFOLLOW"):
        raise QualificationVerificationError("NOFOLLOW_UNAVAILABLE", "O_NOFOLLOW is required")
    before_path = os.stat(absolute, follow_symlinks=False)
    if not stat.S_ISREG(before_path.st_mode):
        raise QualificationVerificationError("NON_REGULAR_INPUT", f"input is not a regular file: {absolute}")
    descriptor = os.open(absolute, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before_fd = os.fstat(descriptor)
        if not _same_stat(before_path, before_fd):
            raise QualificationVerificationError("INPUT_RACE", f"input changed before read: {absolute}")
        chunks: list[bytes] = []
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            digest.update(chunk)
        data = b"".join(chunks)
        if after_read is not None:
            after_read(absolute)
        after_fd = os.fstat(descriptor)
        after_path = os.stat(absolute, follow_symlinks=False)
        if not _same_stat(before_fd, after_fd) or not _same_stat(after_fd, after_path):
            raise QualificationVerificationError("INPUT_RACE", f"input/path inode changed during read: {absolute}")
        if len(data) != after_fd.st_size or digest.hexdigest() != _sha256(data):
            raise QualificationVerificationError("INPUT_RACE", f"input snapshot mismatch: {absolute}")
        return Snapshot(
            path=absolute,
            data=data,
            sha256=digest.hexdigest(),
            size=len(data),
            stat_result=after_fd,
        )
    finally:
        os.close(descriptor)


def _json_from_snapshot(snapshot: Snapshot, label: str) -> dict[str, Any]:
    try:
        value = json.loads(snapshot.data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QualificationVerificationError("JSON_INVALID", f"{label} is invalid JSON: {exc}") from exc
    if type(value) is not dict:
        raise QualificationVerificationError("JSON_INVALID", f"{label} root must be an object")
    return value


def _identity(snapshot: Snapshot) -> dict[str, object]:
    return {"path": str(snapshot.path), "sha256": snapshot.sha256, "size_bytes": snapshot.size}


def _write_exclusive(path: Path, data: bytes) -> None:
    absolute = _absolute(path)
    _reject_symlink_chain(absolute.parent)
    if absolute.exists() or absolute.is_symlink():
        raise QualificationVerificationError("NO_OVERWRITE_COLLISION", f"refusing to overwrite {absolute}")
    if not absolute.parent.is_dir():
        raise QualificationVerificationError("OUTPUT_PARENT_INVALID", f"output parent is invalid: {absolute.parent}")
    if not hasattr(os, "O_NOFOLLOW"):
        raise QualificationVerificationError("NOFOLLOW_UNAVAILABLE", "O_NOFOLLOW is required")
    descriptor = os.open(absolute, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _safe_checksum_path(raw: str) -> str:
    if not raw or raw == "SHA256SUMS" or "\\" in raw:
        raise QualificationVerificationError("SHA_PATH_INVALID", f"unsafe checksum path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise QualificationVerificationError("SHA_PATH_INVALID", f"unsafe checksum path: {raw!r}")
    return path.as_posix()


def _parse_sha(snapshot: Snapshot) -> dict[str, str]:
    try:
        lines = snapshot.data.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise QualificationVerificationError("SHA_INVALID", "SHA256SUMS is not ASCII") from exc
    if not lines or not snapshot.data.endswith(b"\n"):
        raise QualificationVerificationError("SHA_INVALID", "SHA256SUMS must be non-empty and newline-terminated")
    entries: dict[str, str] = {}
    for line in lines:
        if len(line) < 67 or line[64:66] != "  ":
            raise QualificationVerificationError("SHA_INVALID", f"malformed SHA256SUMS line: {line!r}")
        digest = line[:64]
        relative = _safe_checksum_path(line[66:])
        if SHA256_PATTERN.fullmatch(digest) is None or relative in entries:
            raise QualificationVerificationError("SHA_INVALID", f"invalid or duplicate SHA256SUMS entry: {relative}")
        entries[relative] = digest
    return entries


def _scan_package(package: Path) -> tuple[dict[str, Snapshot], set[str]]:
    package = _absolute(package)
    _reject_symlink_chain(package)
    if not package.is_dir():
        raise QualificationVerificationError("PACKAGE_MISSING", f"package directory is missing: {package}")
    files: dict[str, Snapshot] = {}
    directories: set[str] = set()
    for path in sorted(package.rglob("*")):
        mode = os.lstat(path).st_mode
        relative = path.relative_to(package).as_posix()
        if stat.S_ISLNK(mode):
            raise QualificationVerificationError("SYMLINK_REJECTED", f"symlink in package: {relative}")
        if stat.S_ISDIR(mode):
            directories.add(relative)
        elif stat.S_ISREG(mode):
            files[relative] = snapshot_regular(path)
        else:
            raise QualificationVerificationError("PACKAGE_MEMBER_INVALID", f"non-regular package object: {relative}")
    return files, directories


def _source_matches(record: Mapping[str, object], snapshot: Snapshot) -> bool:
    raw_stat = record.get("stat")
    return (
        isinstance(raw_stat, Mapping)
        and record.get("size_bytes") == snapshot.size
        and record.get("sha256") == snapshot.sha256
        and raw_stat.get("st_dev") == snapshot.stat_result.st_dev
        and raw_stat.get("st_ino") == snapshot.stat_result.st_ino
        and raw_stat.get("st_mode") == snapshot.stat_result.st_mode
        and raw_stat.get("st_mtime_ns") == snapshot.stat_result.st_mtime_ns
        and raw_stat.get("st_ctime_ns") == snapshot.stat_result.st_ctime_ns
    )


def verify_package(run_dir: Path, *, verification_id: str) -> dict[str, object]:
    """Return a complete PASS/FAIL replay without writing a receipt."""

    checks: list[dict[str, object]] = []
    errors: list[str] = []
    current_sources: list[dict[str, object]] = []
    package_id: str | None = None
    manifest_identity: dict[str, object] | None = None
    sha_identity: dict[str, object] | None = None

    def check(name: str, passed: bool, detail: object = None) -> None:
        checks.append({"detail": detail, "name": name, "passed": bool(passed)})
        if not passed:
            errors.append(name)

    try:
        files, directories = _scan_package(_absolute(run_dir) / "package")
        check("package_directories_exact", directories == EXPECTED_PACKAGE_DIRS, sorted(directories))
        required = {"package-manifest.json", "SHA256SUMS"}
        check("package_required_files", required <= set(files), sorted(files))
        if not required <= set(files):
            raise QualificationVerificationError("PACKAGE_MISSING", "manifest or seal is missing")

        sha_snapshot = files["SHA256SUMS"]
        sha_identity = _identity(sha_snapshot)
        package_id = sha_snapshot.sha256
        entries = _parse_sha(sha_snapshot)
        covered = set(files) - {"SHA256SUMS"}
        check("sha_member_set_exact", set(entries) == covered, {"covered": sorted(covered), "entries": sorted(entries)})
        check(
            "sha_hashes_exact",
            set(entries) == covered and all(entries[path] == files[path].sha256 for path in entries),
        )
        manifest_snapshot = files["package-manifest.json"]
        manifest_identity = _identity(manifest_snapshot)
        manifest = _json_from_snapshot(manifest_snapshot, "package manifest")
        manifest_keys = {
            "authorization_semantics",
            "excluded_from_manifest_domain",
            "external_sources",
            "package_members",
            "repository_head",
            "run_nonce",
            "schema",
            "seal_contract",
        }
        check("manifest_keys_exact", set(manifest) == manifest_keys, sorted(manifest))
        check("manifest_schema", manifest.get("schema") == PACKAGE_SCHEMA, manifest.get("schema"))
        check(
            "manifest_authorization_none",
            manifest.get("authorization_semantics")
            == "none; qualification package PASS cannot authorize arm launch or classification",
        )
        expected_exclusions = [
            "package-manifest.json",
            "SHA256SUMS",
            "../verifications/",
            "../launch-selections/",
            "../replay/",
            "../classification/",
            "package_id",
        ]
        check("manifest_exclusions_exact", manifest.get("excluded_from_manifest_domain") == expected_exclusions)
        check(
            "manifest_seal_contract",
            manifest.get("seal_contract")
            == {
                "package_id_definition": "sha256(SHA256SUMS exact bytes)",
                "sha256sums_covers": "all regular files under package except SHA256SUMS itself",
                "writes_after_sha256sums": "forbidden",
            },
        )

        members = manifest.get("package_members")
        member_files = set(files) - {"package-manifest.json", "SHA256SUMS"}
        expected_members = [
            {"path": name, "sha256": files[name].sha256, "size_bytes": files[name].size}
            for name in sorted(member_files)
        ]
        check("manifest_member_set_and_hashes", members == expected_members)
        external = manifest.get("external_sources")
        check("external_sources_schema", isinstance(external, list) and bool(external))
        if not isinstance(external, list):
            raise QualificationVerificationError("MANIFEST_INVALID", "external_sources must be a list")

        source_identity_snapshot = files.get("control/source-identities.json")
        if source_identity_snapshot is None:
            raise QualificationVerificationError("PACKAGE_MISSING", "control/source-identities.json is missing")
        source_identity = _json_from_snapshot(source_identity_snapshot, "source identities")
        check("source_identity_schema", source_identity.get("schema") == SOURCE_SCHEMA)
        check("source_identity_head", source_identity.get("repository_head") == manifest.get("repository_head"))
        check("source_identity_nonce", source_identity.get("run_nonce") == manifest.get("run_nonce"))
        check("source_identity_manifest_match", source_identity.get("sources") == external)

        seen_roles: set[str] = set()
        sources_ok = True
        for index, raw in enumerate(external):
            if not isinstance(raw, Mapping):
                sources_ok = False
                errors.append(f"external_source[{index}]")
                continue
            role = raw.get("role")
            package_path = raw.get("package_path")
            source_path = raw.get("source_path")
            if (
                not isinstance(role, str)
                or role in seen_roles
                or not isinstance(package_path, str)
                or not isinstance(source_path, str)
                or package_path != f"payload/{role}"
                or package_path not in files
            ):
                sources_ok = False
                errors.append(f"external_source[{index}]")
                continue
            seen_roles.add(role)
            current = snapshot_regular(Path(source_path))
            current_sources.append({"role": role, **_identity(current)})
            if not _source_matches(raw, current):
                sources_ok = False
            payload = files[package_path]
            if payload.sha256 != current.sha256 or payload.size != current.size:
                sources_ok = False
            if raw.get("parse_json") is True:
                _json_from_snapshot(current, f"source {role}")
        check("external_sources_current_and_copied", sources_ok, current_sources)

        build_snapshot = files.get("control/build-record.json")
        if build_snapshot is None:
            raise QualificationVerificationError("PACKAGE_MISSING", "control/build-record.json is missing")
        build = _json_from_snapshot(build_snapshot, "build record")
        check("build_schema", build.get("schema") == BUILD_SCHEMA)
        check("build_not_authority", build.get("authorization_root") is False)
        check("build_preseal_state", build.get("state") == "PAYLOAD_PLAN_BEFORE_SEAL")
    except Exception as exc:  # noqa: BLE001 - convert every malformed package into FAIL
        if isinstance(exc, QualificationVerificationError):
            errors.append(f"{exc.code}: {exc}")
        else:
            errors.append(f"{type(exc).__name__}: {exc}")

    status = "PASS" if not errors and checks and all(bool(row["passed"]) for row in checks) else "FAIL"
    verifier_identity = _identity(snapshot_regular(Path(__file__)))
    return {
        "arm_launch_authorized": False,
        "authorization_root": False,
        "checks": checks,
        "classification_authorized": False,
        "corpus_errors": errors,
        "current_source_identities": current_sources,
        "manifest_identity": manifest_identity,
        "package_id": package_id,
        "receipt_semantics": "derived qualification only; launch-selection is the direct authority root",
        "schema": RECEIPT_SCHEMA,
        "sha256s_identity": sha_identity,
        "status": status,
        "verification_id": verification_id,
        "verifier_identity": verifier_identity,
    }


def create_pass_receipt(run_dir: Path, verification_id: str) -> dict[str, object]:
    """Write one sibling PASS receipt; failures are returned by verify_package only."""

    if VERIFICATION_ID_PATTERN.fullmatch(verification_id) is None:
        raise QualificationVerificationError("VERIFICATION_ID_INVALID", "unsafe verification ID")
    payload = verify_package(run_dir, verification_id=verification_id)
    if payload["status"] != "PASS":
        raise QualificationVerificationError("QUALIFICATION_FAILED", json.dumps(payload, sort_keys=True))
    root = _absolute(run_dir)
    verification_dir = root / "verifications" / verification_id
    _reject_symlink_chain(verification_dir.parent, allow_missing_leaf=True)
    verification_dir.parent.mkdir(exist_ok=True)
    try:
        verification_dir.mkdir()
    except FileExistsError as exc:
        raise QualificationVerificationError(
            "NO_OVERWRITE_COLLISION",
            f"verification directory already exists: {verification_dir}",
        ) from exc
    receipt_path = verification_dir / "receipt.json"
    relative = receipt_path.relative_to(root).as_posix()
    payload["receipt_relative_path"] = relative
    _write_exclusive(receipt_path, _canonical_json(payload))
    return {**payload, "receipt_identity": _identity(snapshot_regular(receipt_path))}


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--verification-id", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = create_pass_receipt(args.run_dir, args.verification_id)
    except QualificationVerificationError as exc:
        print(json.dumps({"error_code": exc.code, "message": str(exc), "status": "FAIL"}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
