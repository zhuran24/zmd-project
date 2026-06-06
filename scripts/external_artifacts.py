#!/usr/bin/env python3
"""Shared helpers for recoverable external artifact checks."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "data" / "external_artifacts.json"


@dataclass(frozen=True)
class ExternalArtifact:
    name: str
    path: Path
    sha256: str
    size_bytes: int
    required_for: tuple[str, ...]
    policy_doc: str
    restore_hints: tuple[str, ...]

    @property
    def rel_path(self) -> str:
        return self.path.relative_to(REPO_ROOT).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_external_artifacts(path: Path = MANIFEST_PATH) -> dict[str, ExternalArtifact]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("data/external_artifacts.json schema_version must be 1")
    raw = payload.get("artifacts", {})
    if not isinstance(raw, dict):
        raise ValueError("data/external_artifacts.json artifacts must be an object")

    artifacts: dict[str, ExternalArtifact] = {}
    for name, info in sorted(raw.items()):
        if not isinstance(info, dict):
            raise ValueError(f"external artifact {name!r} must be an object")
        rel_path = str(info["path"])
        artifacts[str(name)] = ExternalArtifact(
            name=str(name),
            path=REPO_ROOT / rel_path,
            sha256=str(info["sha256"]).lower(),
            size_bytes=int(info["size_bytes"]),
            required_for=tuple(str(item) for item in info.get("required_for", [])),
            policy_doc=str(info.get("policy_doc", "START_HERE.md")),
            restore_hints=tuple(str(item) for item in info.get("restore_hints", [])),
        )
    return artifacts


def validate_artifact(artifact: ExternalArtifact) -> tuple[bool, str]:
    if not artifact.path.exists():
        return False, f"missing: {artifact.rel_path}"
    size = artifact.path.stat().st_size
    if size != artifact.size_bytes:
        return False, f"size mismatch for {artifact.rel_path}: expected {artifact.size_bytes}, got {size}"
    digest = sha256_file(artifact.path)
    if digest.lower() != artifact.sha256.lower():
        return False, f"sha256 mismatch for {artifact.rel_path}: expected {artifact.sha256}, got {digest}"
    return True, f"ok: {artifact.rel_path}"
