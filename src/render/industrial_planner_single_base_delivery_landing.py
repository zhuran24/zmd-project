"""Stable current landing bundle builder for the active IndustrialPlanner single-base delivery line.

This helper resolves the checked-in current-viewer pointer, materializes one
stable current-delivery directory with a copied viewer bundle under `viewer/`,
and renders a single-entry landing/download page that stays inside the active
`valley4_protocol_core` 70×70 contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import html
from pathlib import Path
import shutil
import tempfile
import zipfile
from typing import Any, Mapping, Sequence

from src.io.serializer import load_json_mapping
from src.render.industrial_planner_exact_status import normalize_non_authoritative_exact_status
from src.search.exact_campaign import atomic_write_json, sha256_file

_LANDING_MANIFEST_FILENAME = "landing_manifest.json"
_LANDING_SOURCE = "industrial_planner_single_base_delivery_landing_v2"
_LANDING_SCHEMA_VERSION = "1.1.0"

_CURRENT_BUNDLE_POINTER_SOURCE = "industrial_planner_single_base_current_bundle_pointer_v1"
_CURRENT_BUNDLE_POINTER_SCHEMA_VERSION = "1.0.0"
_CURRENT_BUNDLE_ARCHIVE_ROOT = "industrial_planner_current_single_base_delivery_bundle"
_CURRENT_BUNDLE_ZIP_FILENAME = "industrial_planner_current_single_base_delivery_bundle.zip"
_CURRENT_BUNDLE_POINTER_JSON_FILENAME = "current_single_base_delivery_bundle.json"
_CURRENT_BUNDLE_POINTER_MARKDOWN_FILENAME = "current_single_base_delivery_bundle.md"
_DOWNLOADS_SUBDIR = Path("downloads")

_DEFAULT_VIEWER_POINTER_JSON = Path("data/examples/industrial_planner/active_single_base_delivery_viewer.json")
_DEFAULT_OUTPUT_DIR = Path(".artifacts/industrial_planner_single_base_delivery_landing")
_VIEWER_SUBDIR = Path("viewer")


class SingleBaseDeliveryLandingBundleError(RuntimeError):
    """Raised when a stable current landing bundle cannot be produced safely."""


@dataclass(frozen=True)
class _CurrentBundleArchiveBuild:
    zip_path: Path
    pointer_json_path: Path
    pointer_markdown_path: Path
    zip_relative_path: str
    pointer_json_relative_path: str
    pointer_markdown_relative_path: str
    archive_root: str
    archive_sha256: str
    archive_size_bytes: int
    payload_file_count: int
    metadata_file_count: int

    @property
    def included_entry_count(self) -> int:
        return self.payload_file_count + self.metadata_file_count


@dataclass(frozen=True)
class SingleBaseDeliveryLandingBundleResult:
    release_id: str
    base_id: str
    lot_size: int
    delivery_status: str
    output_dir: Path
    viewer_source_dir: Path
    landing_manifest_path: Path
    landing_index_html_path: Path
    materialized_viewer_dir: Path
    current_bundle_zip_path: Path
    current_bundle_pointer_json_path: Path
    current_bundle_pointer_markdown_path: Path
    current_bundle_archive_sha256: str
    current_bundle_payload_file_count: int
    current_bundle_metadata_file_count: int
    quick_download_count: int
    download_group_count: int
    exact_full_scale_certified_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "base_id": self.base_id,
            "lot_size": self.lot_size,
            "delivery_status": self.delivery_status,
            "output_dir": str(self.output_dir),
            "viewer_source_dir": str(self.viewer_source_dir),
            "landing_manifest_path": str(self.landing_manifest_path),
            "landing_index_html_path": str(self.landing_index_html_path),
            "materialized_viewer_dir": str(self.materialized_viewer_dir),
            "current_bundle_zip_path": str(self.current_bundle_zip_path),
            "current_bundle_pointer_json_path": str(self.current_bundle_pointer_json_path),
            "current_bundle_pointer_markdown_path": str(self.current_bundle_pointer_markdown_path),
            "current_bundle_archive_sha256": self.current_bundle_archive_sha256,
            "current_bundle_payload_file_count": self.current_bundle_payload_file_count,
            "current_bundle_metadata_file_count": self.current_bundle_metadata_file_count,
            "quick_download_count": self.quick_download_count,
            "download_group_count": self.download_group_count,
            "exact_full_scale_certified_status": self.exact_full_scale_certified_status,
        }


def build_single_base_delivery_landing_bundle(
    *,
    project_root: Path,
    viewer_pointer_json_path: Path = _DEFAULT_VIEWER_POINTER_JSON,
    output_dir: Path = _DEFAULT_OUTPUT_DIR,
) -> SingleBaseDeliveryLandingBundleResult:
    project_root = Path(project_root).resolve()
    viewer_pointer_json_path = _resolve_repo_path(project_root, viewer_pointer_json_path)
    output_dir = _resolve_output_path(project_root, output_dir)

    pointer_payload = load_json_mapping(viewer_pointer_json_path)
    current_viewer = _mapping(pointer_payload.get("current_viewer"))
    if not current_viewer:
        raise SingleBaseDeliveryLandingBundleError(
            f"viewer pointer {viewer_pointer_json_path} does not contain a current_viewer mapping"
        )

    viewer_manifest_display = current_viewer.get("viewer_manifest_json")
    if not isinstance(viewer_manifest_display, str) or not viewer_manifest_display.strip():
        raise SingleBaseDeliveryLandingBundleError(
            f"viewer pointer {viewer_pointer_json_path} does not declare current_viewer.viewer_manifest_json"
        )
    viewer_manifest_path = _resolve_repo_path(project_root, Path(viewer_manifest_display))
    viewer_manifest_payload = load_json_mapping(viewer_manifest_path)

    viewer_dir_display = current_viewer.get("viewer_dir")
    if not isinstance(viewer_dir_display, str) or not viewer_dir_display.strip():
        raise SingleBaseDeliveryLandingBundleError(
            f"viewer pointer {viewer_pointer_json_path} does not declare current_viewer.viewer_dir"
        )
    viewer_source_dir = _resolve_repo_path(project_root, Path(viewer_dir_display))
    if not viewer_source_dir.is_dir():
        raise SingleBaseDeliveryLandingBundleError(
            f"current_viewer.viewer_dir is not a directory: {viewer_source_dir}"
        )

    current_release = _mapping(viewer_manifest_payload.get("current_release"))
    release_id = str(current_release.get("release_id", current_viewer.get("release_id", "unknown_release")))
    base_id = str(current_release.get("base_id", current_viewer.get("base_id", "unknown_base")))
    lot_size = int(current_release.get("lot_size", current_viewer.get("lot_size", 0)) or 0)
    delivery_status = str(current_release.get("delivery_status", current_viewer.get("delivery_status", "")))
    if delivery_status != "ready_for_single_base_delivery":
        raise SingleBaseDeliveryLandingBundleError(
            "landing bundle build requires a ready_for_single_base_delivery current viewer"
        )

    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging.", dir=str(output_dir.parent if output_dir.parent else project_root))
    )
    try:
        materialized_viewer_dir = staging_dir / _VIEWER_SUBDIR
        shutil.copytree(viewer_source_dir, materialized_viewer_dir)

        current_bundle_build = _materialize_current_bundle_archive(
            project_root=project_root,
            staging_dir=staging_dir,
            pointer_json_path=viewer_pointer_json_path,
            materialized_viewer_dir=materialized_viewer_dir,
            viewer_manifest_path=viewer_manifest_path,
            pointer_payload=pointer_payload,
            viewer_manifest_payload=viewer_manifest_payload,
        )

        landing_manifest_payload = _build_landing_manifest_payload(
            project_root=project_root,
            output_dir=output_dir,
            materialized_viewer_dir=materialized_viewer_dir,
            current_bundle_build=current_bundle_build,
            pointer_json_path=viewer_pointer_json_path,
            viewer_source_dir=viewer_source_dir,
            viewer_manifest_path=viewer_manifest_path,
            pointer_payload=pointer_payload,
            viewer_manifest_payload=viewer_manifest_payload,
        )
        atomic_write_json(staging_dir / _LANDING_MANIFEST_FILENAME, landing_manifest_payload)
        (staging_dir / "index.html").write_text(
            _render_landing_html(landing_manifest_payload),
            encoding="utf-8",
        )
        _commit_directory_swap(staging_dir=staging_dir, output_dir=output_dir)
    except Exception:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        raise

    manifest_path = output_dir / _LANDING_MANIFEST_FILENAME
    manifest_payload = load_json_mapping(manifest_path)
    current_landing = _mapping(manifest_payload.get("current_landing"))
    exact_payload = _mapping(manifest_payload.get("exact_full_scale_certified"))
    exact_status = normalize_non_authoritative_exact_status(
        exact_payload.get("status", "unknown"),
        context="landing_manifest.exact_full_scale_certified",
    )
    return SingleBaseDeliveryLandingBundleResult(
        release_id=str(current_landing.get("release_id", release_id)),
        base_id=str(current_landing.get("base_id", base_id)),
        lot_size=int(current_landing.get("lot_size", lot_size) or 0),
        delivery_status=str(current_landing.get("delivery_status", delivery_status)),
        output_dir=output_dir,
        viewer_source_dir=viewer_source_dir,
        landing_manifest_path=manifest_path,
        landing_index_html_path=output_dir / "index.html",
        materialized_viewer_dir=output_dir / _VIEWER_SUBDIR,
        current_bundle_zip_path=output_dir / str(current_landing.get("current_bundle_zip", (_DOWNLOADS_SUBDIR / _CURRENT_BUNDLE_ZIP_FILENAME).as_posix())),
        current_bundle_pointer_json_path=output_dir / str(current_landing.get("current_bundle_pointer_json", (_DOWNLOADS_SUBDIR / _CURRENT_BUNDLE_POINTER_JSON_FILENAME).as_posix())),
        current_bundle_pointer_markdown_path=output_dir / str(current_landing.get("current_bundle_pointer_markdown", (_DOWNLOADS_SUBDIR / _CURRENT_BUNDLE_POINTER_MARKDOWN_FILENAME).as_posix())),
        current_bundle_archive_sha256=str(current_landing.get("current_bundle_archive_sha256", "")),
        current_bundle_payload_file_count=int(current_landing.get("current_bundle_payload_file_count", 0) or 0),
        current_bundle_metadata_file_count=int(current_landing.get("current_bundle_metadata_file_count", 0) or 0),
        quick_download_count=len(manifest_payload.get("quick_downloads") or []),
        download_group_count=len(manifest_payload.get("download_groups") or []),
        exact_full_scale_certified_status=exact_status,
    )


def _build_landing_manifest_payload(
    *,
    project_root: Path,
    output_dir: Path,
    materialized_viewer_dir: Path,
    current_bundle_build: _CurrentBundleArchiveBuild,
    pointer_json_path: Path,
    viewer_source_dir: Path,
    viewer_manifest_path: Path,
    pointer_payload: Mapping[str, Any],
    viewer_manifest_payload: Mapping[str, Any],
) -> dict[str, Any]:
    current_viewer = _mapping(pointer_payload.get("current_viewer"))
    current_release = _mapping(viewer_manifest_payload.get("current_release"))
    exact_payload = _mapping(viewer_manifest_payload.get("exact_full_scale_certified"))
    exact_status = normalize_non_authoritative_exact_status(
        exact_payload.get("status", "unknown"),
        context="viewer_manifest.exact_full_scale_certified",
    )
    exact_note = str(exact_payload.get("note", ""))
    viewer_bundle = _mapping(viewer_manifest_payload.get("viewer_bundle"))

    quick_downloads = _prefix_quick_downloads(
        quick_downloads_raw=viewer_manifest_payload.get("quick_downloads"),
        prefix=f"{_VIEWER_SUBDIR.as_posix()}/",
    )
    download_groups = _prefix_download_groups(
        download_groups_raw=viewer_manifest_payload.get("download_groups"),
        prefix=f"{_VIEWER_SUBDIR.as_posix()}/",
    )

    current_landing = {
        "release_id": str(current_release.get("release_id", current_viewer.get("release_id", "unknown_release"))),
        "base_id": str(current_release.get("base_id", current_viewer.get("base_id", "unknown_base"))),
        "lot_size": int(current_release.get("lot_size", current_viewer.get("lot_size", 0)) or 0),
        "delivery_status": str(current_release.get("delivery_status", current_viewer.get("delivery_status", "unknown"))),
        "output_dir": _display_repo_path(project_root, output_dir),
        "landing_index_html": "index.html",
        "landing_manifest_json": _LANDING_MANIFEST_FILENAME,
        "materialized_viewer_dir": _VIEWER_SUBDIR.as_posix(),
        "viewer_index_html": (_VIEWER_SUBDIR / "index.html").as_posix(),
        "viewer_manifest_json": (_VIEWER_SUBDIR / "release_viewer_manifest.json").as_posix(),
        "selected_facility_type_count": int(
            viewer_bundle.get("selected_facility_type_count", current_viewer.get("selected_facility_type_count", 0))
            or 0
        ),
        "selected_pose_count": int(
            viewer_bundle.get("selected_pose_count", current_viewer.get("selected_pose_count", 0))
            or 0
        ),
        "payload_download_count": int(current_viewer.get("payload_download_count", 0) or 0),
        "metadata_download_count": int(current_viewer.get("metadata_download_count", 0) or 0),
        "current_bundle_zip": current_bundle_build.zip_relative_path,
        "current_bundle_pointer_json": current_bundle_build.pointer_json_relative_path,
        "current_bundle_pointer_markdown": current_bundle_build.pointer_markdown_relative_path,
        "current_bundle_archive_root": current_bundle_build.archive_root,
        "current_bundle_archive_sha256": current_bundle_build.archive_sha256,
        "current_bundle_archive_size_bytes": current_bundle_build.archive_size_bytes,
        "current_bundle_payload_file_count": current_bundle_build.payload_file_count,
        "current_bundle_metadata_file_count": current_bundle_build.metadata_file_count,
        "quick_download_count": len(quick_downloads),
        "download_group_count": len(download_groups),
        "scope_note": str(current_release.get("scope_note", current_viewer.get("scope_note", ""))),
        "source_viewer_pointer_json": _display_repo_path(project_root, pointer_json_path),
        "source_viewer_dir": _display_repo_path(project_root, viewer_source_dir),
    }

    actions = {
        "open_viewer": current_landing["viewer_index_html"],
        "download_current_bundle_zip": current_landing["current_bundle_zip"],
        "current_bundle_pointer_json": current_landing["current_bundle_pointer_json"],
        "current_bundle_pointer_markdown": current_landing["current_bundle_pointer_markdown"],
        "viewer_manifest_json": current_landing["viewer_manifest_json"],
        "landing_manifest_json": current_landing["landing_manifest_json"],
        "release_pointer_json": _meta_download_href(download_groups, "current_release_pointer_json"),
        "release_manifest_json": _meta_download_href(download_groups, "release_manifest_json"),
        "sha256sums": _meta_download_href(download_groups, "sha256sums"),
        "release_index_json": _meta_download_href(download_groups, "release_index_json"),
        "release_index_markdown": _meta_download_href(download_groups, "release_index_markdown"),
        "blueprint": _quick_download_href(quick_downloads, "industrial_planner_blueprint"),
        "validation_report": _quick_download_href(quick_downloads, "validation_report_json"),
        "throughput_report": _quick_download_href(quick_downloads, "throughput_report_json"),
        "run_summary": _quick_download_href(quick_downloads, "run_summary_json"),
    }

    return {
        "metadata": {
            "schema_version": _LANDING_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "source": _LANDING_SOURCE,
        },
        "current_landing": current_landing,
        "current_release": {
            "release_id": current_landing["release_id"],
            "base_id": current_landing["base_id"],
            "lot_size": current_landing["lot_size"],
            "delivery_status": current_landing["delivery_status"],
            "release_dir": str(current_release.get("release_dir", "")),
            "scope_note": current_landing["scope_note"],
        },
        "exact_full_scale_certified": {
            "status": exact_status,
            "note": exact_note,
        },
        "actions": actions,
        "quick_downloads": quick_downloads,
        "download_groups": download_groups,
        "current_bundle_archive": {
            "bundle_zip": current_bundle_build.zip_relative_path,
            "pointer_json": current_bundle_build.pointer_json_relative_path,
            "pointer_markdown": current_bundle_build.pointer_markdown_relative_path,
            "archive_root": current_bundle_build.archive_root,
            "archive_sha256": current_bundle_build.archive_sha256,
            "archive_size_bytes": current_bundle_build.archive_size_bytes,
            "payload_file_count": current_bundle_build.payload_file_count,
            "metadata_file_count": current_bundle_build.metadata_file_count,
            "included_entry_count": current_bundle_build.included_entry_count,
            "source_viewer_downloads_root": (_VIEWER_SUBDIR / "downloads").as_posix(),
        },
        "notes": [
            current_landing["scope_note"],
            exact_note,
            (
                "A stable one-file ZIP alias now sits under current_delivery/downloads/ so "
                "download-first consumers can pull the active bundle without piecing together "
                "individual sidecars by hand."
            ),
        ],
        "viewer_copy": {
            "materialized_viewer_dir": current_landing["materialized_viewer_dir"],
            "source_viewer_dir": current_landing["source_viewer_dir"],
            "copied_from_release_id": current_landing["release_id"],
            "viewer_source_manifest": _display_repo_path(project_root, viewer_manifest_path),
            "contains_downloads_root": (materialized_viewer_dir / "downloads").is_dir(),
        },
    }


def _prefix_quick_downloads(*, quick_downloads_raw: Any, prefix: str) -> list[dict[str, Any]]:
    items = list(quick_downloads_raw) if isinstance(quick_downloads_raw, Sequence) and not isinstance(quick_downloads_raw, (str, bytes, bytearray)) else []
    prefixed: list[dict[str, Any]] = []
    for entry in items:
        if not isinstance(entry, Mapping):
            continue
        href = str(entry.get("href", "")).strip()
        if not href:
            continue
        prefixed.append(
            {
                "id": str(entry.get("id", "")),
                "label": str(entry.get("label", "")),
                "href": f"{prefix}{href}",
                "kind": str(entry.get("kind", "")),
                "stage": str(entry.get("stage", "")),
                "required_for_delivery": bool(entry.get("required_for_delivery")),
                "role": str(entry.get("role", "")),
            }
        )
    return prefixed


def _prefix_download_groups(*, download_groups_raw: Any, prefix: str) -> list[dict[str, Any]]:
    groups = list(download_groups_raw) if isinstance(download_groups_raw, Sequence) and not isinstance(download_groups_raw, (str, bytes, bytearray)) else []
    normalized: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        entries_raw = group.get("entries")
        entries = list(entries_raw) if isinstance(entries_raw, Sequence) and not isinstance(entries_raw, (str, bytes, bytearray)) else []
        prefixed_entries: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            href = str(entry.get("href", "")).strip()
            if not href:
                continue
            prefixed_entry = dict(entry)
            prefixed_entry["href"] = f"{prefix}{href}"
            prefixed_entries.append(prefixed_entry)
        normalized.append(
            {
                "group_id": str(group.get("group_id", "")),
                "title": str(group.get("title", "")),
                "description": str(group.get("description", "")),
                "entries": prefixed_entries,
            }
        )
    return normalized


def _meta_download_href(download_groups: Sequence[Mapping[str, Any]], label: str) -> str | None:
    for group in download_groups:
        if str(group.get("group_id", "")) != "metadata":
            continue
        entries = group.get("entries") if isinstance(group.get("entries"), list) else []
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            if str(entry.get("label", "")) == label:
                href = str(entry.get("href", "")).strip()
                return href or None
    return None


def _quick_download_href(quick_downloads: Sequence[Mapping[str, Any]], download_id: str) -> str | None:
    for entry in quick_downloads:
        if str(entry.get("id", "")) == download_id:
            href = str(entry.get("href", "")).strip()
            return href or None
    return None


def _materialize_current_bundle_archive(
    *,
    project_root: Path,
    staging_dir: Path,
    pointer_json_path: Path,
    materialized_viewer_dir: Path,
    viewer_manifest_path: Path,
    pointer_payload: Mapping[str, Any],
    viewer_manifest_payload: Mapping[str, Any],
) -> _CurrentBundleArchiveBuild:
    viewer_downloads_root = materialized_viewer_dir / "downloads"
    release_root = viewer_downloads_root / "release"
    meta_root = viewer_downloads_root / "meta"
    if not release_root.is_dir():
        raise SingleBaseDeliveryLandingBundleError(
            f"current viewer bundle is missing release downloads root: {release_root}"
        )
    if not meta_root.is_dir():
        raise SingleBaseDeliveryLandingBundleError(
            f"current viewer bundle is missing metadata downloads root: {meta_root}"
        )

    payload_files = sorted(path for path in release_root.rglob("*") if path.is_file())
    metadata_files = sorted(path for path in meta_root.rglob("*") if path.is_file())
    if not payload_files:
        raise SingleBaseDeliveryLandingBundleError(
            f"current viewer bundle has no payload files under {release_root}"
        )
    if not metadata_files:
        raise SingleBaseDeliveryLandingBundleError(
            f"current viewer bundle has no metadata files under {meta_root}"
        )

    downloads_dir = staging_dir / _DOWNLOADS_SUBDIR
    downloads_dir.mkdir(parents=True, exist_ok=True)
    zip_path = downloads_dir / _CURRENT_BUNDLE_ZIP_FILENAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        _write_directory_to_zip(
            archive=archive,
            source_root=release_root,
            archive_root=Path(_CURRENT_BUNDLE_ARCHIVE_ROOT) / "release",
        )
        _write_directory_to_zip(
            archive=archive,
            source_root=meta_root,
            archive_root=Path(_CURRENT_BUNDLE_ARCHIVE_ROOT) / "meta",
        )

    zip_relative_path = (_DOWNLOADS_SUBDIR / _CURRENT_BUNDLE_ZIP_FILENAME).as_posix()
    pointer_json_relative_path = (_DOWNLOADS_SUBDIR / _CURRENT_BUNDLE_POINTER_JSON_FILENAME).as_posix()
    pointer_markdown_relative_path = (_DOWNLOADS_SUBDIR / _CURRENT_BUNDLE_POINTER_MARKDOWN_FILENAME).as_posix()

    current_release = _mapping(viewer_manifest_payload.get("current_release"))
    exact_payload = _mapping(viewer_manifest_payload.get("exact_full_scale_certified"))
    exact_status = normalize_non_authoritative_exact_status(
        exact_payload.get("status", "unknown"),
        context="viewer_manifest.exact_full_scale_certified",
    )
    exact_note = str(exact_payload.get("note", ""))
    current_viewer = _mapping(pointer_payload.get("current_viewer"))
    pointer_payload_data = {
        "metadata": {
            "schema_version": _CURRENT_BUNDLE_POINTER_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "source": _CURRENT_BUNDLE_POINTER_SOURCE,
        },
        "current_bundle": {
            "release_id": str(current_release.get("release_id", current_viewer.get("release_id", "unknown_release"))),
            "base_id": str(current_release.get("base_id", current_viewer.get("base_id", "unknown_base"))),
            "lot_size": int(current_release.get("lot_size", current_viewer.get("lot_size", 0)) or 0),
            "delivery_status": str(current_release.get("delivery_status", current_viewer.get("delivery_status", "unknown"))),
            "bundle_zip": zip_relative_path,
            "pointer_json": pointer_json_relative_path,
            "pointer_markdown": pointer_markdown_relative_path,
            "archive_root": _CURRENT_BUNDLE_ARCHIVE_ROOT,
            "archive_sha256": sha256_file(zip_path),
            "archive_size_bytes": int(zip_path.stat().st_size),
            "payload_file_count": len(payload_files),
            "metadata_file_count": len(metadata_files),
            "included_entry_count": len(payload_files) + len(metadata_files),
            "source_viewer_downloads_root": (_VIEWER_SUBDIR / "downloads").as_posix(),
            "scope_note": str(current_release.get("scope_note", current_viewer.get("scope_note", ""))),
        },
        "exact_full_scale_certified": {
            "status": exact_status,
            "note": exact_note,
        },
        "included_roots": {
            "release": (Path(_CURRENT_BUNDLE_ARCHIVE_ROOT) / "release").as_posix(),
            "meta": (Path(_CURRENT_BUNDLE_ARCHIVE_ROOT) / "meta").as_posix(),
        },
        "source_inputs": {
            "source_viewer_pointer_json": _display_repo_path(project_root, pointer_json_path),
            "source_viewer_manifest_json": _display_repo_path(project_root, viewer_manifest_path),
        },
        "notes": [
            str(current_release.get("scope_note", current_viewer.get("scope_note", ""))),
            str(exact_payload.get("note", "")),
            (
                "This ZIP is a stable download-first alias for the active single-base release. "
                "It packages the current release payload tree and the current release metadata tree "
                "without widening the contract beyond valley4_protocol_core 70×70."
            ),
        ],
    }
    pointer_json_path_output = downloads_dir / _CURRENT_BUNDLE_POINTER_JSON_FILENAME
    pointer_markdown_path_output = downloads_dir / _CURRENT_BUNDLE_POINTER_MARKDOWN_FILENAME
    atomic_write_json(pointer_json_path_output, pointer_payload_data)
    pointer_markdown_path_output.write_text(
        _render_current_bundle_pointer_markdown(pointer_payload_data),
        encoding="utf-8",
    )

    current_bundle = _mapping(pointer_payload_data.get("current_bundle"))
    return _CurrentBundleArchiveBuild(
        zip_path=zip_path,
        pointer_json_path=pointer_json_path_output,
        pointer_markdown_path=pointer_markdown_path_output,
        zip_relative_path=zip_relative_path,
        pointer_json_relative_path=pointer_json_relative_path,
        pointer_markdown_relative_path=pointer_markdown_relative_path,
        archive_root=_CURRENT_BUNDLE_ARCHIVE_ROOT,
        archive_sha256=str(current_bundle.get("archive_sha256", "")),
        archive_size_bytes=int(current_bundle.get("archive_size_bytes", 0) or 0),
        payload_file_count=int(current_bundle.get("payload_file_count", 0) or 0),
        metadata_file_count=int(current_bundle.get("metadata_file_count", 0) or 0),
    )


def _write_directory_to_zip(*, archive: zipfile.ZipFile, source_root: Path, archive_root: Path) -> None:
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        archive.write(path, arcname=(archive_root / path.relative_to(source_root)).as_posix())


def _render_current_bundle_pointer_markdown(payload: Mapping[str, Any]) -> str:
    current_bundle = _mapping(payload.get("current_bundle"))
    exact_payload = _mapping(payload.get("exact_full_scale_certified"))
    notes = [str(note) for note in (payload.get("notes") or []) if str(note).strip()]

    lines = [
        "# Current Single-Base Delivery Bundle ZIP",
        "",
        f"- Release id: `{current_bundle.get('release_id', '')}`",
        f"- Base id: `{current_bundle.get('base_id', '')}`",
        f"- Lot size: `{current_bundle.get('lot_size', '')}`",
        f"- Delivery status: `{current_bundle.get('delivery_status', '')}`",
        f"- Bundle ZIP: `{current_bundle.get('bundle_zip', '')}`",
        f"- Pointer JSON: `{current_bundle.get('pointer_json', '')}`",
        f"- Archive root: `{current_bundle.get('archive_root', '')}`",
        f"- Archive SHA256: `{current_bundle.get('archive_sha256', '')}`",
        f"- Archive size: `{_format_size_bytes(current_bundle.get('archive_size_bytes', 0))}`",
        (
            "- Included files: "
            f"`{current_bundle.get('payload_file_count', 0)}` payload + "
            f"`{current_bundle.get('metadata_file_count', 0)}` metadata"
        ),
        f"- Exact full-scale CERTIFIED status: `{exact_payload.get('status', 'unknown')}`",
    ]
    if str(exact_payload.get("note", "")).strip():
        lines.append(f"- Exact note: {exact_payload.get('note', '')}")
    if notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in notes)
    lines.append("")
    return "\n".join(lines)


def _format_size_bytes(value: Any) -> str:
    try:
        size = int(value)
    except (TypeError, ValueError):
        size = 0
    units = ["B", "KB", "MB", "GB"]
    display = float(size)
    unit = units[0]
    for unit in units:
        if display < 1024 or unit == units[-1]:
            break
        display /= 1024.0
    if unit == "B":
        return f"{int(display)} {unit}"
    return f"{display:.1f} {unit}"


def _render_landing_html(payload: Mapping[str, Any]) -> str:
    current = _mapping(payload.get("current_landing"))
    exact_payload = _mapping(payload.get("exact_full_scale_certified"))
    current_bundle_archive = _mapping(payload.get("current_bundle_archive"))
    actions = _mapping(payload.get("actions"))
    quick_downloads = list(payload.get("quick_downloads") or [])
    download_groups = list(payload.get("download_groups") or [])
    notes = [str(note) for note in (payload.get("notes") or []) if str(note).strip()]

    action_links = [
        _render_action_link("Open interactive viewer", actions.get("open_viewer"), primary=True),
        _render_action_link("Download current bundle ZIP", actions.get("download_current_bundle_zip")),
        _render_action_link("Landing manifest JSON", actions.get("landing_manifest_json")),
        _render_action_link("Current bundle pointer JSON", actions.get("current_bundle_pointer_json")),
        _render_action_link("Viewer manifest JSON", actions.get("viewer_manifest_json")),
        _render_action_link("Release manifest JSON", actions.get("release_manifest_json")),
        _render_action_link("Checksums", actions.get("sha256sums")),
    ]
    action_links_html = "\n".join(link for link in action_links if link)

    quick_cards_html = "\n".join(_render_quick_download_card(entry) for entry in quick_downloads if isinstance(entry, Mapping))
    groups_html = "\n".join(_render_download_group(group) for group in download_groups if isinstance(group, Mapping))
    notes_html = "\n".join(f"<li>{_escape(note)}</li>" for note in notes)

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
<title>IndustrialPlanner Current Single-Base Delivery</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #0d1117; color: #e6edf3; font-family: "Segoe UI", system-ui, sans-serif; }}
a {{ color: #58a6ff; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.page {{ max-width: 1160px; margin: 0 auto; padding: 28px 20px 48px; }}
.hero {{ background: linear-gradient(180deg, rgba(88,166,255,0.12), rgba(13,17,23,0.92)); border: 1px solid #30363d; border-radius: 18px; padding: 24px; margin-bottom: 18px; }}
.eyebrow {{ color: #8b949e; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 10px; }}
h1 {{ margin: 0 0 10px; font-size: 30px; }}
.lead {{ color: #c9d1d9; line-height: 1.65; max-width: 900px; }}
.actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}
.button {{ display: inline-flex; align-items: center; justify-content: center; border: 1px solid #30363d; border-radius: 999px; padding: 10px 14px; background: #161b22; font-size: 14px; }}
.button.primary {{ background: #1f6feb; border-color: #1f6feb; color: #ffffff; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin: 18px 0; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 16px; padding: 16px; }}
.card h2, .card h3 {{ margin: 0 0 8px; font-size: 16px; }}
.kicker {{ color: #8b949e; font-size: 12px; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 6px; }}
.value {{ font-size: 24px; font-weight: 700; color: #58a6ff; }}
.muted {{ color: #8b949e; line-height: 1.55; }}
.panel {{ background: #0d1117; border: 1px solid #30363d; border-radius: 16px; padding: 18px; margin-top: 16px; }}
.panel h2 {{ margin: 0 0 12px; font-size: 18px; }}
.badge {{ display: inline-block; border: 1px solid #30363d; border-radius: 999px; padding: 3px 8px; font-size: 12px; color: #8b949e; margin-right: 8px; }}
.quick-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
.quick-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 14px; padding: 14px; }}
.quick-card .title {{ font-size: 15px; font-weight: 600; margin-bottom: 8px; }}
.quick-card .meta {{ color: #8b949e; font-size: 12px; line-height: 1.5; margin-bottom: 8px; }}
.group {{ border-top: 1px solid #21262d; padding-top: 14px; margin-top: 14px; }}
.group:first-of-type {{ border-top: none; padding-top: 0; margin-top: 0; }}
.group-title {{ font-size: 15px; font-weight: 600; margin-bottom: 4px; }}
.group-desc {{ color: #8b949e; font-size: 13px; line-height: 1.5; margin-bottom: 10px; }}
.entry-list {{ display: grid; gap: 10px; }}
.entry {{ display: flex; justify-content: space-between; gap: 16px; border: 1px solid #21262d; border-radius: 12px; padding: 10px 12px; background: #161b22; }}
.entry .meta {{ color: #8b949e; font-size: 12px; text-align: right; line-height: 1.45; }}
ul {{ margin: 0; padding-left: 18px; }}
footer {{ margin-top: 22px; color: #8b949e; font-size: 12px; line-height: 1.5; }}
code {{ background: rgba(110,118,129,0.2); padding: 1px 5px; border-radius: 6px; }}
</style>
</head>
<body>
<div class=\"page\">
  <section class=\"hero\">
    <div class=\"eyebrow\">IndustrialPlanner · current single-base delivery</div>
    <h1>{_escape(current.get('base_id', 'unknown_base'))} · {current.get('lot_size', '')}×{current.get('lot_size', '')}</h1>
    <p class=\"lead\">Stable single-entry landing/download page for the active IndustrialPlanner contract. It materializes the current viewer pointer into one direct page with a copied viewer bundle under <code>viewer/</code> and a one-file ZIP alias under <code>downloads/</code>, while keeping every other base and the outer-deployment line as <code>future_scope</code>.</p>
    <div class=\"actions\">{action_links_html}</div>
  </section>

  <section class=\"grid\">
    <div class=\"card\"><div class=\"kicker\">Release id</div><div class=\"value\">{_escape(current.get('release_id', ''))}</div></div>
    <div class=\"card\"><div class=\"kicker\">Delivery status</div><div class=\"value\">{_escape(current.get('delivery_status', ''))}</div></div>
    <div class=\"card\"><div class=\"kicker\">Viewer geometry</div><div class=\"value\">{current.get('selected_facility_type_count', 0)} / {current.get('selected_pose_count', 0)}</div><div class=\"muted\">facility types / selected poses</div></div>
    <div class=\"card\"><div class=\"kicker\">Download surface</div><div class=\"value\">{current.get('quick_download_count', 0)} / {current.get('download_group_count', 0)}</div><div class=\"muted\">quick downloads / grouped sections</div></div>
  </section>

  <section class=\"panel\">
    <h2>Boundary notes</h2>
    <p class=\"muted\"><span class=\"badge\">scope</span>{_escape(current.get('scope_note', ''))}</p>
    <p class=\"muted\" style=\"margin-top:10px;\"><span class=\"badge\">exact</span>full-scale 70×70 exact <code>CERTIFIED</code> status: <strong>{_escape(exact_payload.get('status', 'unknown'))}</strong>. {_escape(exact_payload.get('note', ''))}</p>
  </section>

  <section class=\"panel\">
    <h2>One-file current bundle</h2>
    <p class=\"muted\"><span class=\"badge\">zip</span><code>{_escape(current_bundle_archive.get('bundle_zip', actions.get('download_current_bundle_zip', '')))}</code></p>
    <p class=\"muted\" style=\"margin-top:10px;\"><span class=\"badge\">contents</span>{current_bundle_archive.get('payload_file_count', 0)} payload files + {current_bundle_archive.get('metadata_file_count', 0)} metadata files, packaged as one download-first bundle alias.</p>
    <p class=\"muted\" style=\"margin-top:10px;\"><span class=\"badge\">sha256</span><code>{_escape(current_bundle_archive.get('archive_sha256', ''))}</code></p>
    <p class=\"muted\" style=\"margin-top:10px;\"><span class=\"badge\">size</span>{_escape(_format_size_bytes(current_bundle_archive.get('archive_size_bytes', 0)))}</p>
  </section>

  <section class=\"panel\">
    <h2>Quick downloads</h2>
    <div class=\"quick-grid\">{quick_cards_html}</div>
  </section>

  <section class=\"panel\">
    <h2>Grouped downloads</h2>
    {groups_html}
  </section>

  <section class=\"panel\">
    <h2>What lives in this current directory</h2>
    <ul>
      <li><code>index.html</code> — this stable landing/download page</li>
      <li><code>{_escape(current.get('landing_manifest_json', 'landing_manifest.json'))}</code> — machine-readable landing summary</li>
      <li><code>{_escape(current.get('materialized_viewer_dir', 'viewer'))}/</code> — copied current viewer bundle with its own <code>index.html</code>, <code>release_viewer_manifest.json</code>, and <code>downloads/</code> tree</li>
      <li><code>downloads/</code> — stable ZIP alias plus pointer sidecars for the current release bundle</li>
      <li>Source viewer pointer used for this materialization: <code>{_escape(current.get('source_viewer_pointer_json', ''))}</code></li>
    </ul>
  </section>

  <section class=\"panel\">
    <h2>Current notes</h2>
    <ul>{notes_html}</ul>
  </section>

  <footer>
    Generated from the checked-in current-viewer pointer for the active <code>valley4_protocol_core</code> 70×70 line. This landing page is intentionally narrower than a future multi-base portal, now exposes a one-file current bundle alias for download-first consumers, and does not claim the full exact solver end-state has already been certified.
  </footer>
</div>
</body>
</html>
"""


def _render_action_link(label: str, href: Any, *, primary: bool = False) -> str:
    target = str(href).strip() if isinstance(href, str) else ""
    if not target:
        return ""
    classes = "button primary" if primary else "button"
    return f'<a class="{classes}" href="{_escape(target)}">{_escape(label)}</a>'


def _render_quick_download_card(entry: Mapping[str, Any]) -> str:
    href = str(entry.get("href", "")).strip()
    label = str(entry.get("label", entry.get("id", "download")))
    meta_bits = [str(entry.get("kind", "")).strip(), str(entry.get("stage", "")).strip()]
    role = str(entry.get("role", "")).strip()
    required = bool(entry.get("required_for_delivery"))
    meta_line = " · ".join(bit for bit in meta_bits if bit)
    required_line = "required for delivery" if required else "supplementary"
    role_html = f"<div class=\"meta\">{_escape(role)}</div>" if role else ""
    return (
        "<div class=\"quick-card\">"
        f"<div class=\"title\"><a href=\"{_escape(href)}\">{_escape(label)}</a></div>"
        f"<div class=\"meta\">{_escape(meta_line)}<br>{_escape(required_line)}</div>"
        f"{role_html}"
        "</div>"
    )


def _render_download_group(group: Mapping[str, Any]) -> str:
    entries = list(group.get("entries") or [])
    entries_html = "\n".join(_render_group_entry(entry) for entry in entries if isinstance(entry, Mapping))
    return (
        f'<div class="group">'
        f'<div class="group-title">{_escape(str(group.get("title", "")))}</div>'
        f'<div class="group-desc">{_escape(str(group.get("description", "")))}</div>'
        f'<div class="entry-list">{entries_html}</div>'
        '</div>'
    )


def _render_group_entry(entry: Mapping[str, Any]) -> str:
    href = str(entry.get("href", "")).strip()
    label = str(entry.get("label", "download"))
    meta_bits = [str(entry.get("kind", "")).strip(), str(entry.get("stage", "")).strip()]
    if entry.get("required_for_delivery"):
        meta_bits.append("required")
    role = str(entry.get("role", "")).strip()
    sha256 = str(entry.get("sha256", "")).strip()
    side = "<br>".join(
        _escape(bit)
        for bit in ([" · ".join(bit for bit in meta_bits if bit)] + ([role] if role else []) + ([f"sha256: {sha256[:12]}…"] if sha256 else []))
        if bit
    )
    return (
        '<div class="entry">'
        f'<div><a href="{_escape(href)}">{_escape(label)}</a></div>'
        f'<div class="meta">{side}</div>'
        '</div>'
    )


def _commit_directory_swap(*, staging_dir: Path, output_dir: Path) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise SingleBaseDeliveryLandingBundleError(
            f"landing output path already exists and is not a directory: {output_dir}"
        )

    backup_dir: Path | None = None
    if output_dir.exists():
        backup_dir = Path(
            tempfile.mkdtemp(prefix=f".{output_dir.name}.backup.", dir=str(output_dir.parent))
        )
        shutil.rmtree(backup_dir)
        output_dir.rename(backup_dir)

    try:
        shutil.move(str(staging_dir), str(output_dir))
    except Exception:
        if backup_dir is not None and backup_dir.exists() and not output_dir.exists():
            backup_dir.rename(output_dir)
        raise
    else:
        if backup_dir is not None and backup_dir.exists():
            shutil.rmtree(backup_dir)


def _resolve_repo_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    resolved = candidate if candidate.is_absolute() else project_root / candidate
    resolved = resolved.resolve()
    if not resolved.exists():
        raise SingleBaseDeliveryLandingBundleError(f"required path does not exist: {resolved}")
    return resolved


def _resolve_output_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    resolved = candidate if candidate.is_absolute() else project_root / candidate
    resolved = resolved.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _display_repo_path(project_root: Path, path: Path) -> str:
    resolved = Path(path).resolve()
    project_root = Path(project_root).resolve()
    try:
        return resolved.relative_to(project_root).as_posix()
    except ValueError:
        return str(resolved)


def _mapping(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
