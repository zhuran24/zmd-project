"""Build-time snapshot ingest for endfield-calc-like data snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from src.adapters.endfield_calc.normalize_catalog import build_normalized_catalog_from_snapshot_payload
from src.adapters.endfield_calc.typescript_snapshot import can_load_typescript_source, load_typescript_source_dir

SNAPSHOT_METADATA_FILENAME = "SNAPSHOT_METADATA.json"
_REQUIRED_FILENAMES = ("items.json", "recipes.json", "facilities.json")
_REQUIRED_TYPESCRIPT_FILENAMES = ("items.ts", "recipes.ts", "facilities.ts", "constants.ts")
SnapshotSourceFormat = Literal["json", "typescript"]


def detect_snapshot_source_format(snapshot_dir: Path) -> SnapshotSourceFormat:
    snapshot_dir = Path(snapshot_dir)
    if snapshot_dir.is_dir() and all((snapshot_dir / filename).exists() for filename in _REQUIRED_FILENAMES):
        return "json"
    if can_load_typescript_source(snapshot_dir):
        return "typescript"
    raise FileNotFoundError(
        "snapshot path does not look like a JSON snapshot directory or endfield-calc TypeScript source input: "
        f"{snapshot_dir}"
    )


def load_snapshot_dir(snapshot_dir: Path) -> dict[str, Any]:
    snapshot_dir = Path(snapshot_dir)
    if not snapshot_dir.exists():
        raise FileNotFoundError(f"snapshot directory not found: {snapshot_dir}")

    payload: dict[str, Any] = {}
    for filename in _REQUIRED_FILENAMES:
        path = snapshot_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"missing snapshot file: {path}")
        payload[filename[:-5]] = json.loads(path.read_text(encoding="utf-8"))

    metadata_path = snapshot_dir / SNAPSHOT_METADATA_FILENAME
    if metadata_path.exists():
        payload["snapshot_metadata"] = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        payload["snapshot_metadata"] = {}
    return payload


def load_snapshot_source(
    snapshot_dir: Path,
    *,
    source_format: SnapshotSourceFormat | Literal["auto"] = "auto",
) -> dict[str, Any]:
    snapshot_dir = Path(snapshot_dir)
    resolved_format = detect_snapshot_source_format(snapshot_dir) if source_format == "auto" else source_format
    if resolved_format == "json":
        return load_snapshot_dir(snapshot_dir)
    if resolved_format == "typescript":
        return load_typescript_source_dir(snapshot_dir)
    raise ValueError(f"unsupported snapshot source_format: {resolved_format}")


def ingest_snapshot_dir(snapshot_dir: Path) -> dict[str, Any]:
    loaded = load_snapshot_dir(snapshot_dir)
    return build_normalized_catalog_from_snapshot_payload(
        items=loaded["items"],
        recipes=loaded["recipes"],
        facilities=loaded["facilities"],
        snapshot_metadata=loaded.get("snapshot_metadata"),
    )


def ingest_snapshot_source(
    snapshot_dir: Path,
    *,
    source_format: SnapshotSourceFormat | Literal["auto"] = "auto",
) -> dict[str, Any]:
    loaded = load_snapshot_source(snapshot_dir, source_format=source_format)
    return build_normalized_catalog_from_snapshot_payload(
        items=loaded["items"],
        recipes=loaded["recipes"],
        facilities=loaded["facilities"],
        snapshot_metadata=loaded.get("snapshot_metadata"),
    )


def write_snapshot_payload(snapshot_dir: Path, loaded_payload: dict[str, Any]) -> None:
    snapshot_dir = Path(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for key in ("items", "recipes", "facilities"):
        path = snapshot_dir / f"{key}.json"
        path.write_text(json.dumps(loaded_payload[key], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    metadata_path = snapshot_dir / SNAPSHOT_METADATA_FILENAME
    metadata_path.write_text(
        json.dumps(loaded_payload.get("snapshot_metadata", {}), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
