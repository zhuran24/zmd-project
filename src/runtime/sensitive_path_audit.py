from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

DEFAULT_SENSITIVE_RELATIVE_PATHS: tuple[str, ...] = (
    "data/checkpoints",
    "data/checkpoints/exact_campaign_state.json",
    "data/checkpoints/exact_campaign_telemetry.json",
    "data/solutions/final_solution.json",
    "data/blueprints/optimal_blueprint.json",
    "data/solutions/certified_delivery_manifest.json",
    ".artifacts/phase3b_long_run_preflight/preflight_summary.json",
    "viewer",
    "release",
    "frontdoor",
)

FINAL_DELIVERY_RELATIVE_PATHS: frozenset[str] = frozenset(
    {
        "data/solutions/final_solution.json",
        "data/blueprints/optimal_blueprint.json",
        "data/solutions/certified_delivery_manifest.json",
    }
)


def build_sensitive_path_fingerprint(
    project_root: Path,
    *,
    relative_paths: Sequence[str] = DEFAULT_SENSITIVE_RELATIVE_PATHS,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    entries = [
        fingerprint_path(project_root / relative_path, relative_path=relative_path)
        for relative_path in relative_paths
    ]
    return {
        "schema": "phase3b-sensitive-path-fingerprint/v0",
        "project_root": str(project_root),
        "entries": entries,
        "canonical_checkpoint_exists": any(
            bool(entry.get("exists"))
            and str(entry.get("relative_path", "")).startswith("data/checkpoints")
            for entry in entries
        ),
        "final_delivery_artifact_exists": any(
            bool(entry.get("exists"))
            and str(entry.get("relative_path", "")) in FINAL_DELIVERY_RELATIVE_PATHS
            for entry in entries
        ),
    }


def compare_sensitive_path_fingerprints(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    before_by_path = _entries_by_relative_path(before)
    after_by_path = _entries_by_relative_path(after)
    relative_paths = sorted(set(before_by_path) | set(after_by_path))
    changed_entries: list[dict[str, Any]] = []
    for relative_path in relative_paths:
        before_entry = before_by_path.get(relative_path)
        after_entry = after_by_path.get(relative_path)
        if _stable_entry(before_entry) != _stable_entry(after_entry):
            changed_entries.append(
                {
                    "relative_path": relative_path,
                    "before": before_entry,
                    "after": after_entry,
                }
            )
    return {
        "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
        "changed": bool(changed_entries),
        "changed_paths": [entry["relative_path"] for entry in changed_entries],
        "changed_entries": changed_entries,
    }


def fingerprint_path(path: Path, *, relative_path: str) -> dict[str, Any]:
    path = Path(path)
    normalized_relative = str(relative_path).replace("\\", "/")
    if not path.exists():
        return {
            "relative_path": normalized_relative,
            "path": str(path),
            "exists": False,
            "kind": "missing",
            "size_bytes": None,
            "mtime_ns": None,
            "sha256": None,
            "file_count": 0,
        }
    if path.is_dir():
        return _fingerprint_directory(path, relative_path=normalized_relative)
    stat = path.stat()
    return {
        "relative_path": normalized_relative,
        "path": str(path),
        "exists": True,
        "kind": "file",
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sha256": _sha256_file(path),
        "file_count": 1,
    }


def _fingerprint_directory(path: Path, *, relative_path: str) -> dict[str, Any]:
    files = sorted(file for file in path.rglob("*") if file.is_file())
    digest = hashlib.sha256()
    total_size = 0
    max_mtime_ns = int(path.stat().st_mtime_ns)
    for file in files:
        stat = file.stat()
        total_size += int(stat.st_size)
        max_mtime_ns = max(max_mtime_ns, int(stat.st_mtime_ns))
        rel = file.relative_to(path).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256_file(file).encode("ascii"))
        digest.update(b"\0")
    return {
        "relative_path": relative_path,
        "path": str(path),
        "exists": True,
        "kind": "directory",
        "size_bytes": int(total_size),
        "mtime_ns": int(max_mtime_ns),
        "sha256": digest.hexdigest(),
        "file_count": len(files),
    }


def _entries_by_relative_path(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, Mapping):
            result[str(entry.get("relative_path", "")).replace("\\", "/")] = entry
    return result


def _stable_entry(entry: Mapping[str, Any] | None) -> tuple[Any, ...] | None:
    if entry is None:
        return None
    return (
        bool(entry.get("exists")),
        str(entry.get("kind")),
        entry.get("size_bytes"),
        entry.get("mtime_ns"),
        entry.get("sha256"),
        entry.get("file_count"),
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
