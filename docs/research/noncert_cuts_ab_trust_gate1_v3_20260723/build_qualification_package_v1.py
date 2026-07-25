#!/usr/bin/env python3
"""Build one immutable Gate-1 qualification package.

The package is evidence about bytes, not permission to launch arms or classify
an experiment.  Its write graph is deliberately one-way:

payload/control -> package-manifest.json -> SHA256SUMS -> package_id
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


PACKAGE_SCHEMA = "noncert-cuts-gate1-qualification-package-v1"
SOURCE_SCHEMA = "noncert-cuts-gate1-source-identities-v1"
BUILD_SCHEMA = "noncert-cuts-gate1-qualification-build-v1"
ROLE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


class QualificationBuildError(RuntimeError):
    """Fail-closed package construction error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SourceSpec:
    """One source byte stream copied into and pinned by the package."""

    role: str
    path: Path
    parse_json: bool = False


@dataclass(frozen=True)
class Snapshot:
    """Bytes and stable inode facts captured through one open descriptor."""

    path: Path
    data: bytes
    sha256: str
    size: int
    st_dev: int
    st_ino: int
    st_mode: int
    st_mtime_ns: int
    st_ctime_ns: int


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
            raise QualificationBuildError("SYMLINK_REJECTED", f"symlink path component rejected: {current}")


def _same_snapshot_stat(left: os.stat_result, right: os.stat_result) -> bool:
    fields = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")
    return all(getattr(left, field) == getattr(right, field) for field in fields)


def snapshot_regular(
    path: Path,
    *,
    after_read: Callable[[Path], None] | None = None,
) -> Snapshot:
    """Read once through O_NOFOLLOW and prove the path still names that inode."""

    absolute = _absolute(path)
    _reject_symlink_chain(absolute)
    if not hasattr(os, "O_NOFOLLOW"):
        raise QualificationBuildError("NOFOLLOW_UNAVAILABLE", "O_NOFOLLOW is required")
    before_path = os.stat(absolute, follow_symlinks=False)
    if not stat.S_ISREG(before_path.st_mode):
        raise QualificationBuildError("NON_REGULAR_SOURCE", f"source is not a regular file: {absolute}")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    descriptor = os.open(absolute, flags)
    try:
        before_fd = os.fstat(descriptor)
        if not _same_snapshot_stat(before_path, before_fd):
            raise QualificationBuildError("SOURCE_RACE", f"source changed before descriptor read: {absolute}")
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
        if not _same_snapshot_stat(before_fd, after_fd):
            raise QualificationBuildError("SOURCE_RACE", f"source changed during descriptor read: {absolute}")
        if not _same_snapshot_stat(after_fd, after_path):
            raise QualificationBuildError("SOURCE_RACE", f"path inode changed during descriptor read: {absolute}")
        if len(data) != after_fd.st_size or digest.hexdigest() != _sha256(data):
            raise QualificationBuildError("SOURCE_RACE", f"source snapshot length/hash mismatch: {absolute}")
        return Snapshot(
            path=absolute,
            data=data,
            sha256=digest.hexdigest(),
            size=len(data),
            st_dev=after_fd.st_dev,
            st_ino=after_fd.st_ino,
            st_mode=after_fd.st_mode,
            st_mtime_ns=after_fd.st_mtime_ns,
            st_ctime_ns=after_fd.st_ctime_ns,
        )
    finally:
        os.close(descriptor)


def _source_record(spec: SourceSpec, snapshot: Snapshot) -> dict[str, object]:
    parsed_type: str | None = None
    if spec.parse_json:
        try:
            parsed = json.loads(snapshot.data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise QualificationBuildError("SOURCE_JSON_INVALID", f"invalid JSON source {snapshot.path}: {exc}") from exc
        parsed_type = type(parsed).__name__
    return {
        "json_root_type": parsed_type,
        "package_path": f"payload/{spec.role}",
        "parse_json": spec.parse_json,
        "role": spec.role,
        "sha256": snapshot.sha256,
        "size_bytes": snapshot.size,
        "source_path": str(snapshot.path),
        "stat": {
            "st_ctime_ns": snapshot.st_ctime_ns,
            "st_dev": snapshot.st_dev,
            "st_ino": snapshot.st_ino,
            "st_mode": snapshot.st_mode,
            "st_mtime_ns": snapshot.st_mtime_ns,
        },
    }


def _member_record(relative: str, data: bytes) -> dict[str, object]:
    return {"path": relative, "sha256": _sha256(data), "size_bytes": len(data)}


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_exclusive(path: Path, data: bytes) -> None:
    absolute = _absolute(path)
    _reject_symlink_chain(absolute.parent)
    if absolute.exists() or absolute.is_symlink():
        raise QualificationBuildError("NO_OVERWRITE_COLLISION", f"refusing to overwrite {absolute}")
    if not absolute.parent.is_dir():
        raise QualificationBuildError("OUTPUT_PARENT_INVALID", f"output parent is not a directory: {absolute.parent}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if not hasattr(os, "O_NOFOLLOW"):
        raise QualificationBuildError("NOFOLLOW_UNAVAILABLE", "O_NOFOLLOW is required")
    flags |= os.O_NOFOLLOW
    descriptor = os.open(absolute, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    _fsync_directory(absolute.parent)


def _publish_package(run_dir: Path, relative: str, data: bytes) -> None:
    seal = run_dir / "package/SHA256SUMS"
    if seal.exists() or seal.is_symlink():
        raise QualificationBuildError("PACKAGE_SEALED", "SHA256SUMS exists; package is immutable")
    _write_exclusive(run_dir / "package" / relative, data)


def _validate_role(role: str) -> None:
    if ROLE_PATTERN.fullmatch(role) is None or role in {".", "..", "SHA256SUMS", "package-manifest.json"}:
        raise QualificationBuildError("SOURCE_ROLE_INVALID", f"unsafe or reserved source role: {role!r}")


def _validate_head(head: str) -> None:
    if SHA256_PATTERN.fullmatch(head) is None and re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise QualificationBuildError("REPOSITORY_HEAD_INVALID", "repository head must be a lowercase Git SHA")


def _assert_sources_unchanged(records: Sequence[Mapping[str, object]]) -> None:
    for record in records:
        current = snapshot_regular(Path(str(record["source_path"])))
        stat_record = record.get("stat")
        if not isinstance(stat_record, Mapping):
            raise QualificationBuildError("SOURCE_IDENTITY_INVALID", "source stat record is malformed")
        same = (
            current.size == record.get("size_bytes")
            and current.sha256 == record.get("sha256")
            and current.st_dev == stat_record.get("st_dev")
            and current.st_ino == stat_record.get("st_ino")
            and current.st_mode == stat_record.get("st_mode")
            and current.st_mtime_ns == stat_record.get("st_mtime_ns")
            and current.st_ctime_ns == stat_record.get("st_ctime_ns")
        )
        if not same:
            raise QualificationBuildError("STALE_INPUT", f"source changed before package seal: {current.path}")


def build_package(
    output_dir: Path,
    sources: Sequence[SourceSpec],
    *,
    repository_head: str,
    run_nonce: str,
    argv: Sequence[str] = (),
) -> dict[str, object]:
    """Create and seal one previously nonexistent qualification package."""

    _validate_head(repository_head)
    if not run_nonce or len(run_nonce) > 128:
        raise QualificationBuildError("RUN_NONCE_INVALID", "run nonce must contain 1..128 characters")
    if not sources:
        raise QualificationBuildError("SOURCE_SET_INVALID", "at least one source is required")
    roles = [spec.role for spec in sources]
    for role in roles:
        _validate_role(role)
    if len(set(roles)) != len(roles):
        raise QualificationBuildError("SOURCE_SET_INVALID", "source roles must be unique")

    run_dir = _absolute(output_dir)
    _reject_symlink_chain(run_dir.parent)
    if run_dir.exists() or run_dir.is_symlink():
        raise QualificationBuildError("NO_OVERWRITE_COLLISION", f"output directory already exists: {run_dir}")
    snapshots = {spec.role: snapshot_regular(spec.path) for spec in sources}
    source_records = [
        _source_record(spec, snapshots[spec.role]) for spec in sorted(sources, key=lambda item: item.role)
    ]

    try:
        run_dir.mkdir(mode=0o755)
        (run_dir / "package").mkdir()
        (run_dir / "package/payload").mkdir()
        (run_dir / "package/control").mkdir()
    except FileExistsError as exc:
        raise QualificationBuildError(
            "NO_OVERWRITE_COLLISION", f"output directory raced into existence: {run_dir}"
        ) from exc

    payloads: dict[str, bytes] = {f"payload/{role}": snapshots[role].data for role in sorted(snapshots)}
    source_identity_payload = {
        "repository_head": repository_head,
        "run_nonce": run_nonce,
        "schema": SOURCE_SCHEMA,
        "sources": source_records,
    }
    payloads["control/source-identities.json"] = _canonical_json(source_identity_payload)
    payloads["control/build-record.json"] = _canonical_json(
        {
            "argv": list(argv),
            "authorization_root": False,
            "output_dir": str(run_dir),
            "python": {"executable": sys.executable, "version": sys.version.split()[0]},
            "schema": BUILD_SCHEMA,
            "state": "PAYLOAD_PLAN_BEFORE_SEAL",
        }
    )
    for relative in sorted(payloads):
        _publish_package(run_dir, relative, payloads[relative])

    manifest = {
        "authorization_semantics": "none; qualification package PASS cannot authorize arm launch or classification",
        "excluded_from_manifest_domain": [
            "package-manifest.json",
            "SHA256SUMS",
            "../verifications/",
            "../launch-selections/",
            "../replay/",
            "../classification/",
            "package_id",
        ],
        "external_sources": source_records,
        "package_members": [_member_record(path, payloads[path]) for path in sorted(payloads)],
        "repository_head": repository_head,
        "run_nonce": run_nonce,
        "schema": PACKAGE_SCHEMA,
        "seal_contract": {
            "package_id_definition": "sha256(SHA256SUMS exact bytes)",
            "sha256sums_covers": "all regular files under package except SHA256SUMS itself",
            "writes_after_sha256sums": "forbidden",
        },
    }
    manifest_bytes = _canonical_json(manifest)
    _publish_package(run_dir, "package-manifest.json", manifest_bytes)
    _assert_sources_unchanged(source_records)

    sealed: dict[str, bytes] = {}
    for path in sorted((run_dir / "package").rglob("*")):
        if path.is_symlink():
            raise QualificationBuildError("SYMLINK_REJECTED", f"symlink in package: {path}")
        if path.is_file():
            relative = path.relative_to(run_dir / "package").as_posix()
            sealed[relative] = snapshot_regular(path).data
        elif not path.is_dir():
            raise QualificationBuildError("PACKAGE_MEMBER_INVALID", f"non-regular package object: {path}")
    expected = set(payloads) | {"package-manifest.json"}
    if set(sealed) != expected:
        raise QualificationBuildError("PACKAGE_MEMBER_SET", "pre-seal package member set is not exact")
    sha_bytes = "".join(f"{_sha256(sealed[name])}  {name}\n" for name in sorted(sealed)).encode("ascii")
    _publish_package(run_dir, "SHA256SUMS", sha_bytes)
    package_id = _sha256(sha_bytes)
    return {
        "authorization_root": False,
        "manifest_sha256": _sha256(manifest_bytes),
        "package_id": package_id,
        "run_dir": str(run_dir),
        "sha256sums_sha256": package_id,
        "status": "SEALED_AWAITING_INDEPENDENT_QUALIFICATION",
    }


def _parse_source(value: str, json_roles: set[str]) -> SourceSpec:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--source must be ROLE=PATH")
    role, raw_path = value.split("=", 1)
    return SourceSpec(role=role, path=Path(raw_path), parse_json=role in json_roles)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repository-head", required=True)
    parser.add_argument("--run-nonce", required=True)
    parser.add_argument("--json-role", action="append", default=[])
    parser.add_argument("--source", action="append", required=True)
    args = parser.parse_args(argv)
    json_roles = set(args.json_role)
    args.sources = [_parse_source(value, json_roles) for value in args.source]
    unknown = json_roles - {spec.role for spec in args.sources}
    if unknown:
        parser.error(f"--json-role has no matching --source: {sorted(unknown)}")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = build_package(
            args.output_dir,
            args.sources,
            repository_head=args.repository_head,
            run_nonce=args.run_nonce,
            argv=sys.argv if argv is None else argv,
        )
    except QualificationBuildError as exc:
        print(json.dumps({"error_code": exc.code, "message": str(exc), "status": "FAIL"}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
