#!/usr/bin/env python3
"""Shared helpers for external large-artifact contracts."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "data" / "external_artifacts.json"


@dataclass(frozen=True)
class ExternalArtifact:
    artifact_id: str
    path: Path
    sha256: str
    size_bytes: int
    required_for: tuple[str, ...]
    optional_in_lightweight_checkout: bool
    restore_hints: tuple[str, ...]

    @property
    def rel_path(self) -> str:
        return self.path.relative_to(PROJECT_ROOT).as_posix()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def load_manifest(path: Path = MANIFEST_PATH) -> list[ExternalArtifact]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("data/external_artifacts.json schema_version must be 1")
    artifacts: list[ExternalArtifact] = []
    for raw in payload.get("artifacts", []):
        artifact_path = PROJECT_ROOT / str(raw["path"])
        artifacts.append(
            ExternalArtifact(
                artifact_id=str(raw["id"]),
                path=artifact_path,
                sha256=str(raw["sha256"]).lower(),
                size_bytes=int(raw["size_bytes"]),
                required_for=tuple(str(x) for x in raw.get("required_for", [])),
                optional_in_lightweight_checkout=bool(raw.get("optional_in_lightweight_checkout", False)),
                restore_hints=tuple(str(x) for x in raw.get("restore_hints", [])),
            )
        )
    return artifacts


def find_artifact(artifact_id: str) -> ExternalArtifact:
    for artifact in load_manifest():
        if artifact.artifact_id == artifact_id:
            return artifact
    raise KeyError(f"unknown external artifact: {artifact_id}")


def verify_artifact(artifact: ExternalArtifact) -> tuple[bool, str]:
    if not artifact.path.exists():
        if artifact.optional_in_lightweight_checkout:
            return True, f"{artifact.rel_path} missing by lightweight-checkout policy"
        return False, f"{artifact.rel_path} is required but missing"
    actual_size = artifact.path.stat().st_size
    if actual_size != artifact.size_bytes:
        return False, f"{artifact.rel_path} size {actual_size} != expected {artifact.size_bytes}"
    actual_hash = sha256_file(artifact.path)
    if actual_hash != artifact.sha256:
        return False, f"{artifact.rel_path} sha256 {actual_hash} != expected {artifact.sha256}"
    return True, f"{artifact.rel_path} verified"


def manifest_as_dict(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
