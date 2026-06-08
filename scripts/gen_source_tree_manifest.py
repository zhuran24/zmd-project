#!/usr/bin/env python3
"""Generate a deterministic source-tree manifest identity for review packages.

The Phase 1.2 clean-review gate intentionally does not use package-internal Git
state as machine authority.  Review packages should instead bind the source tree
through a canonical manifest of file bytes.  This helper emits that manifest and
prints its SHA256 identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXCLUDED_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".hypothesis",
}
DEFAULT_EXCLUDED_PREFIXES = (
    ".artifacts/",
    "data/checkpoints/",
    "data/exports/",
    "data/hints/",
    "data/solutions/",
)


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_normalized_rel_path(value: str) -> bool:
    path = PurePosixPath(value)
    return not path.is_absolute() and "\\" not in value and all(part not in {"", ".", ".."} for part in path.parts)


def _excluded(rel_path: str, extra_excludes: set[str]) -> bool:
    parts = set(PurePosixPath(rel_path).parts)
    if parts.intersection(DEFAULT_EXCLUDED_PARTS):
        return True
    if any(rel_path.startswith(prefix) for prefix in DEFAULT_EXCLUDED_PREFIXES):
        return True
    if rel_path in extra_excludes:
        return True
    return False


def iter_source_files(root: Path, *, extra_excludes: set[str]) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = _rel(path, root)
        if not _is_normalized_rel_path(rel_path):
            continue
        if _excluded(rel_path, extra_excludes):
            continue
        yield path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path, *, extra_excludes: set[str]) -> dict[str, object]:
    files = []
    for path in iter_source_files(root, extra_excludes=extra_excludes):
        stat = path.stat()
        files.append({"path": _rel(path, root), "size_bytes": stat.st_size, "sha256": file_sha256(path)})
    return {
        "schema_version": 1,
        "manifest_type": "zmd_source_tree_manifest",
        "root": ".",
        "excluded_prefixes": list(DEFAULT_EXCLUDED_PREFIXES),
        "file_count": len(files),
        "files": files,
    }


def canonical_manifest_bytes(manifest: dict[str, object]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate source-tree manifest identity")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Project root to scan")
    parser.add_argument("--output", type=Path, help="Write canonical manifest JSON to this path")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional exact project-relative path to exclude from the manifest",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    extra_excludes = set(args.exclude)
    manifest = build_manifest(root, extra_excludes=extra_excludes)
    payload = canonical_manifest_bytes(manifest)
    identity = hashlib.sha256(payload).hexdigest()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
    print(identity)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
