#!/usr/bin/env python3
"""Restore recoverable external artifacts from a local directory or archive.

This script never downloads artifacts. It only copies bytes from an explicit
local source, then verifies the declared size and sha256 from
`data/external_artifacts.json`.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from external_artifacts import ExternalArtifact, load_external_artifacts, validate_artifact  # noqa: E402


def candidate_relative_paths(artifact: ExternalArtifact) -> list[Path]:
    rel = Path(artifact.rel_path)
    return [rel, Path("zmd") / rel, Path("project") / rel]


def copy_from_directory(source: Path, artifact: ExternalArtifact) -> bool:
    for rel in candidate_relative_paths(artifact):
        candidate = source / rel
        if candidate.exists() and candidate.is_file():
            artifact.path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(candidate, artifact.path)
            return True
    return False


def find_7z() -> str | None:
    for name in ("7z", "7zz", "7za"):
        found = shutil.which(name)
        if found:
            return found
    return None


def extract_archive(archive: Path, output_dir: Path) -> None:
    suffixes = archive.suffixes
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(output_dir)
        return
    if any(suffix in suffixes for suffix in (".tar", ".gz", ".xz", ".bz2", ".tgz", ".txz")):
        with tarfile.open(archive) as tf:
            tf.extractall(output_dir)
        return
    if archive.suffix == ".7z":
        seven_zip = find_7z()
        if seven_zip:
            subprocess.run([seven_zip, "x", str(archive), f"-o{output_dir}"], check=True)
            return
        try:
            import py7zr  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - depends on local tooling.
            raise RuntimeError("restoring from .7z requires 7z/7zz/7za on PATH or py7zr installed") from exc
        with py7zr.SevenZipFile(archive, "r") as zf:  # type: ignore[name-defined]
            zf.extractall(output_dir)
        return
    raise RuntimeError(f"unsupported archive format: {archive}")


def restore_one(artifact: ExternalArtifact, *, source: Path | None, source_archive: Path | None) -> None:
    restored = False
    if source is not None:
        restored = copy_from_directory(source, artifact)
    if not restored and source_archive is not None:
        with tempfile.TemporaryDirectory(prefix="zmd_external_artifact_") as tmp:
            extract_archive(source_archive, Path(tmp))
            restored = copy_from_directory(Path(tmp), artifact)
    if not restored:
        hints = "\n  ".join(artifact.restore_hints)
        raise RuntimeError(f"could not find {artifact.rel_path} in supplied source(s). Hints:\n  {hints}")
    ok, message = validate_artifact(artifact)
    if not ok:
        raise RuntimeError(message)
    print(f"restored {artifact.name}: {message}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", action="append", default=[], help="Artifact name to restore. Default: all declared artifacts.")
    parser.add_argument("--source", type=Path, default=None, help="Directory containing artifact paths, optionally under zmd/.")
    parser.add_argument("--source-archive", type=Path, default=None, help="Archive containing artifact paths, optionally under zmd/.")
    args = parser.parse_args()

    if args.source is None and args.source_archive is None:
        parser.error("provide --source and/or --source-archive")

    artifacts = load_external_artifacts()
    names = args.artifact or sorted(artifacts)
    unknown = sorted(set(names) - set(artifacts))
    if unknown:
        print(f"unknown external artifact(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    for name in names:
        try:
            restore_one(artifacts[name], source=args.source, source_archive=args.source_archive)
        except Exception as exc:
            print(f"restore failed for {name}: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
