#!/usr/bin/env python3
"""Restore external large artifacts from a local source file or directory."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from external_artifacts import find_artifact, verify_artifact


def resolve_source(source: Path, artifact_rel_path: str) -> Path:
    source = source.expanduser().resolve()
    if source.is_file():
        return source
    if source.is_dir():
        candidates = [source / artifact_rel_path, source / Path(artifact_rel_path).name]
        for candidate in candidates:
            if candidate.exists():
                return candidate
    raise FileNotFoundError(f"could not find {artifact_rel_path} under {source}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore one external artifact and verify bytes.")
    parser.add_argument("artifact_id", help="Artifact id from data/external_artifacts.json")
    parser.add_argument("--source", type=Path, required=True, help="Source file or directory containing the artifact.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing destination file.")
    args = parser.parse_args()

    artifact = find_artifact(args.artifact_id)
    source = resolve_source(args.source, artifact.rel_path)
    artifact.path.parent.mkdir(parents=True, exist_ok=True)
    if artifact.path.exists() and not args.force:
        print(f"destination already exists: {artifact.rel_path}; use --force to overwrite", file=sys.stderr)
        return 1
    shutil.copy2(source, artifact.path)
    ok, message = verify_artifact(artifact)
    if not ok:
        print(f"restore failed verification: {message}", file=sys.stderr)
        return 1
    print(f"restored {artifact.artifact_id}: {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
