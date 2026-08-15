#!/usr/bin/env python3
"""Plan and verify a non-destructive document patch landing.

This tool exists for the repository's shared-workspace topology.  It never
stages, commits, resets, cleans, amends, or rolls back the working tree.  A
landing is split into explicit, fail-closed operations:

* ``plan`` compares the real worktree with a supplier baseline, discovers patch
  conflicts, and seals exact drift and package-successor bytes outside the repo;
* ``apply-base`` applies only paths that remain equal to the plan;
* ``confirm-base`` proves those paths were committed exactly once;
* ``begin-migration`` creates landing-time immutable archives and an ACK template;
* ``verify-migration`` / ``finalize-migration`` enforce semantic migration before
  package-owned successor bytes replace the drifted legacy pages.

All mutable receipts live outside the repository except the immutable archive
manifest under ``docs/history/status/landing``.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence

import jsonschema  # type: ignore[import-untyped]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = "data/repository_governance/document_system/landing.json"
DEFAULT_PROTOCOL_SCHEMA = "data/repository_governance/document_system/landing.schema.json"
DEFAULT_ACK_SCHEMA = "data/repository_governance/document_system/landing_ack.schema.json"
PLAN_SCHEMA_VERSION = "zmd_document_landing_plan_v1"
ARCHIVE_MANIFEST_SCHEMA_VERSION = "zmd_document_landing_archive_manifest_v1"
RECEIPT_SCHEMA_VERSION = "zmd_document_landing_receipt_v1"


class LandingError(RuntimeError):
    """Fail-closed landing or migration error."""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class ProtocolBundle:
    protocol: Mapping[str, Any]
    protocol_path: Path
    protocol_schema: Mapping[str, Any]
    protocol_schema_path: Path
    ack_schema: Mapping[str, Any]
    ack_schema_path: Path


@dataclass(frozen=True)
class PlanContext:
    plan_path: Path
    plan_dir: Path
    plan: Mapping[str, Any]
    bundle: ProtocolBundle

    @property
    def protocol(self) -> Mapping[str, Any]:
        return self.bundle.protocol

    @property
    def ack_schema(self) -> Mapping[str, Any]:
        return self.bundle.ack_schema


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _strict_json(path: Path) -> Any:
    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise LandingError(f"duplicate JSON key in {path}: {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise LandingError(f"non-finite JSON constant in {path}: {value}")

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate,
            parse_constant=reject_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LandingError(f"cannot read strict JSON {path}: {exc}") from exc


def _validate(schema: Mapping[str, Any], value: Any, label: str) -> None:
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
        errors = sorted(
            jsonschema.Draft202012Validator(schema).iter_errors(value),
            key=lambda error: tuple(str(part) for part in error.absolute_path),
        )
    except jsonschema.SchemaError as exc:
        raise LandingError(f"invalid schema for {label}: {exc.message}") from exc
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise LandingError(f"{label} schema error at {location}: {error.message}")


def _relpath(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or value.startswith("/")
        or ".." in path.parts
        or "\\" in value
        or "\0" in value
    ):
        raise LandingError(f"unsafe repository-relative path: {value!r}")
    return path.as_posix()


def _within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(
        path,
        (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8"),
    )


def _seal_path(path: Path) -> Path:
    return path.with_name(path.name + ".sha256")


def _write_sealed_json(path: Path, value: Any) -> None:
    _write_json(path, value)
    _atomic_write(_seal_path(path), (_sha256_file(path) + "  " + path.name + "\n").encode("ascii"))


def _load_sealed_json(path: Path) -> Any:
    seal = _seal_path(path)
    try:
        line = seal.read_text(encoding="ascii").strip()
    except OSError as exc:
        raise LandingError(f"sealed JSON digest is missing for {path}: {exc}") from exc
    parts = line.split()
    if len(parts) != 2 or parts[1] != path.name or len(parts[0]) != 64:
        raise LandingError(f"invalid sealed JSON digest file: {seal}")
    if not path.is_file() or _sha256_file(path) != parts[0]:
        raise LandingError(f"sealed JSON changed after creation: {path}")
    return _strict_json(path)


def _run(
    args: Sequence[str],
    *,
    cwd: Path,
    check: bool = False,
    input_bytes: bytes | None = None,
) -> CommandResult:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    result = CommandResult(completed.returncode, completed.stdout, completed.stderr)
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise LandingError(f"command failed ({' '.join(args)}): {detail}")
    return result


def _git(root: Path, *args: str, check: bool = True) -> bytes:
    result = _run(("git", "-c", "core.quotePath=false", *args), cwd=root, check=False)
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise LandingError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _ensure_repository(root: Path) -> Path:
    root = root.resolve()
    result = _run(("git", "rev-parse", "--show-toplevel"), cwd=root, check=False)
    if result.returncode != 0:
        raise LandingError(f"not a Git worktree: {root}")
    top = Path(result.stdout.decode("utf-8").strip()).resolve()
    if top != root:
        raise LandingError(f"--repo-root must be the Git top level: expected {top}, got {root}")
    return root


def _resolve_input_path(root: Path, value: str | Path | None, default: str) -> Path:
    path = Path(value) if value is not None else root / default
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _load_protocol(
    root: Path,
    protocol_arg: str | Path | None = None,
    protocol_schema_arg: str | Path | None = None,
    ack_schema_arg: str | Path | None = None,
) -> ProtocolBundle:
    protocol_path = _resolve_input_path(root, protocol_arg, DEFAULT_PROTOCOL)
    if protocol_arg is not None and protocol_schema_arg is None:
        protocol_schema_path = protocol_path.with_name("landing.schema.json")
    else:
        protocol_schema_path = _resolve_input_path(root, protocol_schema_arg, DEFAULT_PROTOCOL_SCHEMA)
    if protocol_arg is not None and ack_schema_arg is None:
        ack_schema_path = protocol_path.with_name("landing_ack.schema.json")
    else:
        ack_schema_path = _resolve_input_path(root, ack_schema_arg, DEFAULT_ACK_SCHEMA)
    protocol = _strict_json(protocol_path)
    protocol_schema = _strict_json(protocol_schema_path)
    ack_schema = _strict_json(ack_schema_path)
    if not isinstance(protocol, dict) or not isinstance(protocol_schema, dict) or not isinstance(ack_schema, dict):
        raise LandingError("landing protocol and schemas must be JSON objects")
    _validate(protocol_schema, protocol, protocol_path.as_posix())
    jsonschema.Draft202012Validator.check_schema(ack_schema)
    return ProtocolBundle(
        protocol,
        protocol_path,
        protocol_schema,
        protocol_schema_path,
        ack_schema,
        ack_schema_path,
    )


def _copy_protocol_bundle(output: Path, bundle: ProtocolBundle) -> Mapping[str, Any]:
    directory = output / "protocol_bundle"
    directory.mkdir(parents=True, exist_ok=False)
    paths = {
        "source": directory / "landing.json",
        "schema": directory / "landing.schema.json",
        "ack_schema": directory / "landing_ack.schema.json",
    }
    shutil.copyfile(bundle.protocol_path, paths["source"])
    shutil.copyfile(bundle.protocol_schema_path, paths["schema"])
    shutil.copyfile(bundle.ack_schema_path, paths["ack_schema"])
    return {
        key: {
            "path": path.relative_to(output).as_posix(),
            "sha256": _sha256_file(path),
        }
        for key, path in paths.items()
    }


def _load_plan_protocol(plan_dir: Path, descriptor: Mapping[str, Any]) -> ProtocolBundle:
    paths: dict[str, Path] = {}
    for key in ("source", "schema", "ack_schema"):
        record = descriptor.get(key)
        if not isinstance(record, dict):
            raise LandingError(f"landing plan protocol bundle omits {key}")
        relpath = _relpath(str(record.get("path", "")))
        path = (plan_dir / relpath).resolve()
        if not _within(path, plan_dir) or not path.is_file():
            raise LandingError(f"landing plan protocol bundle path is invalid: {relpath}")
        if _sha256_file(path) != record.get("sha256"):
            raise LandingError(f"landing plan protocol bundle changed: {relpath}")
        paths[key] = path
    return _load_protocol(
        plan_dir,
        paths["source"],
        paths["schema"],
        paths["ack_schema"],
    )


def _branch(root: Path) -> str:
    value = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False).decode().strip()
    if not value:
        raise LandingError("landing requires a named branch, not detached HEAD")
    return value


def _staged_paths(root: Path) -> tuple[str, ...]:
    raw = _git(root, "diff", "--cached", "--name-only", "-z")
    return tuple(part.decode("utf-8", errors="surrogateescape") for part in raw.split(b"\0") if part)


def _tracked_status_bytes(root: Path) -> bytes:
    return _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=no")


def _tracked_paths(root: Path) -> frozenset[str]:
    raw = _git(root, "ls-files", "--cached", "-z")
    return frozenset(
        part.decode("utf-8", errors="surrogateescape")
        for part in raw.split(b"\0")
        if part
    )


def _file_record(root: Path, relpath: str) -> Mapping[str, Any]:
    path = root / relpath
    if not path.exists() and not path.is_symlink():
        return {"path": relpath, "presence": "absent", "sha256": None, "size": None}
    if path.is_symlink() or not path.is_file():
        raise LandingError(f"declared overlay or drift path is not a local regular file: {relpath}")
    data = path.read_bytes()
    return {"path": relpath, "presence": "file", "sha256": _sha256_bytes(data), "size": len(data)}


def _path_records(root: Path, paths: Sequence[str]) -> list[Mapping[str, Any]]:
    return [_file_record(root, _relpath(path)) for path in paths]


def _record_content_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return (left.get("presence"), left.get("sha256"), left.get("size")) == (
        right.get("presence"),
        right.get("sha256"),
        right.get("size"),
    )


def _record_map(records: Sequence[Mapping[str, Any]]) -> Mapping[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        relpath = _relpath(str(record.get("path", "")))
        if relpath in result:
            raise LandingError(f"duplicate path record: {relpath}")
        result[relpath] = record
    return result


def _verify_path_records(root: Path, records: Sequence[Mapping[str, Any]], *, label: str) -> None:
    for relpath, expected in _record_map(records).items():
        actual = _file_record(root, relpath)
        if not _record_content_equal(actual, expected):
            raise LandingError(f"{label} changed after planning: {relpath}; create a new landing plan")


def _derive_patched_file(
    *,
    baseline_root: Path,
    patch: Path,
    relpath: str,
    output: Path,
) -> Mapping[str, Any]:
    relpath = _relpath(relpath)
    with tempfile.TemporaryDirectory(prefix="zmd-landing-successor-") as temporary:
        sandbox = Path(temporary)
        baseline = baseline_root / relpath
        target = sandbox / relpath
        if baseline.exists() or baseline.is_symlink():
            if baseline.is_symlink() or not baseline.is_file():
                raise LandingError(f"supplier baseline path is not a local regular file: {relpath}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(baseline, target)
        result = _run(
            _apply_command(patch, check_only=False, includes=(relpath,)),
            cwd=sandbox,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise LandingError(f"cannot derive canonical package bytes for {relpath}: {detail}")
        if not target.exists() and not target.is_symlink():
            return {"path": relpath, "presence": "absent", "sha256": None, "size": None, "snapshot_path": None}
        if target.is_symlink() or not target.is_file():
            raise LandingError(f"canonical package result is not a local regular file: {relpath}")
        content = target.read_bytes()
        snapshot = output / "package_successors" / PurePosixPath(relpath)
        _atomic_write(snapshot, content)
        return {
            "path": relpath,
            "presence": "file",
            "sha256": _sha256_bytes(content),
            "size": len(content),
            "snapshot_path": snapshot.relative_to(output).as_posix(),
        }


def _fingerprint(root: Path, protocol: Mapping[str, Any]) -> Mapping[str, Any]:
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    index_tree = _git(root, "write-tree").decode().strip()
    tracked_diff = _git(root, "diff", "--binary", "--full-index", "--no-ext-diff")
    cached_diff = _git(root, "diff", "--cached", "--binary", "--full-index", "--no-ext-diff")
    overlays = [_file_record(root, _relpath(str(value))) for value in protocol["workspace_overlays"]]
    payload = {
        "version": "zmd_landing_git_state_v1",
        "head": head,
        "branch": _branch(root),
        "index_tree": index_tree,
        "tracked_status_sha256": _sha256_bytes(_tracked_status_bytes(root)),
        "tracked_diff_sha256": _sha256_bytes(tracked_diff),
        "cached_diff_sha256": _sha256_bytes(cached_diff),
        "workspace_overlays": overlays,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**payload, "digest": _sha256_bytes(canonical)}


def _ensure_safe_branch(root: Path, protocol: Mapping[str, Any]) -> None:
    current = _branch(root)
    forbidden = {str(value) for value in protocol["forbidden_branches"]}
    if current in forbidden:
        raise LandingError(f"landing is forbidden on branch {current!r}; create a dedicated branch first")
    staged = _staged_paths(root)
    if staged:
        raise LandingError("landing requires a clean index; staged paths: " + ", ".join(staged))


def _ensure_no_unexpected_tracked_changes(root: Path, allowed_paths: Sequence[str]) -> None:
    raw = _git(root, "diff", "--name-only", "-z", "--no-ext-diff")
    changed = {
        part.decode("utf-8", errors="surrogateescape")
        for part in raw.split(b"\0")
        if part
    }
    unexpected = sorted(changed - {_relpath(value) for value in allowed_paths})
    if unexpected:
        raise LandingError(
            "migration requires all base and adaptation changes to be committed; "
            "only planned drift may remain dirty: " + ", ".join(unexpected)
        )


def _patch_paths(root: Path, patch: Path) -> tuple[str, ...]:
    summary = _run(
        ("git", "-c", "core.quotePath=false", "apply", "--summary", str(patch)),
        cwd=root,
        check=False,
    )
    if summary.returncode != 0:
        raise LandingError(summary.stderr.decode("utf-8", errors="replace").strip())
    summary_text = summary.stdout.decode("utf-8", errors="replace")
    if any(token in summary_text for token in (" rename ", " copy ")):
        raise LandingError("landing patches with rename/copy records are unsupported; materialize them as explicit paths")

    result = _run(
        ("git", "-c", "core.quotePath=false", "apply", "--numstat", "-z", str(patch)),
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        raise LandingError(result.stderr.decode("utf-8", errors="replace").strip())
    parts = result.stdout.split(b"\0")
    paths: list[str] = []
    for part in parts:
        if not part:
            continue
        fields = part.split(b"\t", 2)
        if len(fields) != 3 or not fields[2]:
            raise LandingError("unsupported git apply --numstat record in patch")
        relpath = _relpath(fields[2].decode("utf-8", errors="surrogateescape"))
        if relpath not in paths:
            paths.append(relpath)
    if not paths:
        raise LandingError("patch contains no file changes")
    return tuple(paths)


def _apply_command(patch: Path, *, check_only: bool, includes: Sequence[str] = (), excludes: Sequence[str] = ()) -> list[str]:
    command = ["git", "-c", "core.quotePath=false", "apply"]
    if check_only:
        command.append("--check")
    command.extend(["--whitespace=nowarn", "--recount"])
    for path in includes:
        command.append(f"--include={path}")
    for path in excludes:
        command.append(f"--exclude={path}")
    command.append(str(patch))
    return command


def _discover_conflicts(root: Path, patch: Path, paths: Sequence[str]) -> tuple[tuple[str, ...], str]:
    full = _run(_apply_command(patch, check_only=True), cwd=root, check=False)
    if full.returncode == 0:
        return (), ""

    conflicts: list[str] = []
    diagnostics: list[str] = []
    for path in paths:
        result = _run(_apply_command(patch, check_only=True, includes=(path,)), cwd=root, check=False)
        if result.returncode != 0:
            conflicts.append(path)
            text = result.stderr.decode("utf-8", errors="replace").strip()
            if text:
                diagnostics.append(f"[{path}] {text}")
    if not conflicts:
        detail = full.stderr.decode("utf-8", errors="replace").strip()
        raise LandingError("patch fails as a whole but no path-local conflict was found: " + detail)

    remainder = _run(
        _apply_command(patch, check_only=True, excludes=tuple(conflicts)),
        cwd=root,
        check=False,
    )
    if remainder.returncode != 0:
        detail = remainder.stderr.decode("utf-8", errors="replace").strip()
        raise LandingError("patch still fails after excluding discovered conflicts: " + detail)
    return tuple(conflicts), "\n".join(diagnostics)


def _existing_untracked_patch_paths(root: Path, paths: Sequence[str]) -> tuple[str, ...]:
    tracked = _tracked_paths(root)
    collisions: list[str] = []
    for relpath in paths:
        path = root / relpath
        if relpath in tracked or (not path.exists() and not path.is_symlink()):
            continue
        if path.is_symlink() or not path.is_file():
            raise LandingError(f"patch target collides with a non-regular untracked path: {relpath}")
        collisions.append(relpath)
    return tuple(collisions)


def _discover_drift(
    root: Path,
    patch: Path,
    paths: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    conflicts, diagnostics = _discover_conflicts(root, patch, paths)
    workspace_collisions = _existing_untracked_patch_paths(root, paths)
    drift_set = set(conflicts) | set(workspace_collisions)
    drift = tuple(path for path in paths if path in drift_set)
    if drift:
        remainder = _run(
            _apply_command(patch, check_only=True, excludes=drift),
            cwd=root,
            check=False,
        )
        if remainder.returncode != 0:
            detail = remainder.stderr.decode("utf-8", errors="replace").strip()
            raise LandingError("patch still fails after preserving dynamic drift: " + detail)
    collision_only = [path for path in workspace_collisions if path not in conflicts]
    if collision_only:
        extra = "\n".join(
            f"[{path}] preserved because the patch target exists but is not Git-tracked"
            for path in collision_only
        )
        diagnostics = "\n".join(value for value in (diagnostics, extra) if value)
    return drift, workspace_collisions, diagnostics


def _migration_index(protocol: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in protocol["known_migrations"]:
        relpath = _relpath(str(record["source_path"]))
        if relpath in result:
            raise LandingError(f"duplicate known migration source: {relpath}")
        result[relpath] = record
    return result


def _baseline_relation(current: bytes, baseline: bytes | None) -> tuple[str, bytes | None]:
    if baseline is None:
        return "unavailable", None
    if current == baseline:
        return "unchanged", b""
    if current.startswith(baseline):
        return "appended", current[len(baseline):]
    try:
        before = baseline.decode("utf-8").splitlines(keepends=True)
        after = current.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return "diverged_binary", None
    diff = "".join(difflib.unified_diff(before, after, fromfile="baseline", tofile="landing"))
    return "diverged_text", diff.encode("utf-8")


def _snapshot_name(relpath: str) -> Path:
    return Path("source_snapshots") / PurePosixPath(relpath)


def _plan_id(explicit: str | None) -> str:
    if explicit:
        if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in explicit):
            raise LandingError("landing ID may contain only letters, digits, dot, underscore and hyphen")
        return explicit
    return "landing-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_plan(
    *,
    root: Path,
    patch: Path,
    output: Path,
    protocol_arg: str | Path | None,
    protocol_schema_arg: str | Path | None = None,
    ack_schema_arg: str | Path | None = None,
    baseline_root: Path | None,
    landing_id: str | None,
) -> Path:
    root = _ensure_repository(root)
    bundle = _load_protocol(root, protocol_arg, protocol_schema_arg, ack_schema_arg)
    _ensure_safe_branch(root, bundle.protocol)
    patch = patch.resolve()
    if not patch.is_file():
        raise LandingError(f"patch does not exist: {patch}")
    if baseline_root is None:
        raise LandingError("plan requires --baseline-root so non-conflicting local drift cannot be overwritten")
    baseline_root = baseline_root.resolve()
    if not baseline_root.is_dir():
        raise LandingError(f"supplier baseline root is not a directory: {baseline_root}")
    output = output.resolve()
    if _within(output, root):
        raise LandingError("landing output directory must be outside the repository")
    if output.exists() and any(output.iterdir()):
        raise LandingError(f"landing output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    copied_patch = output / "input.patch"
    shutil.copyfile(patch, copied_patch)
    protocol_descriptor = _copy_protocol_bundle(output, bundle)
    paths = _patch_paths(root, copied_patch)
    patch_conflicts, conflict_diagnostics = _discover_conflicts(root, copied_patch, paths)
    workspace_collisions = _existing_untracked_patch_paths(root, paths)
    current_records = _path_records(root, paths)
    baseline_records = _path_records(baseline_root, paths)
    current_by_path = _record_map(current_records)
    baseline_by_path = _record_map(baseline_records)
    content_drift = tuple(
        path
        for path in paths
        if not _record_content_equal(current_by_path[path], baseline_by_path[path])
    )
    drift_set = set(patch_conflicts) | set(workspace_collisions) | set(content_drift)
    drift_paths = tuple(path for path in paths if path in drift_set)
    remainder = _run(
        _apply_command(copied_patch, check_only=True, excludes=drift_paths),
        cwd=root,
        check=False,
    )
    if remainder.returncode != 0:
        detail = remainder.stderr.decode("utf-8", errors="replace").strip()
        raise LandingError("patch still fails after preserving dynamic drift: " + detail)

    diagnostics: list[str] = []
    if conflict_diagnostics:
        diagnostics.append(conflict_diagnostics)
    for path in workspace_collisions:
        if path not in patch_conflicts:
            diagnostics.append(f"[{path}] preserved because the patch target exists but is not Git-tracked")
    for path in content_drift:
        if path not in patch_conflicts and path not in workspace_collisions:
            diagnostics.append(f"[{path}] preserved because current bytes differ from the supplied baseline")

    known = _migration_index(bundle.protocol)
    unknown = tuple(path for path in drift_paths if path not in known)
    unsupported = tuple(
        path for path in drift_paths if current_by_path[path]["presence"] != "file"
    )
    blocked_paths = tuple(dict.fromkeys((*unknown, *unsupported)))

    drift_records: list[dict[str, Any]] = []
    for relpath in drift_paths:
        current_record = current_by_path[relpath]
        if current_record["presence"] != "file":
            continue
        content = (root / relpath).read_bytes()
        snapshot_relpath = _snapshot_name(relpath)
        _atomic_write(output / snapshot_relpath, content)
        baseline_record = baseline_by_path[relpath]
        baseline_content = (
            (baseline_root / relpath).read_bytes()
            if baseline_record["presence"] == "file"
            else None
        )
        relation, delta = _baseline_relation(content, baseline_content)
        delta_relpath: str | None = None
        if delta:
            suffix = ".append" if relation == "appended" else ".diff"
            delta_path = Path("drift_analysis") / f"{relpath}{suffix}"
            _atomic_write(output / delta_path, delta)
            delta_relpath = delta_path.as_posix()
        drift_records.append(
            {
                "source_path": relpath,
                "sha256": current_record["sha256"],
                "size": current_record["size"],
                "snapshot_path": snapshot_relpath.as_posix(),
                "baseline_presence": baseline_record["presence"],
                "baseline_sha256": baseline_record["sha256"],
                "baseline_relation": relation,
                "delta_path": delta_relpath,
                "known_migration": relpath in known,
                "patch_conflict": relpath in patch_conflicts,
                "workspace_collision": relpath in workspace_collisions,
                "content_drift": relpath in content_drift,
            }
        )

    successor_records: list[Mapping[str, Any]] = []
    for relpath in paths:
        if relpath in known:
            successor_records.append(
                _derive_patched_file(
                    baseline_root=baseline_root,
                    patch=copied_patch,
                    relpath=relpath,
                    output=output,
                )
            )

    baseline_manifest = {
        "schema_version": "zmd_document_landing_baseline_manifest_v1",
        "created_at": _utc_now(),
        "baseline_root": str(baseline_root),
        "records": baseline_records,
    }
    baseline_manifest_path = output / "BASELINE_PATHS.json"
    _write_sealed_json(baseline_manifest_path, baseline_manifest)

    base_paths = tuple(path for path in paths if path not in drift_set)
    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "landing_id": _plan_id(landing_id),
        "created_at": _utc_now(),
        "status": "BLOCKED" if blocked_paths else "READY",
        "repo_root": str(root),
        "protocol_bundle": protocol_descriptor,
        "protocol_system_version": bundle.protocol["system_version"],
        "patch_path": "input.patch",
        "patch_sha256": _sha256_file(copied_patch),
        "patch_paths": list(paths),
        "base_apply_paths": list(base_paths),
        "drift_paths": list(drift_paths),
        "patch_conflict_paths": list(patch_conflicts),
        "workspace_collision_paths": list(workspace_collisions),
        "content_drift_paths": list(content_drift),
        "unknown_drift_paths": list(unknown),
        "unsupported_drift_paths": list(unsupported),
        "known_patch_paths_without_drift": [
            path for path in known if path in paths and path not in drift_set
        ],
        "diagnostics": "\n".join(diagnostics),
        "git_state": _fingerprint(root, bundle.protocol),
        "patch_path_records": current_records,
        "baseline_manifest_path": baseline_manifest_path.name,
        "baseline_manifest_sha256": _sha256_file(baseline_manifest_path),
        "drift_records": drift_records,
        "successor_records": successor_records,
    }
    plan_path = output / "LANDING_PLAN.json"
    _write_sealed_json(plan_path, plan)
    _atomic_write(output / "BASE_APPLY_PATHS.nul", b"".join(path.encode("utf-8") + b"\0" for path in base_paths))
    _atomic_write(output / "BASE_APPLY_PATHS.txt", ("\n".join(base_paths) + "\n").encode("utf-8"))
    _atomic_write(output / "DRIFT_PATHS.txt", ("\n".join(drift_paths) + ("\n" if drift_paths else "")).encode("utf-8"))
    return plan_path


def _load_plan(plan_path: Path, *, expected_root: Path | None = None) -> PlanContext:
    plan_path = plan_path.resolve()
    plan = _load_sealed_json(plan_path)
    if not isinstance(plan, dict) or plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise LandingError(f"unsupported landing plan: {plan_path}")
    root = Path(str(plan.get("repo_root", ""))).resolve()
    if expected_root is not None and root != expected_root.resolve():
        raise LandingError(f"plan repository mismatch: plan={root}, argument={expected_root.resolve()}")
    bundle = _load_plan_protocol(plan_path.parent, plan.get("protocol_bundle", {}))
    if bundle.protocol["system_version"] != plan.get("protocol_system_version"):
        raise LandingError("landing protocol system version changed after plan creation")
    patch_relpath = _relpath(str(plan.get("patch_path", "")))
    patch = (plan_path.parent / patch_relpath).resolve()
    if not _within(patch, plan_path.parent) or not patch.is_file():
        raise LandingError("planned patch path is missing or escapes the plan directory")
    if _sha256_file(patch) != plan.get("patch_sha256"):
        raise LandingError("planned patch bytes changed")
    baseline_relpath = _relpath(str(plan.get("baseline_manifest_path", "")))
    baseline_manifest = (plan_path.parent / baseline_relpath).resolve()
    if not _within(baseline_manifest, plan_path.parent) or not baseline_manifest.is_file():
        raise LandingError("landing baseline manifest is missing")
    if _sha256_file(baseline_manifest) != plan.get("baseline_manifest_sha256"):
        raise LandingError("landing baseline manifest changed after planning")
    _load_sealed_json(baseline_manifest)
    return PlanContext(plan_path, plan_path.parent, plan, bundle)


def _drift_record_map(plan: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in plan["drift_records"]:
        relpath = _relpath(str(record["source_path"]))
        if relpath in result:
            raise LandingError(f"duplicate drift record: {relpath}")
        result[relpath] = record
    return result


def _successor_record_map(plan: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    return _record_map(plan.get("successor_records", []))


def _plan_file(context: PlanContext, relpath_value: Any, *, label: str) -> Path:
    relpath = _relpath(str(relpath_value))
    path = (context.plan_dir / relpath).resolve()
    if not _within(path, context.plan_dir) or path.is_symlink() or not path.is_file():
        raise LandingError(f"{label} is missing or escapes the landing plan: {relpath}")
    return path


def _verify_drift_bytes(root: Path, context: PlanContext) -> None:
    plan = context.plan
    drift_records = _drift_record_map(plan)
    if set(drift_records) != set(plan["drift_paths"]):
        raise LandingError("landing plan drift records do not cover the dynamic drift set")
    for relpath, record in drift_records.items():
        path = root / relpath
        if path.is_symlink() or not path.is_file():
            raise LandingError(f"drift source disappeared or ceased to be a local regular file: {relpath}")
        actual = _sha256_file(path)
        if actual != record["sha256"]:
            raise LandingError(f"drift source changed after planning: {relpath}; create a new plan")
        snapshot = _plan_file(context, record["snapshot_path"], label="drift snapshot")
        if _sha256_file(snapshot) != record["sha256"] or snapshot.stat().st_size != record["size"]:
            raise LandingError(f"sealed drift snapshot changed after planning: {relpath}")


def _successor_content(context: PlanContext, relpath: str) -> bytes:
    relpath = _relpath(relpath)
    record = _successor_record_map(context.plan).get(relpath)
    if record is None:
        raise LandingError(f"landing plan has no package successor record: {relpath}")
    if record.get("presence") != "file":
        raise LandingError(f"package successor is not a regular file result: {relpath}")
    snapshot = _plan_file(context, record.get("snapshot_path"), label="package successor snapshot")
    content = snapshot.read_bytes()
    if _sha256_bytes(content) != record.get("sha256") or len(content) != record.get("size"):
        raise LandingError(f"package successor snapshot changed after planning: {relpath}")
    return content


def _receipt_path(context: PlanContext, name: str) -> Path:
    return context.plan_dir / name


def apply_base(*, root: Path, plan_path: Path) -> Path:
    root = _ensure_repository(root)
    context = _load_plan(plan_path, expected_root=root)
    _ensure_safe_branch(root, context.protocol)
    plan = context.plan
    if plan["status"] != "READY" or plan["unknown_drift_paths"] or plan["unsupported_drift_paths"]:
        raise LandingError("landing plan is blocked by unknown or unsupported drift")
    current = _fingerprint(root, context.protocol)
    if current["digest"] != plan["git_state"]["digest"]:
        raise LandingError("Git-visible state changed after planning; create a new landing plan")
    _verify_path_records(root, plan["patch_path_records"], label="patch target")
    patch = context.plan_dir / str(plan["patch_path"])
    paths = tuple(str(value) for value in plan["patch_paths"])
    patch_conflicts, _ = _discover_conflicts(root, patch, paths)
    workspace_collisions = _existing_untracked_patch_paths(root, paths)
    actual_drift = tuple(
        path
        for path in paths
        if path in set(patch_conflicts)
        or path in set(workspace_collisions)
        or path in set(plan["content_drift_paths"])
    )
    if tuple(patch_conflicts) != tuple(plan["patch_conflict_paths"]):
        raise LandingError("dynamic patch-conflict set changed after planning; create a new plan")
    if tuple(workspace_collisions) != tuple(plan["workspace_collision_paths"]):
        raise LandingError("untracked patch collision set changed after planning; create a new plan")
    if actual_drift != tuple(plan["drift_paths"]):
        raise LandingError("dynamic drift set changed after planning; create a new plan")
    _verify_drift_bytes(root, context)
    result = _run(
        _apply_command(patch, check_only=False, excludes=tuple(plan["drift_paths"])),
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise LandingError(f"base patch application failed without rollback: {detail}")
    _verify_drift_bytes(root, context)
    post_records = _path_records(root, tuple(str(value) for value in plan["base_apply_paths"]))
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "kind": "base_apply",
        "landing_id": plan["landing_id"],
        "created_at": _utc_now(),
        "initial_head": plan["git_state"]["head"],
        "patch_sha256": plan["patch_sha256"],
        "applied_paths": list(plan["base_apply_paths"]),
        "post_apply_path_records": post_records,
        "preserved_drift_paths": list(plan["drift_paths"]),
        "post_apply_git_state": _fingerprint(root, context.protocol),
        "next_required_action": (
            "stage exactly BASE_APPLY_PATHS.nul, commit once, then run confirm-base before applying the adaptation patch"
        ),
    }
    receipt_path = _receipt_path(context, "BASE_APPLY_RECEIPT.json")
    _write_sealed_json(receipt_path, receipt)
    return receipt_path


def _git_record_at_commit(root: Path, commit: str, relpath: str) -> Mapping[str, Any]:
    relpath = _relpath(relpath)
    tree = _git(root, "ls-tree", "-z", commit, "--", relpath)
    if not tree:
        return {"path": relpath, "presence": "absent", "sha256": None, "size": None}
    if tree.count(b"\0") != 1:
        raise LandingError(f"commit path lookup is ambiguous: {relpath}")
    metadata, _name = tree[:-1].split(b"\t", 1)
    mode, kind, _object_id = metadata.decode("ascii").split()
    if kind != "blob" or mode not in {"100644", "100755"}:
        raise LandingError(f"commit path is not a regular file: {relpath}")
    content = _git(root, "show", f"{commit}:{relpath}")
    return {"path": relpath, "presence": "file", "sha256": _sha256_bytes(content), "size": len(content)}


def _load_receipt(context: PlanContext, name: str, expected_kind: str) -> Mapping[str, Any]:
    path = _receipt_path(context, name)
    value = _load_sealed_json(path)
    if not isinstance(value, dict) or value.get("kind") != expected_kind:
        raise LandingError(f"{name} is missing or invalid")
    if value.get("landing_id") != context.plan["landing_id"]:
        raise LandingError(f"{name} belongs to a different landing")
    return value


def confirm_base(*, root: Path, plan_path: Path) -> Path:
    root = _ensure_repository(root)
    context = _load_plan(plan_path, expected_root=root)
    _ensure_safe_branch(root, context.protocol)
    receipt = _load_receipt(context, "BASE_APPLY_RECEIPT.json", "base_apply")
    initial_head = str(receipt["initial_head"])
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    parent = _git(root, "rev-parse", "HEAD^", check=False).decode().strip()
    if head == initial_head or parent != initial_head:
        raise LandingError("base layer must be committed as exactly one immediate commit before confirm-base")
    count = _git(root, "rev-list", "--count", f"{initial_head}..{head}").decode().strip()
    if count != "1":
        raise LandingError("base layer confirmation requires exactly one commit after the planned HEAD")
    changed_raw = _git(root, "diff", "--name-only", "-z", initial_head, head)
    changed = tuple(part.decode("utf-8", errors="surrogateescape") for part in changed_raw.split(b"\0") if part)
    expected = tuple(str(value) for value in receipt["applied_paths"])
    if set(changed) != set(expected) or len(changed) != len(expected):
        missing = sorted(set(expected) - set(changed))
        extra = sorted(set(changed) - set(expected))
        raise LandingError(f"base commit path set differs from BASE_APPLY_PATHS; missing={missing}, extra={extra}")
    for relpath, expected_record in _record_map(receipt["post_apply_path_records"]).items():
        actual = _git_record_at_commit(root, head, relpath)
        if not _record_content_equal(actual, expected_record):
            raise LandingError(f"base commit bytes differ from applied patch receipt: {relpath}")
    _verify_drift_bytes(root, context)
    confirmation = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "kind": "base_commit",
        "landing_id": context.plan["landing_id"],
        "created_at": _utc_now(),
        "initial_head": initial_head,
        "base_commit": head,
        "base_tree": _git(root, "rev-parse", f"{head}^{{tree}}").decode().strip(),
        "committed_paths": list(expected),
    }
    path = _receipt_path(context, "BASE_COMMIT_RECEIPT.json")
    _write_sealed_json(path, confirmation)
    return path


def _verify_confirmed_base(root: Path, context: PlanContext) -> Mapping[str, Any]:
    confirmation = _load_receipt(context, "BASE_COMMIT_RECEIPT.json", "base_commit")
    commit = str(confirmation["base_commit"])
    ancestor = _run(("git", "merge-base", "--is-ancestor", commit, "HEAD"), cwd=root, check=False)
    if ancestor.returncode != 0:
        raise LandingError("confirmed base commit is no longer an ancestor of HEAD")
    tree = _git(root, "rev-parse", f"{commit}^{{tree}}").decode().strip()
    if tree != confirmation["base_tree"]:
        raise LandingError("confirmed base commit tree changed")
    return confirmation


def _verify_installed_protocol(root: Path, context: PlanContext) -> None:
    installed = _load_protocol(root)
    records = (
        (DEFAULT_PROTOCOL, installed.protocol_path, context.bundle.protocol_path, "protocol"),
        (DEFAULT_PROTOCOL_SCHEMA, installed.protocol_schema_path, context.bundle.protocol_schema_path, "protocol schema"),
        (DEFAULT_ACK_SCHEMA, installed.ack_schema_path, context.bundle.ack_schema_path, "ACK schema"),
    )
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    tracked = _tracked_paths(root)
    for relpath, installed_path, planned_path, label in records:
        if relpath not in tracked:
            raise LandingError(f"installed landing {label} is not Git-tracked: {relpath}")
        expected_sha = _sha256_file(planned_path)
        if _sha256_file(installed_path) != expected_sha:
            raise LandingError(f"installed landing {label} differs from the bundle used to create the plan")
        committed = _git_record_at_commit(root, head, relpath)
        if committed.get("presence") != "file" or committed.get("sha256") != expected_sha:
            raise LandingError(f"installed landing {label} is not committed at HEAD: {relpath}")


def _archive_path(
    protocol: Mapping[str, Any],
    landing_date: str,
    landing_id: str,
    source_path: str,
) -> str:
    try:
        date.fromisoformat(landing_date)
    except ValueError as exc:
        raise LandingError(f"invalid landing date: {landing_date!r}") from exc
    safe_landing_id = _plan_id(landing_id)
    return PurePosixPath(
        str(protocol["archive_root"]), landing_date, safe_landing_id, source_path
    ).as_posix()


def _migration_target_paths(protocol: Mapping[str, Any]) -> tuple[str, ...]:
    paths: list[str] = []
    for migration in protocol["known_migrations"]:
        for obligation in migration["obligations"]:
            for value in obligation["allowed_targets"]:
                relpath = _relpath(str(value))
                if relpath not in paths:
                    paths.append(relpath)
    return tuple(paths)


def _ack_template(plan: Mapping[str, Any], protocol: Mapping[str, Any], landing_date: str) -> Mapping[str, Any]:
    migrations = _migration_index(protocol)
    drift = _drift_record_map(plan)
    records: list[dict[str, Any]] = []
    for source_path in plan["drift_paths"]:
        migration = migrations[source_path]
        source = drift[source_path]
        obligations = []
        for obligation in migration["obligations"]:
            obligations.append(
                {
                    "id": obligation["id"],
                    "target_path": obligation["allowed_targets"][0],
                    "record_ids": [],
                    "required_strings": [],
                }
            )
        records.append(
            {
                "source_path": source_path,
                "source_sha256": source["sha256"],
                "archive_path": _archive_path(
                    protocol,
                    landing_date,
                    str(plan["landing_id"]),
                    source_path,
                ),
                "obligations": obligations,
            }
        )
    return {
        "schema_version": "zmd_document_landing_ack_v1",
        "landing_id": plan["landing_id"],
        "records": records,
    }


def _target_baselines(root: Path, context: PlanContext) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    for relpath in _migration_target_paths(context.protocol):
        record = dict(_file_record(root, relpath))
        if record["presence"] != "file":
            raise LandingError(f"migration target is missing before begin-migration: {relpath}")
        source = root / relpath
        snapshot = context.plan_dir / "migration_baseline" / PurePosixPath(relpath)
        _atomic_write(snapshot, source.read_bytes())
        record["snapshot_path"] = snapshot.relative_to(context.plan_dir).as_posix()
        records.append(record)
    return records


def _archive_records(root: Path, context: PlanContext, landing_date: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for relpath, record in _drift_record_map(context.plan).items():
        archive_relpath = _archive_path(
            context.protocol,
            landing_date,
            str(context.plan["landing_id"]),
            relpath,
        )
        source = root / relpath
        if source.is_symlink() or not source.is_file():
            raise LandingError(f"drift source is not a local regular file: {relpath}")
        content = source.read_bytes()
        if _sha256_bytes(content) != record["sha256"]:
            raise LandingError(f"drift source changed before archive creation: {relpath}")
        archive = root / archive_relpath
        if archive.exists() or archive.is_symlink():
            if archive.is_symlink() or not archive.is_file() or archive.read_bytes() != content:
                raise LandingError(f"landing archive already exists with different bytes: {archive_relpath}")
        records.append(
            {
                "source_path": relpath,
                "source_sha256": record["sha256"],
                "source_size": record["size"],
                "archive_path": archive_relpath,
                "archive_sha256": record["sha256"],
            }
        )
    return records


def begin_migration(*, root: Path, plan_path: Path, landing_date: str) -> tuple[Path, Path]:
    root = _ensure_repository(root)
    context = _load_plan(plan_path, expected_root=root)
    _ensure_safe_branch(root, context.protocol)
    confirmation = _verify_confirmed_base(root, context)
    _verify_installed_protocol(root, context)
    plan = context.plan
    _ensure_no_unexpected_tracked_changes(root, plan["drift_paths"])
    if plan["status"] != "READY":
        raise LandingError("cannot begin migration from a blocked plan")
    _verify_drift_bytes(root, context)

    state_path = context.plan_dir / "MIGRATION_STATE.json"
    ack_path = context.plan_dir / "MIGRATION_ACK.json"
    if state_path.exists() or _seal_path(state_path).exists() or ack_path.exists():
        raise LandingError("migration state already exists; do not overwrite a started landing")

    archive_records = _archive_records(root, context, landing_date)
    archive_root = PurePosixPath(str(context.protocol["archive_root"]), landing_date, str(plan["landing_id"])).as_posix()
    archive_manifest_path = root / archive_root / "LANDING_ARCHIVE_MANIFEST.json"
    archive_manifest = {
        "schema_version": ARCHIVE_MANIFEST_SCHEMA_VERSION,
        "landing_id": plan["landing_id"],
        "created_at": _utc_now(),
        "records": archive_records,
    }
    if archive_manifest_path.exists():
        existing = _strict_json(archive_manifest_path)
        if not isinstance(existing, dict) or existing.get("landing_id") != plan["landing_id"]:
            raise LandingError(f"landing-date archive manifest belongs to another landing: {archive_manifest_path}")
        existing_records = existing.get("records")
        if existing_records != archive_records:
            raise LandingError(f"landing-date archive manifest has different source records: {archive_manifest_path}")
        archive_manifest = existing

    target_baselines = _target_baselines(root, context)

    # All validations above run before the first repository write. Existing exact
    # archive bytes are tolerated so an interrupted copy can be inspected and resumed.
    for record in archive_records:
        archive = root / str(record["archive_path"])
        if not archive.exists():
            _atomic_write(archive, (root / str(record["source_path"])).read_bytes())
    if not archive_manifest_path.exists():
        _write_json(archive_manifest_path, archive_manifest)

    state = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "kind": "migration_begin",
        "landing_id": plan["landing_id"],
        "landing_date": landing_date,
        "created_at": _utc_now(),
        "confirmed_base_commit": confirmation["base_commit"],
        "archive_manifest": archive_manifest_path.relative_to(root).as_posix(),
        "archive_manifest_sha256": _sha256_file(archive_manifest_path),
        "target_baselines": target_baselines,
        "append_only_targets": [str(value) for value in context.protocol["append_only_targets"]],
    }
    _write_sealed_json(state_path, state)
    _write_json(ack_path, _ack_template(plan, context.protocol, landing_date))
    return state_path, ack_path


def _load_migration_state(context: PlanContext) -> Mapping[str, Any]:
    path = context.plan_dir / "MIGRATION_STATE.json"
    value = _load_sealed_json(path)
    if not isinstance(value, dict) or value.get("kind") != "migration_begin":
        raise LandingError("MIGRATION_STATE.json is missing or invalid; run begin-migration first")
    if value.get("landing_id") != context.plan["landing_id"]:
        raise LandingError("migration state belongs to a different landing")
    return value


def _baseline_content(context: PlanContext, record: Mapping[str, Any]) -> bytes:
    snapshot = _plan_file(context, record.get("snapshot_path"), label="migration target baseline")
    content = snapshot.read_bytes()
    if _sha256_bytes(content) != record.get("sha256") or len(content) != record.get("size"):
        raise LandingError(f"migration target baseline changed: {record.get('path')}")
    return content


def _target_baseline_map(context: PlanContext, state: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    records = state.get("target_baselines")
    if not isinstance(records, list):
        raise LandingError("migration state has no target baseline records")
    result = _record_map(records)
    expected = set(_migration_target_paths(context.protocol))
    if set(result) != expected:
        raise LandingError("migration target baseline set differs from the landing protocol")
    return result


def _verify_append_only(root: Path, context: PlanContext, state: Mapping[str, Any]) -> None:
    baselines = _target_baseline_map(context, state)
    for value in state["append_only_targets"]:
        relpath = _relpath(str(value))
        record = baselines.get(relpath)
        if record is None:
            raise LandingError(f"append-only target has no baseline: {relpath}")
        before = _baseline_content(context, record)
        current = root / relpath
        if current.is_symlink() or not current.is_file():
            raise LandingError(f"append-only target disappeared: {relpath}")
        after = current.read_bytes()
        if not after.startswith(before):
            raise LandingError(f"append-only target rewrote existing bytes: {relpath}")


def _read_target_text(root: Path, relpath: str) -> str:
    path = root / relpath
    if path.is_symlink() or not path.is_file():
        raise LandingError(f"migration target is missing or not a local regular file: {relpath}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise LandingError(f"migration target is not UTF-8 text: {relpath}") from exc


def _json_object_pairs(label: str):
    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise LandingError(f"duplicate JSON key in {label}: {key!r}")
            result[key] = value
        return result

    return reject_duplicate


def _read_jsonl_records(root: Path, relpath: str) -> list[Mapping[str, Any]]:
    text = _read_target_text(root, relpath)
    records: list[Mapping[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(
                line,
                object_pairs_hook=_json_object_pairs(f"{relpath}:{number}"),
                parse_constant=lambda constant: (_ for _ in ()).throw(
                    LandingError(f"non-finite JSON constant in {relpath}:{number}: {constant}")
                ),
            )
        except json.JSONDecodeError as exc:
            raise LandingError(f"invalid JSONL record in {relpath}:{number}: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise LandingError(f"JSONL record is not an object in {relpath}:{number}")
        records.append(value)
    return records


def _read_json_document(root: Path, relpath: str) -> Any:
    return _strict_json(root / relpath)


def _obligation_format(obligation: Mapping[str, Any], target: str) -> str:
    formats = obligation.get("target_formats")
    if not isinstance(formats, dict) or target not in formats:
        raise LandingError(f"migration obligation omits target format for {target}")
    value = str(formats[target])
    if value not in {"text", "json", "jsonl"}:
        raise LandingError(f"unsupported migration target format {value!r} for {target}")
    return value


def _source_text_for_ack(root: Path, archive_relpath: str) -> str:
    try:
        return _read_target_text(root, archive_relpath)
    except LandingError as exc:
        raise LandingError(f"source-derived ACK strings require UTF-8 archive text: {archive_relpath}") from exc


def _verify_obligation(
    *,
    root: Path,
    obligation: Mapping[str, Any],
    acknowledgement: Mapping[str, Any],
    archive_relpath: str,
    source_sha256: str,
) -> None:
    obligation_id = str(obligation["id"])
    target = _relpath(str(acknowledgement["target_path"]))
    if target not in obligation["allowed_targets"]:
        raise LandingError(f"obligation {obligation_id} uses disallowed target {target}")
    required_strings = [str(value) for value in acknowledgement["required_strings"]]
    if obligation["require_ack_strings"] and not required_strings:
        raise LandingError(f"obligation {obligation_id} requires source-derived ACK strings")
    source_text = _source_text_for_ack(root, archive_relpath)
    for value in required_strings:
        if value not in source_text:
            raise LandingError(
                f"obligation {obligation_id} ACK string is not present in the archived source: {value!r}"
            )

    markers = list(dict.fromkeys([*(str(value) for value in obligation["required_markers"]), *required_strings]))
    archive_coordinates = [archive_relpath, source_sha256] if obligation["require_archive_reference"] else []
    record_ids = [str(value) for value in acknowledgement["record_ids"]]
    if obligation["require_record_id"] and not record_ids:
        raise LandingError(f"obligation {obligation_id} requires at least one record ID")

    target_format = _obligation_format(obligation, target)
    if target_format == "jsonl" and obligation["require_record_id"]:
        records = _read_jsonl_records(root, target)
        indexed: dict[str, list[Mapping[str, Any]]] = {}
        for record in records:
            record_id = record.get("id")
            if isinstance(record_id, str):
                indexed.setdefault(record_id, []).append(record)
        for record_id in record_ids:
            matches = indexed.get(record_id, [])
            if len(matches) != 1:
                raise LandingError(
                    f"obligation {obligation_id} requires exactly one JSONL record with id {record_id!r}"
                )
            encoded = json.dumps(matches[0], ensure_ascii=False, sort_keys=True)
            for marker in (*markers, *archive_coordinates):
                if marker not in encoded:
                    raise LandingError(
                        f"obligation {obligation_id} JSONL record {record_id!r} lacks marker {marker!r}"
                    )
        return

    if target_format == "jsonl":
        target_text = "\n".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True)
            for record in _read_jsonl_records(root, target)
        )
    elif target_format == "json":
        target_text = json.dumps(_read_json_document(root, target), ensure_ascii=False, sort_keys=True)
    else:
        target_text = _read_target_text(root, target)
    for marker in (*markers, *archive_coordinates, *record_ids):
        if marker not in target_text:
            raise LandingError(f"obligation {obligation_id} target {target} lacks marker {marker!r}")


def _verify_archive_manifest(root: Path, context: PlanContext, state: Mapping[str, Any]) -> None:
    relpath = _relpath(str(state["archive_manifest"]))
    path = root / relpath
    if path.is_symlink() or not path.is_file():
        raise LandingError(f"landing archive manifest is missing: {relpath}")
    if _sha256_file(path) != state["archive_manifest_sha256"]:
        raise LandingError(f"landing archive manifest changed after begin-migration: {relpath}")
    value = _strict_json(path)
    if not isinstance(value, dict) or value.get("landing_id") != context.plan["landing_id"]:
        raise LandingError(f"landing archive manifest belongs to another landing: {relpath}")


def _verify_migration_core(
    *,
    root: Path,
    context: PlanContext,
    state: Mapping[str, Any],
    ack: Mapping[str, Any],
    allow_package_successors: bool,
    require_finalized: bool,
) -> Mapping[str, Any]:
    _verify_append_only(root, context, state)
    _verify_archive_manifest(root, context, state)
    migrations = _migration_index(context.protocol)
    drift = _drift_record_map(context.plan)
    ack_records = {str(record["source_path"]): record for record in ack["records"]}
    if len(ack_records) != len(ack["records"]):
        raise LandingError("migration ACK contains duplicate source_path records")
    expected_sources = set(context.plan["drift_paths"])
    if set(ack_records) != expected_sources:
        missing = sorted(expected_sources - set(ack_records))
        extra = sorted(set(ack_records) - expected_sources)
        raise LandingError(f"migration ACK source mismatch; missing={missing}, extra={extra}")

    verified: list[dict[str, Any]] = []
    for source_path in sorted(expected_sources):
        migration = migrations[source_path]
        source_record = drift[source_path]
        ack_record = ack_records[source_path]
        if ack_record["source_sha256"] != source_record["sha256"]:
            raise LandingError(f"migration ACK source digest mismatch: {source_path}")
        archive_relpath = _relpath(str(ack_record["archive_path"]))
        expected_archive = _archive_path(context.protocol, str(state["landing_date"]), str(context.plan["landing_id"]), source_path)
        if archive_relpath != expected_archive:
            raise LandingError(f"migration ACK archive path mismatch for {source_path}")
        archive = root / archive_relpath
        if archive.is_symlink() or not archive.is_file() or _sha256_file(archive) != source_record["sha256"]:
            raise LandingError(f"landing archive is not byte-faithful: {archive_relpath}")

        obligations = {str(value["id"]): value for value in migration["obligations"]}
        acknowledged = {str(value["id"]): value for value in ack_record["obligations"]}
        if len(acknowledged) != len(ack_record["obligations"]):
            raise LandingError(f"duplicate obligation IDs in ACK for {source_path}")
        if set(acknowledged) != set(obligations):
            raise LandingError(f"ACK obligations do not match protocol for {source_path}")
        for obligation_id, obligation in obligations.items():
            _verify_obligation(
                root=root,
                obligation=obligation,
                acknowledgement=acknowledged[obligation_id],
                archive_relpath=archive_relpath,
                source_sha256=str(source_record["sha256"]),
            )

        source = root / source_path
        if source.is_symlink() or not source.is_file():
            raise LandingError(f"migration source is missing or not a local regular file: {source_path}")
        current = source.read_bytes()
        original = _plan_file(context, source_record["snapshot_path"], label="drift snapshot").read_bytes()
        if migration["replacement_mode"] == "manual_overlay":
            changed = current != original
            if migration["require_source_change"] and not changed:
                raise LandingError(f"workspace overlay has not been reconciled: {source_path}")
            text = _read_target_text(root, source_path)
            for marker in migration["source_markers_after_migration"]:
                if marker not in text:
                    raise LandingError(f"reconciled overlay {source_path} lacks marker {marker!r}")
            state_name = "manual_overlay"
        else:
            successor = _successor_content(context, source_path)
            if current == original:
                state_name = "original"
            elif current == successor:
                state_name = "successor"
            else:
                raise LandingError(f"package-owned migration source has unplanned bytes: {source_path}")
            if require_finalized and state_name != "successor":
                raise LandingError(f"package successor has not replaced drifted source: {source_path}")
            if not allow_package_successors and state_name != "original":
                raise LandingError(f"package-owned successor was replaced before finalize-migration: {source_path}")
        verified.append(
            {
                "source_path": source_path,
                "archive_path": archive_relpath,
                "source_state": state_name,
            }
        )

    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "kind": "migration_verify_final" if require_finalized else "migration_verify_pre_finalize",
        "landing_id": context.plan["landing_id"],
        "created_at": _utc_now(),
        "verified_records": verified,
    }


def verify_migration(*, root: Path, plan_path: Path, ack_path: Path, finalized: bool = False) -> Mapping[str, Any]:
    root = _ensure_repository(root)
    context = _load_plan(plan_path, expected_root=root)
    _ensure_safe_branch(root, context.protocol)
    _verify_confirmed_base(root, context)
    _verify_installed_protocol(root, context)
    state = _load_migration_state(context)
    ack = _strict_json(ack_path.resolve())
    _validate(context.ack_schema, ack, str(ack_path))
    if ack["landing_id"] != context.plan["landing_id"]:
        raise LandingError("migration ACK belongs to a different landing")
    return _verify_migration_core(
        root=root,
        context=context,
        state=state,
        ack=ack,
        allow_package_successors=finalized,
        require_finalized=finalized,
    )


def _migration_changed_paths(root: Path, context: PlanContext, state: Mapping[str, Any]) -> tuple[str, ...]:
    paths: list[str] = []
    for record in state["target_baselines"]:
        relpath = _relpath(str(record["path"]))
        current = _file_record(root, relpath)
        if not _record_content_equal(current, record) and relpath not in context.protocol["workspace_overlays"]:
            paths.append(relpath)
    for record in _drift_record_map(context.plan).values():
        archive = _archive_path(
            context.protocol,
            str(state["landing_date"]),
            str(context.plan["landing_id"]),
            str(record["source_path"]),
        )
        if archive not in paths:
            paths.append(archive)
    manifest = _relpath(str(state["archive_manifest"]))
    if manifest not in paths:
        paths.append(manifest)
    migrations = _migration_index(context.protocol)
    for source_path in context.plan["drift_paths"]:
        if migrations[source_path]["replacement_mode"] == "package_successor" and source_path not in paths:
            paths.append(source_path)
    return tuple(paths)


def finalize_migration(*, root: Path, plan_path: Path, ack_path: Path) -> Path:
    root = _ensure_repository(root)
    context = _load_plan(plan_path, expected_root=root)
    _ensure_safe_branch(root, context.protocol)
    _verify_confirmed_base(root, context)
    _verify_installed_protocol(root, context)
    state = _load_migration_state(context)
    ack = _strict_json(ack_path.resolve())
    _validate(context.ack_schema, ack, str(ack_path))
    if ack["landing_id"] != context.plan["landing_id"]:
        raise LandingError("migration ACK belongs to a different landing")

    # This mode accepts exact planned successors left by an interrupted prior
    # finalize, but rejects every other byte pattern before writing anything.
    _verify_migration_core(
        root=root,
        context=context,
        state=state,
        ack=ack,
        allow_package_successors=True,
        require_finalized=False,
    )
    migrations = _migration_index(context.protocol)
    drift_records = _drift_record_map(context.plan)
    candidates: list[tuple[str, bytes]] = []
    for source_path in context.plan["drift_paths"]:
        migration = migrations[source_path]
        if migration["replacement_mode"] != "package_successor":
            continue
        content = _successor_content(context, source_path)
        current = (root / source_path).read_bytes()
        original = _plan_file(
            context,
            drift_records[source_path]["snapshot_path"],
            label="drift snapshot",
        ).read_bytes()
        if current == content:
            continue
        if current != original:
            raise LandingError(f"cannot finalize unplanned package source bytes: {source_path}")
        candidates.append((source_path, content))

    for source_path, content in candidates:
        _atomic_write(root / source_path, content)

    receipt = _verify_migration_core(
        root=root,
        context=context,
        state=state,
        ack=ack,
        allow_package_successors=True,
        require_finalized=True,
    )
    changed_paths = _migration_changed_paths(root, context, state)
    receipt = {
        **receipt,
        "successor_source": "sealed_plan_package_successors",
        "replaced_paths": [path for path, _content in candidates],
        "migration_changed_paths": list(changed_paths),
    }
    receipt_path = context.plan_dir / "FINALIZE_RECEIPT.json"
    _write_sealed_json(receipt_path, receipt)
    _atomic_write(
        context.plan_dir / "MIGRATION_CHANGED_PATHS.nul",
        b"".join(path.encode("utf-8") + b"\0" for path in changed_paths),
    )
    _atomic_write(
        context.plan_dir / "MIGRATION_CHANGED_PATHS.txt",
        ("\n".join(changed_paths) + "\n").encode("utf-8"),
    )
    overlays = tuple(
        path
        for path in context.protocol["workspace_overlays"]
        if _file_record(root, _relpath(str(path)))["presence"] == "file"
    )
    _atomic_write(
        context.plan_dir / "WORKSPACE_OVERLAY_PATHS.txt",
        ("\n".join(str(path) for path in overlays) + ("\n" if overlays else "")).encode("utf-8"),
    )
    return receipt_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="discover dynamic drift and seal an external landing plan")
    plan.add_argument("--repo-root", type=Path, default=ROOT)
    plan.add_argument("--patch", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--protocol", type=Path)
    plan.add_argument("--protocol-schema", type=Path)
    plan.add_argument("--ack-schema", type=Path)
    plan.add_argument("--baseline-root", type=Path, required=True)
    plan.add_argument("--landing-id")

    apply_command = subparsers.add_parser("apply-base", help="apply only dynamically verified non-drift paths")
    apply_command.add_argument("--repo-root", type=Path, default=ROOT)
    apply_command.add_argument("--plan", type=Path, required=True)

    confirm = subparsers.add_parser("confirm-base", help="verify the base layer was committed exactly once")
    confirm.add_argument("--repo-root", type=Path, default=ROOT)
    confirm.add_argument("--plan", type=Path, required=True)

    begin = subparsers.add_parser("begin-migration", help="archive landing-time bytes and open migration ACK")
    begin.add_argument("--repo-root", type=Path, default=ROOT)
    begin.add_argument("--plan", type=Path, required=True)
    begin.add_argument("--landing-date", required=True)

    verify = subparsers.add_parser("verify-migration", help="verify archives and semantic migration obligations")
    verify.add_argument("--repo-root", type=Path, default=ROOT)
    verify.add_argument("--plan", type=Path, required=True)
    verify.add_argument("--ack", type=Path, required=True)
    verify.add_argument("--finalized", action="store_true")

    finalize = subparsers.add_parser("finalize-migration", help="verify then install sealed package successors")
    finalize.add_argument("--repo-root", type=Path, default=ROOT)
    finalize.add_argument("--plan", type=Path, required=True)
    finalize.add_argument("--ack", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "plan":
            path = create_plan(
                root=args.repo_root,
                patch=args.patch,
                output=args.output,
                protocol_arg=args.protocol,
                protocol_schema_arg=args.protocol_schema,
                ack_schema_arg=args.ack_schema,
                baseline_root=args.baseline_root,
                landing_id=args.landing_id,
            )
            plan = _load_sealed_json(path)
            print(f"{plan['status']}: {path}")
            if plan["drift_paths"]:
                print("dynamic drift: " + ", ".join(plan["drift_paths"]))
            if plan["unknown_drift_paths"] or plan["unsupported_drift_paths"]:
                print("blocked drift: " + ", ".join(dict.fromkeys([
                    *plan["unknown_drift_paths"],
                    *plan["unsupported_drift_paths"],
                ])))
                return 2
            return 0
        if args.command == "apply-base":
            print(apply_base(root=args.repo_root, plan_path=args.plan))
            return 0
        if args.command == "confirm-base":
            print(confirm_base(root=args.repo_root, plan_path=args.plan))
            return 0
        if args.command == "begin-migration":
            state, ack = begin_migration(root=args.repo_root, plan_path=args.plan, landing_date=args.landing_date)
            print(state)
            print(ack)
            return 0
        if args.command == "verify-migration":
            receipt = verify_migration(
                root=args.repo_root,
                plan_path=args.plan,
                ack_path=args.ack,
                finalized=args.finalized,
            )
            print(json.dumps(receipt, ensure_ascii=False, indent=2))
            return 0
        if args.command == "finalize-migration":
            print(finalize_migration(root=args.repo_root, plan_path=args.plan, ack_path=args.ack))
            return 0
        raise LandingError(f"unknown command: {args.command}")
    except LandingError as exc:
        print(f"BLOCK: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
