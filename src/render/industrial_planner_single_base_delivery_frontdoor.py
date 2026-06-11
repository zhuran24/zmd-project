"""Higher-level repo front door for the active IndustrialPlanner single-base delivery line.

This helper sits one level above the stable ``current_delivery/`` landing bundle.
It renders a small repo-facing entry page and machine-readable manifest in the
checked-in ``data/examples/industrial_planner/`` directory so downstream users
can find the active single-base consumer entry without first guessing the
current release id or current-delivery subdirectory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import html
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping, Sequence

from src.io.serializer import load_json_mapping
from src.render.industrial_planner_exact_status import normalize_non_authoritative_exact_status
from src.search.exact_campaign import atomic_write_json, sha256_file

_FRONTDOOR_MANIFEST_FILENAME = "frontdoor_manifest.json"
_FRONTDOOR_INDEX_FILENAME = "index.html"
_FRONTDOOR_SOURCE = "industrial_planner_single_base_delivery_frontdoor_v7"
_FRONTDOOR_SCHEMA_VERSION = "1.6.0"

_LATEST_BUNDLE_POINTER_SOURCE = "industrial_planner_single_base_latest_bundle_pointer_v1"
_LATEST_BUNDLE_POINTER_SCHEMA_VERSION = "1.0.0"
_LATEST_BUNDLE_ZIP_FILENAME = "industrial_planner_latest_single_base_delivery_bundle.zip"
_LATEST_BUNDLE_POINTER_JSON_FILENAME = "latest_single_base_delivery_bundle.json"
_LATEST_BUNDLE_POINTER_MARKDOWN_FILENAME = "latest_single_base_delivery_bundle.md"
_ENTRYPOINTS_JSON_FILENAME = "active_single_base_delivery_entrypoints.json"
_ENTRYPOINTS_MARKDOWN_FILENAME = "active_single_base_delivery_entrypoints.md"
_SURFACE_ALIGNMENT_JSON_FILENAME = "surface_alignment_summary.json"
_SURFACE_ALIGNMENT_MARKDOWN_FILENAME = "surface_alignment_summary.md"
_SURFACE_ALIGNMENT_CONSOLE_FILENAME = "surface_alignment_summary.txt"
_SURFACE_HEALTH_JSON_FILENAME = "current_surface_health.json"
_SURFACE_HEALTH_MARKDOWN_FILENAME = "current_surface_health.md"
_SURFACE_HEALTH_CONSOLE_FILENAME = "current_surface_health.txt"

_DEFAULT_LANDING_MANIFEST_JSON = Path("data/examples/industrial_planner/current_delivery/landing_manifest.json")
_DEFAULT_OUTPUT_DIR = Path("data/examples/industrial_planner")
_DEFAULT_SURFACE_ALIGNMENT_JSON = Path(
    ".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json"
)
_DEFAULT_SURFACE_ALIGNMENT_MARKDOWN = Path(
    ".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.md"
)
_DEFAULT_SURFACE_ALIGNMENT_CONSOLE = Path(
    ".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.txt"
)
_DEFAULT_SURFACE_HEALTH_JSON = Path("data/examples/industrial_planner/current_surface_health.json")
_DEFAULT_SURFACE_HEALTH_MARKDOWN = Path("data/examples/industrial_planner/current_surface_health.md")
_DEFAULT_SURFACE_HEALTH_CONSOLE = Path("data/examples/industrial_planner/current_surface_health.txt")


class SingleBaseDeliveryFrontdoorError(RuntimeError):
    """Raised when the repo-facing current front door cannot be produced safely."""


@dataclass(frozen=True)
class SingleBaseDeliveryFrontdoorResult:
    release_id: str
    base_id: str
    lot_size: int
    delivery_status: str
    output_dir: Path
    frontdoor_manifest_path: Path
    frontdoor_index_html_path: Path
    current_delivery_index_html: str
    latest_bundle_zip_path: Path
    latest_bundle_pointer_json_path: Path
    latest_bundle_pointer_markdown_path: Path
    quick_download_count: int
    download_group_count: int
    exact_full_scale_certified_status: str
    surface_alignment_status: str | None = None
    surface_alignment_check_count: int | None = None
    surface_alignment_drift_check_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "base_id": self.base_id,
            "lot_size": self.lot_size,
            "delivery_status": self.delivery_status,
            "output_dir": str(self.output_dir),
            "frontdoor_manifest_path": str(self.frontdoor_manifest_path),
            "frontdoor_index_html_path": str(self.frontdoor_index_html_path),
            "current_delivery_index_html": self.current_delivery_index_html,
            "latest_bundle_zip_path": str(self.latest_bundle_zip_path),
            "latest_bundle_pointer_json_path": str(self.latest_bundle_pointer_json_path),
            "latest_bundle_pointer_markdown_path": str(self.latest_bundle_pointer_markdown_path),
            "quick_download_count": self.quick_download_count,
            "download_group_count": self.download_group_count,
            "exact_full_scale_certified_status": self.exact_full_scale_certified_status,
            "surface_alignment_status": self.surface_alignment_status,
            "surface_alignment_check_count": self.surface_alignment_check_count,
            "surface_alignment_drift_check_count": self.surface_alignment_drift_check_count,
        }


@dataclass(frozen=True)
class _LatestBundleAliasBuild:
    zip_path: Path
    pointer_json_path: Path
    pointer_markdown_path: Path
    zip_relative_path: str
    pointer_json_relative_path: str
    pointer_markdown_relative_path: str
    archive_sha256: str
    archive_size_bytes: int
    payload_file_count: int
    metadata_file_count: int
    included_entry_count: int
    source_bundle_relative_path: str
    source_pointer_json_relative_path: str
    source_pointer_markdown_relative_path: str


@dataclass(frozen=True)
class _OptionalScriptEntrypointsRefs:
    json_relative_path: str | None
    markdown_relative_path: str | None
    json_repo_path: str | None
    markdown_repo_path: str | None


@dataclass(frozen=True)
class _OptionalSurfaceAlignmentRefs:
    json_relative_path: str | None
    markdown_relative_path: str | None
    console_relative_path: str | None
    json_repo_path: str | None
    markdown_repo_path: str | None
    console_repo_path: str | None
    status: str | None
    checked_check_count: int | None
    clean_check_count: int | None
    drift_check_count: int | None
    helper_link_count: int | None
    helper_link_clean_count: int | None
    release_id: str | None
    delivery_status: str | None


@dataclass(frozen=True)
class _OptionalSurfaceHealthRefs:
    json_relative_path: str | None
    markdown_relative_path: str | None
    console_relative_path: str | None
    json_repo_path: str | None
    markdown_repo_path: str | None
    console_repo_path: str | None
    status: str | None
    summary_text: str | None
    checked_check_count: int | None
    clean_check_count: int | None
    drift_check_count: int | None
    helper_link_count: int | None
    helper_link_clean_count: int | None
    release_id: str | None
    delivery_status: str | None


def build_single_base_delivery_frontdoor(
    *,
    project_root: Path,
    landing_manifest_json_path: Path = _DEFAULT_LANDING_MANIFEST_JSON,
    output_dir: Path = _DEFAULT_OUTPUT_DIR,
    entrypoints_json_path: Path | None = None,
    entrypoints_markdown_path: Path | None = None,
    require_entrypoints: bool = False,
    surface_alignment_json_path: Path | None = _DEFAULT_SURFACE_ALIGNMENT_JSON,
    surface_alignment_markdown_path: Path | None = _DEFAULT_SURFACE_ALIGNMENT_MARKDOWN,
    surface_alignment_console_path: Path | None = _DEFAULT_SURFACE_ALIGNMENT_CONSOLE,
    require_surface_alignment: bool = False,
    surface_health_json_path: Path | None = _DEFAULT_SURFACE_HEALTH_JSON,
    surface_health_markdown_path: Path | None = _DEFAULT_SURFACE_HEALTH_MARKDOWN,
    surface_health_console_path: Path | None = _DEFAULT_SURFACE_HEALTH_CONSOLE,
    require_surface_health: bool = False,
) -> SingleBaseDeliveryFrontdoorResult:
    project_root = Path(project_root).resolve()
    landing_manifest_json_path = _resolve_repo_path(project_root, landing_manifest_json_path)
    output_dir = _resolve_output_dir(project_root, output_dir)

    landing_payload = load_json_mapping(landing_manifest_json_path)
    current_landing = _mapping(landing_payload.get("current_landing"))
    if not current_landing:
        raise SingleBaseDeliveryFrontdoorError(
            f"landing manifest {landing_manifest_json_path} does not contain a current_landing mapping"
        )

    delivery_status = str(current_landing.get("delivery_status", "")).strip()
    if delivery_status != "ready_for_single_base_delivery":
        raise SingleBaseDeliveryFrontdoorError(
            "repo front door build requires a ready_for_single_base_delivery landing manifest"
        )

    landing_dir = landing_manifest_json_path.parent.resolve()
    landing_index_html_path = landing_dir / "index.html"
    if not landing_index_html_path.is_file():
        raise SingleBaseDeliveryFrontdoorError(
            f"landing index HTML is missing next to {landing_manifest_json_path}: {landing_index_html_path}"
        )

    latest_bundle_alias = _materialize_latest_bundle_alias(
        project_root=project_root,
        output_dir=output_dir,
        landing_manifest_json_path=landing_manifest_json_path,
        landing_payload=landing_payload,
    )
    script_entrypoints = _resolve_optional_script_entrypoints_refs(
        project_root=project_root,
        output_dir=output_dir,
        entrypoints_json_path=entrypoints_json_path,
        entrypoints_markdown_path=entrypoints_markdown_path,
        require_entrypoints=require_entrypoints,
    )
    surface_alignment = _resolve_optional_surface_alignment_refs(
        project_root=project_root,
        output_dir=output_dir,
        json_path=surface_alignment_json_path,
        markdown_path=surface_alignment_markdown_path,
        console_path=surface_alignment_console_path,
        require_surface_alignment=require_surface_alignment,
    )
    surface_health = _resolve_optional_surface_health_refs(
        project_root=project_root,
        output_dir=output_dir,
        json_path=surface_health_json_path,
        markdown_path=surface_health_markdown_path,
        console_path=surface_health_console_path,
        require_surface_health=require_surface_health,
    )

    frontdoor_payload = _build_frontdoor_manifest_payload(
        project_root=project_root,
        output_dir=output_dir,
        landing_manifest_json_path=landing_manifest_json_path,
        landing_payload=landing_payload,
        latest_bundle_alias=latest_bundle_alias,
        script_entrypoints=script_entrypoints,
        surface_alignment=surface_alignment,
        surface_health=surface_health,
    )
    frontdoor_manifest_path = output_dir / _FRONTDOOR_MANIFEST_FILENAME
    frontdoor_index_html_path = output_dir / _FRONTDOOR_INDEX_FILENAME
    atomic_write_json(frontdoor_manifest_path, frontdoor_payload)
    _atomic_write_text(frontdoor_index_html_path, _render_frontdoor_html(frontdoor_payload))

    manifest_payload = load_json_mapping(frontdoor_manifest_path)
    current_frontdoor = _mapping(manifest_payload.get("current_frontdoor"))
    exact_payload = _mapping(manifest_payload.get("exact_full_scale_certified"))
    exact_status = normalize_non_authoritative_exact_status(
        exact_payload.get("status", "unknown"),
        context="frontdoor_manifest.exact_full_scale_certified",
    )
    surface_alignment_payload = _mapping(manifest_payload.get("surface_alignment"))
    return SingleBaseDeliveryFrontdoorResult(
        release_id=str(current_frontdoor.get("release_id", "unknown_release")),
        base_id=str(current_frontdoor.get("base_id", "unknown_base")),
        lot_size=int(current_frontdoor.get("lot_size", 0) or 0),
        delivery_status=str(current_frontdoor.get("delivery_status", delivery_status)),
        output_dir=output_dir,
        frontdoor_manifest_path=frontdoor_manifest_path,
        frontdoor_index_html_path=frontdoor_index_html_path,
        current_delivery_index_html=str(current_frontdoor.get("current_delivery_index_html", "current_delivery/index.html")),
        latest_bundle_zip_path=output_dir / str(current_frontdoor.get("latest_bundle_zip", _LATEST_BUNDLE_ZIP_FILENAME)),
        latest_bundle_pointer_json_path=output_dir / str(current_frontdoor.get("latest_bundle_pointer_json", _LATEST_BUNDLE_POINTER_JSON_FILENAME)),
        latest_bundle_pointer_markdown_path=output_dir / str(current_frontdoor.get("latest_bundle_pointer_markdown", _LATEST_BUNDLE_POINTER_MARKDOWN_FILENAME)),
        quick_download_count=len(manifest_payload.get("quick_downloads") or []),
        download_group_count=len(manifest_payload.get("download_groups") or []),
        exact_full_scale_certified_status=exact_status,
        surface_alignment_status=(
            str(surface_alignment_payload.get("status", "")).strip() or None
        ),
        surface_alignment_check_count=(
            int(surface_alignment_payload.get("checked_check_count", 0) or 0)
            if surface_alignment_payload
            else None
        ),
        surface_alignment_drift_check_count=(
            int(surface_alignment_payload.get("drift_check_count", 0) or 0)
            if surface_alignment_payload
            else None
        ),
    )



def _build_frontdoor_manifest_payload(
    *,
    project_root: Path,
    output_dir: Path,
    landing_manifest_json_path: Path,
    landing_payload: Mapping[str, Any],
    latest_bundle_alias: _LatestBundleAliasBuild,
    script_entrypoints: _OptionalScriptEntrypointsRefs,
    surface_alignment: _OptionalSurfaceAlignmentRefs,
    surface_health: _OptionalSurfaceHealthRefs,
) -> dict[str, Any]:
    current_landing = _mapping(landing_payload.get("current_landing"))
    current_release = _mapping(landing_payload.get("current_release"))
    exact_payload = _mapping(landing_payload.get("exact_full_scale_certified"))
    # A non-allowlisted exact status fails closed here before projection.
    exact_status = normalize_non_authoritative_exact_status(
        exact_payload.get("status", "unknown"),
        context="landing_manifest.exact_full_scale_certified",
    )
    exact_note = str(exact_payload.get("note", ""))
    current_bundle_archive = _mapping(landing_payload.get("current_bundle_archive"))

    landing_dir = landing_manifest_json_path.parent.resolve()
    current_delivery_dir = _path_from_output_dir(output_dir, landing_dir)
    current_delivery_index_html = _join_relative(current_delivery_dir, "index.html")
    current_delivery_manifest_json = _join_relative(current_delivery_dir, landing_manifest_json_path.name)
    current_delivery_prefix = f"{current_delivery_dir.rstrip('/')}/" if current_delivery_dir else ""

    prefixed_actions = _prefix_action_hrefs(
        actions_raw=landing_payload.get("actions"),
        prefix=current_delivery_prefix,
    )
    prefixed_actions["open_current_delivery"] = current_delivery_index_html
    prefixed_actions["frontdoor_manifest_json"] = _FRONTDOOR_MANIFEST_FILENAME
    prefixed_actions["download_latest_bundle_zip"] = latest_bundle_alias.zip_relative_path
    prefixed_actions["latest_bundle_pointer_json"] = latest_bundle_alias.pointer_json_relative_path
    prefixed_actions["latest_bundle_pointer_markdown"] = latest_bundle_alias.pointer_markdown_relative_path
    if script_entrypoints.json_relative_path:
        prefixed_actions["active_entrypoints_json"] = script_entrypoints.json_relative_path
    if script_entrypoints.markdown_relative_path:
        prefixed_actions["active_entrypoints_markdown"] = script_entrypoints.markdown_relative_path
    if surface_alignment.json_relative_path:
        prefixed_actions["surface_alignment_summary_json"] = surface_alignment.json_relative_path
    if surface_alignment.markdown_relative_path:
        prefixed_actions["surface_alignment_summary_markdown"] = surface_alignment.markdown_relative_path
    if surface_alignment.console_relative_path:
        prefixed_actions["surface_alignment_summary_console"] = surface_alignment.console_relative_path
    if surface_health.json_relative_path:
        prefixed_actions["current_surface_health_json"] = surface_health.json_relative_path
    if surface_health.markdown_relative_path:
        prefixed_actions["current_surface_health_markdown"] = surface_health.markdown_relative_path
    if surface_health.console_relative_path:
        prefixed_actions["current_surface_health_console"] = surface_health.console_relative_path

    quick_downloads = _prefix_quick_downloads(
        quick_downloads_raw=landing_payload.get("quick_downloads"),
        prefix=current_delivery_prefix,
    )
    download_groups = _prefix_download_groups(
        download_groups_raw=landing_payload.get("download_groups"),
        prefix=current_delivery_prefix,
    )

    browse_first = _build_browse_first_mode(
        current_delivery_index_html=current_delivery_index_html,
        current_delivery_manifest_json=current_delivery_manifest_json,
        exact_payload=exact_payload,
        prefixed_actions=prefixed_actions,
        selected_facility_type_count=int(current_landing.get("selected_facility_type_count", 0) or 0),
        selected_pose_count=int(current_landing.get("selected_pose_count", 0) or 0),
    )
    download_first = _build_download_first_mode(
        current_landing=current_landing,
        current_bundle_archive=current_bundle_archive,
        latest_bundle_alias=latest_bundle_alias,
        prefixed_actions=prefixed_actions,
        quick_downloads=quick_downloads,
        download_groups=download_groups,
    )

    current_frontdoor = {
        "release_id": str(current_landing.get("release_id", current_release.get("release_id", "unknown_release"))),
        "base_id": str(current_landing.get("base_id", current_release.get("base_id", "unknown_base"))),
        "lot_size": int(current_landing.get("lot_size", current_release.get("lot_size", 0)) or 0),
        "delivery_status": str(current_landing.get("delivery_status", current_release.get("delivery_status", "unknown"))),
        "output_dir": _display_repo_path(project_root, output_dir),
        "frontdoor_index_html": _FRONTDOOR_INDEX_FILENAME,
        "frontdoor_manifest_json": _FRONTDOOR_MANIFEST_FILENAME,
        "current_delivery_dir": current_delivery_dir,
        "current_delivery_index_html": current_delivery_index_html,
        "current_delivery_landing_manifest_json": current_delivery_manifest_json,
        "viewer_index_html": str(prefixed_actions.get("open_viewer", "")),
        "viewer_manifest_json": str(prefixed_actions.get("viewer_manifest_json", "")),
        "current_bundle_zip": str(prefixed_actions.get("download_current_bundle_zip", "")),
        "current_bundle_pointer_json": str(prefixed_actions.get("current_bundle_pointer_json", "")),
        "current_bundle_pointer_markdown": str(prefixed_actions.get("current_bundle_pointer_markdown", "")),
        "latest_bundle_zip": latest_bundle_alias.zip_relative_path,
        "latest_bundle_pointer_json": latest_bundle_alias.pointer_json_relative_path,
        "latest_bundle_pointer_markdown": latest_bundle_alias.pointer_markdown_relative_path,
        "selected_facility_type_count": int(current_landing.get("selected_facility_type_count", 0) or 0),
        "selected_pose_count": int(current_landing.get("selected_pose_count", 0) or 0),
        "payload_download_count": int(current_landing.get("payload_download_count", 0) or 0),
        "metadata_download_count": int(current_landing.get("metadata_download_count", 0) or 0),
        "current_bundle_archive_sha256": str(current_bundle_archive.get("archive_sha256", "")),
        "current_bundle_archive_size_bytes": int(current_bundle_archive.get("archive_size_bytes", 0) or 0),
        "current_bundle_payload_file_count": int(current_bundle_archive.get("payload_file_count", 0) or 0),
        "current_bundle_metadata_file_count": int(current_bundle_archive.get("metadata_file_count", 0) or 0),
        "latest_bundle_archive_sha256": latest_bundle_alias.archive_sha256,
        "latest_bundle_archive_size_bytes": latest_bundle_alias.archive_size_bytes,
        "latest_bundle_payload_file_count": latest_bundle_alias.payload_file_count,
        "latest_bundle_metadata_file_count": latest_bundle_alias.metadata_file_count,
        "quick_download_count": len(quick_downloads),
        "download_group_count": len(download_groups),
        "scope_note": str(current_landing.get("scope_note", current_release.get("scope_note", ""))),
        "source_landing_manifest_json": _display_repo_path(project_root, landing_manifest_json_path),
        "source_current_bundle_zip": latest_bundle_alias.source_bundle_relative_path,
        "source_current_bundle_pointer_json": latest_bundle_alias.source_pointer_json_relative_path,
        "source_current_bundle_pointer_markdown": latest_bundle_alias.source_pointer_markdown_relative_path,
        "browse_primary_href": str(_mapping(browse_first.get("primary_action")).get("href", "")),
        "download_primary_href": str(_mapping(download_first.get("primary_action")).get("href", "")),
        "active_entrypoints_json": script_entrypoints.json_relative_path,
        "active_entrypoints_markdown": script_entrypoints.markdown_relative_path,
        "surface_alignment_summary_json": surface_alignment.json_relative_path,
        "surface_alignment_summary_markdown": surface_alignment.markdown_relative_path,
        "surface_alignment_summary_console": surface_alignment.console_relative_path,
        "surface_alignment_status": surface_alignment.status,
        "surface_alignment_check_count": surface_alignment.checked_check_count,
        "surface_alignment_drift_check_count": surface_alignment.drift_check_count,
        "current_surface_health_json": surface_health.json_relative_path,
        "current_surface_health_markdown": surface_health.markdown_relative_path,
        "current_surface_health_console": surface_health.console_relative_path,
        "surface_health_status": surface_health.status,
        "surface_health_summary_text": surface_health.summary_text,
        "surface_health_check_count": surface_health.checked_check_count,
        "surface_health_drift_check_count": surface_health.drift_check_count,
    }

    if surface_alignment.release_id and surface_alignment.release_id != current_frontdoor["release_id"]:
        raise SingleBaseDeliveryFrontdoorError(
            "surface-alignment summary release_id does not match the active frontdoor release id"
        )
    if (
        surface_alignment.delivery_status
        and surface_alignment.delivery_status != current_frontdoor["delivery_status"]
    ):
        raise SingleBaseDeliveryFrontdoorError(
            "surface-alignment summary delivery_status does not match the active frontdoor delivery status"
        )
    if surface_health.release_id and surface_health.release_id != current_frontdoor["release_id"]:
        raise SingleBaseDeliveryFrontdoorError(
            "current-surface-health release_id does not match the active frontdoor release id"
        )
    if (
        surface_health.delivery_status
        and surface_health.delivery_status != current_frontdoor["delivery_status"]
    ):
        raise SingleBaseDeliveryFrontdoorError(
            "current-surface-health delivery_status does not match the active frontdoor delivery status"
        )

    notes = [
        current_frontdoor["scope_note"],
        str(exact_payload.get("note", "")),
        (
            "This repo-front entry now mirrors the stable current-delivery ZIP under a shorter top-level latest alias. "
            "It still points forward to the same checked-in current_delivery bundle, does not duplicate the viewer assets, "
            "and does not widen the single-base contract."
        ),
    ]
    if surface_alignment.status:
        notes.append(
            "Current consumer-surface alignment audit status: "
            f"{surface_alignment.status}"
            + (
                f" ({surface_alignment.checked_check_count} checks / {surface_alignment.drift_check_count} drift)."
                if surface_alignment.checked_check_count is not None
                and surface_alignment.drift_check_count is not None
                else "."
            )
        )
    if surface_health.status:
        notes.append(
            "Current surface-health snapshot: "
            f"{surface_health.summary_text or surface_health.status}."
        )

    return {
        "metadata": {
            "schema_version": _FRONTDOOR_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "source": _FRONTDOOR_SOURCE,
        },
        "current_frontdoor": current_frontdoor,
        "current_release": {
            "release_id": current_frontdoor["release_id"],
            "base_id": current_frontdoor["base_id"],
            "lot_size": current_frontdoor["lot_size"],
            "delivery_status": current_frontdoor["delivery_status"],
            "release_dir": str(current_release.get("release_dir", "")),
            "scope_note": current_frontdoor["scope_note"],
        },
        "exact_full_scale_certified": {
            "status": exact_status,
            "note": exact_note,
        },
        "actions": prefixed_actions,
        "entry_modes": {
            "browse_first": browse_first,
            "download_first": download_first,
        },
        "quick_downloads": quick_downloads,
        "download_groups": download_groups,
        "latest_bundle_alias": {
            "bundle_zip": latest_bundle_alias.zip_relative_path,
            "pointer_json": latest_bundle_alias.pointer_json_relative_path,
            "pointer_markdown": latest_bundle_alias.pointer_markdown_relative_path,
            "archive_sha256": latest_bundle_alias.archive_sha256,
            "archive_size_bytes": latest_bundle_alias.archive_size_bytes,
            "payload_file_count": latest_bundle_alias.payload_file_count,
            "metadata_file_count": latest_bundle_alias.metadata_file_count,
            "included_entry_count": latest_bundle_alias.included_entry_count,
            "source_current_bundle_zip": latest_bundle_alias.source_bundle_relative_path,
            "source_current_bundle_pointer_json": latest_bundle_alias.source_pointer_json_relative_path,
            "source_current_bundle_pointer_markdown": latest_bundle_alias.source_pointer_markdown_relative_path,
        },
        "script_entrypoints": {
            "json": script_entrypoints.json_relative_path,
            "markdown": script_entrypoints.markdown_relative_path,
            "json_repo_path": script_entrypoints.json_repo_path,
            "markdown_repo_path": script_entrypoints.markdown_repo_path,
            "recommended_for_automation": bool(script_entrypoints.json_relative_path),
        },
        "surface_alignment": {
            "json": surface_alignment.json_relative_path,
            "markdown": surface_alignment.markdown_relative_path,
            "console": surface_alignment.console_relative_path,
            "json_repo_path": surface_alignment.json_repo_path,
            "markdown_repo_path": surface_alignment.markdown_repo_path,
            "console_repo_path": surface_alignment.console_repo_path,
            "status": surface_alignment.status,
            "checked_check_count": surface_alignment.checked_check_count,
            "clean_check_count": surface_alignment.clean_check_count,
            "drift_check_count": surface_alignment.drift_check_count,
            "helper_link_count": surface_alignment.helper_link_count,
            "helper_link_clean_count": surface_alignment.helper_link_clean_count,
            "release_id": surface_alignment.release_id,
            "delivery_status": surface_alignment.delivery_status,
        },
        "surface_health": {
            "json": surface_health.json_relative_path,
            "markdown": surface_health.markdown_relative_path,
            "console": surface_health.console_relative_path,
            "json_repo_path": surface_health.json_repo_path,
            "markdown_repo_path": surface_health.markdown_repo_path,
            "console_repo_path": surface_health.console_repo_path,
            "status": surface_health.status,
            "summary_text": surface_health.summary_text,
            "checked_check_count": surface_health.checked_check_count,
            "clean_check_count": surface_health.clean_check_count,
            "drift_check_count": surface_health.drift_check_count,
            "helper_link_count": surface_health.helper_link_count,
            "helper_link_clean_count": surface_health.helper_link_clean_count,
            "release_id": surface_health.release_id,
            "delivery_status": surface_health.delivery_status,
        },
        "notes": notes,
        "linked_assets": {
            "current_delivery_index_html": current_delivery_index_html,
            "current_delivery_landing_manifest_json": current_delivery_manifest_json,
            "current_bundle_zip": str(prefixed_actions.get("download_current_bundle_zip", "")),
            "latest_bundle_zip": latest_bundle_alias.zip_relative_path,
            "latest_bundle_pointer_json": latest_bundle_alias.pointer_json_relative_path,
            "active_entrypoints_json": script_entrypoints.json_relative_path,
            "active_entrypoints_markdown": script_entrypoints.markdown_relative_path,
            "surface_alignment_summary_json": surface_alignment.json_relative_path,
            "surface_alignment_summary_markdown": surface_alignment.markdown_relative_path,
            "surface_alignment_summary_console": surface_alignment.console_relative_path,
            "current_surface_health_json": surface_health.json_relative_path,
            "current_surface_health_markdown": surface_health.markdown_relative_path,
            "current_surface_health_console": surface_health.console_relative_path,
            "source_landing_manifest_json": current_frontdoor["source_landing_manifest_json"],
        },
    }



def _build_browse_first_mode(
    *,
    current_delivery_index_html: str,
    current_delivery_manifest_json: str,
    exact_payload: Mapping[str, Any],
    prefixed_actions: Mapping[str, str],
    selected_facility_type_count: int,
    selected_pose_count: int,
) -> dict[str, Any]:
    viewer_href = _require_action_href(
        prefixed_actions,
        "open_viewer",
        context="browse-first entry",
    )
    viewer_manifest_href = _require_action_href(
        prefixed_actions,
        "viewer_manifest_json",
        context="browse-first entry",
    )
    landing_manifest_href = _require_action_href(
        prefixed_actions,
        "landing_manifest_json",
        context="browse-first entry",
    )

    return {
        "mode_id": "browse_first",
        "title": "Browse first",
        "headline": "Inspect the active layout before downloading artifacts",
        "description": (
            "Open the interactive viewer or the stable current-delivery page if you "
            "want to inspect the active single-base release before pulling sidecars."
        ),
        "primary_action": _action_spec(
            action_id="open_viewer",
            label="Open interactive viewer",
            href=viewer_href,
        ),
        "secondary_actions": [
            _action_spec(
                action_id="open_current_delivery",
                label="Open current delivery page",
                href=current_delivery_index_html,
            ),
            _action_spec(
                action_id="viewer_manifest_json",
                label="Viewer manifest JSON",
                href=viewer_manifest_href,
            ),
            _action_spec(
                action_id="landing_manifest_json",
                label="Current delivery manifest",
                href=landing_manifest_href,
            ),
        ],
        "highlights": [
            {
                "label": "Viewer geometry",
                "value": f"{selected_facility_type_count} facility types / {selected_pose_count} poses",
            },
            {
                "label": "Stable entry",
                "value": current_delivery_index_html,
            },
            {
                "label": "Exact status",
                "value": str(exact_payload.get("status", "unknown")),
            },
        ],
    }



def _build_download_first_mode(
    *,
    current_landing: Mapping[str, Any],
    current_bundle_archive: Mapping[str, Any],
    latest_bundle_alias: _LatestBundleAliasBuild,
    prefixed_actions: Mapping[str, str],
    quick_downloads: Sequence[Mapping[str, Any]],
    download_groups: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    latest_bundle_zip_href = _require_action_href(
        prefixed_actions,
        "download_latest_bundle_zip",
        context="download-first entry",
    )
    latest_bundle_pointer_json_href = _require_action_href(
        prefixed_actions,
        "latest_bundle_pointer_json",
        context="download-first entry",
    )
    blueprint_href = _require_action_href(
        prefixed_actions,
        "blueprint",
        context="download-first entry",
    )
    validation_report_href = _require_action_href(
        prefixed_actions,
        "validation_report",
        context="download-first entry",
    )
    throughput_report_href = _require_action_href(
        prefixed_actions,
        "throughput_report",
        context="download-first entry",
    )
    run_summary_href = _require_action_href(
        prefixed_actions,
        "run_summary",
        context="download-first entry",
    )
    release_manifest_href = _require_action_href(
        prefixed_actions,
        "release_manifest_json",
        context="download-first entry",
    )
    sha256sums_href = _require_action_href(
        prefixed_actions,
        "sha256sums",
        context="download-first entry",
    )
    _require_quick_download_id(quick_downloads, "industrial_planner_blueprint")
    _require_download_group_id(download_groups, "metadata")

    current_bundle_payload_file_count = int(current_bundle_archive.get("payload_file_count", 0) or 0)
    current_bundle_metadata_file_count = int(current_bundle_archive.get("metadata_file_count", 0) or 0)
    current_bundle_archive_size_bytes = int(current_bundle_archive.get("archive_size_bytes", 0) or 0)
    payload_download_count = int(current_landing.get("payload_download_count", 0) or 0)
    metadata_download_count = int(current_landing.get("metadata_download_count", 0) or 0)
    quick_download_count = int(current_landing.get("quick_download_count", len(quick_downloads)) or 0)
    download_group_count = int(current_landing.get("download_group_count", len(download_groups)) or 0)

    return {
        "mode_id": "download_first",
        "title": "Download first",
        "headline": "Grab the current delivery artifacts without hunting through directories",
        "description": (
            "Use the repo-front page as a download-oriented entry when you already know "
            "you want the blueprint, verification sidecars, and release metadata. The "
            "primary action now points at a shorter checked-in latest ZIP alias instead "
            "of making script consumers remember current_delivery/downloads/."
        ),
        "primary_action": _action_spec(
            action_id="download_latest_bundle_zip",
            label="Download latest bundle ZIP",
            href=latest_bundle_zip_href,
        ),
        "secondary_actions": [
            _action_spec(
                action_id="latest_bundle_pointer_json",
                label="Latest bundle pointer JSON",
                href=latest_bundle_pointer_json_href,
            ),
            _action_spec(
                action_id="validation_report",
                label="Validation report JSON",
                href=validation_report_href,
            ),
            _action_spec(
                action_id="throughput_report",
                label="Throughput report JSON",
                href=throughput_report_href,
            ),
            _action_spec(
                action_id="blueprint",
                label="Blueprint JSON",
                href=blueprint_href,
            ),
            _action_spec(
                action_id="release_manifest_json",
                label="Release manifest JSON",
                href=release_manifest_href,
            ),
            _action_spec(
                action_id="sha256sums",
                label="SHA256SUMS",
                href=sha256sums_href,
            ),
            _action_spec(
                action_id="run_summary",
                label="Run summary JSON",
                href=run_summary_href,
            ),
        ],
        "highlights": [
            {
                "label": "Latest alias",
                "value": latest_bundle_alias.zip_relative_path,
            },
            {
                "label": "Bundle ZIP",
                "value": _format_size_bytes(current_bundle_archive_size_bytes),
            },
            {
                "label": "Included files",
                "value": f"{current_bundle_payload_file_count} payload / {current_bundle_metadata_file_count} metadata",
            },
            {
                "label": "Surface",
                "value": f"{payload_download_count} payload · {metadata_download_count} metadata · {quick_download_count} quick / {download_group_count} grouped",
            },
        ],
    }



def _action_spec(*, action_id: str, label: str, href: str) -> dict[str, str]:
    return {
        "action_id": action_id,
        "label": label,
        "href": href,
    }



def _require_action_href(actions: Mapping[str, str], key: str, *, context: str) -> str:
    href = str(actions.get(key, "")).strip()
    if not href:
        raise SingleBaseDeliveryFrontdoorError(
            f"{context} requires actions.{key} to be present in the landing manifest"
        )
    return href



def _require_quick_download_id(quick_downloads: Sequence[Mapping[str, Any]], quick_download_id: str) -> None:
    if any(str(entry.get("id", "")).strip() == quick_download_id for entry in quick_downloads if isinstance(entry, Mapping)):
        return
    raise SingleBaseDeliveryFrontdoorError(
        f"download-first entry requires quick_downloads entry {quick_download_id!r}"
    )



def _require_download_group_id(download_groups: Sequence[Mapping[str, Any]], group_id: str) -> None:
    if any(str(group.get("group_id", "")).strip() == group_id for group in download_groups if isinstance(group, Mapping)):
        return
    raise SingleBaseDeliveryFrontdoorError(
        f"frontdoor build requires download_groups entry {group_id!r}"
    )


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



def _resolve_optional_script_entrypoints_refs(
    *,
    project_root: Path,
    output_dir: Path,
    entrypoints_json_path: Path | None,
    entrypoints_markdown_path: Path | None,
    require_entrypoints: bool,
) -> _OptionalScriptEntrypointsRefs:
    resolved_json_path = _resolve_optional_entrypoints_path(
        project_root=project_root,
        output_dir=output_dir,
        path=entrypoints_json_path,
        default_filename=_ENTRYPOINTS_JSON_FILENAME,
    )
    resolved_markdown_path = _resolve_optional_entrypoints_path(
        project_root=project_root,
        output_dir=output_dir,
        path=entrypoints_markdown_path,
        default_filename=_ENTRYPOINTS_MARKDOWN_FILENAME,
    )

    json_relative_path = _maybe_relative_href_from_output_dir(output_dir, resolved_json_path)
    markdown_relative_path = _maybe_relative_href_from_output_dir(output_dir, resolved_markdown_path)

    if require_entrypoints and (not json_relative_path or not markdown_relative_path):
        raise SingleBaseDeliveryFrontdoorError(
            "frontdoor helper links require active entrypoints JSON and Markdown to exist"
        )

    return _OptionalScriptEntrypointsRefs(
        json_relative_path=json_relative_path,
        markdown_relative_path=markdown_relative_path,
        json_repo_path=_display_repo_path(project_root, resolved_json_path) if json_relative_path else None,
        markdown_repo_path=_display_repo_path(project_root, resolved_markdown_path) if markdown_relative_path else None,
    )



def _resolve_optional_surface_alignment_refs(
    *,
    project_root: Path,
    output_dir: Path,
    json_path: Path | None,
    markdown_path: Path | None,
    console_path: Path | None,
    require_surface_alignment: bool,
) -> _OptionalSurfaceAlignmentRefs:
    resolved_json_path = _resolve_optional_entrypoints_path(
        project_root=project_root,
        output_dir=output_dir,
        path=json_path,
        default_filename=_SURFACE_ALIGNMENT_JSON_FILENAME,
    )
    resolved_markdown_path = _resolve_optional_entrypoints_path(
        project_root=project_root,
        output_dir=output_dir,
        path=markdown_path,
        default_filename=_SURFACE_ALIGNMENT_MARKDOWN_FILENAME,
    )
    resolved_console_path = _resolve_optional_entrypoints_path(
        project_root=project_root,
        output_dir=output_dir,
        path=console_path,
        default_filename=_SURFACE_ALIGNMENT_CONSOLE_FILENAME,
    )

    json_relative_path = _maybe_relative_href_from_output_dir(output_dir, resolved_json_path)
    markdown_relative_path = _maybe_relative_href_from_output_dir(output_dir, resolved_markdown_path)
    console_relative_path = _maybe_relative_href_from_output_dir(output_dir, resolved_console_path)

    if require_surface_alignment and (
        not json_relative_path or not markdown_relative_path or not console_relative_path
    ):
        raise SingleBaseDeliveryFrontdoorError(
            "frontdoor helper links require surface-alignment JSON/Markdown/TXT summaries to exist"
        )

    summary_payload: Mapping[str, Any] = {}
    summary = {}
    active_contract = {}
    if json_relative_path:
        summary_payload = load_json_mapping(resolved_json_path)
        summary = _mapping(summary_payload.get("summary"))
        active_contract = _mapping(summary_payload.get("active_contract"))

    return _OptionalSurfaceAlignmentRefs(
        json_relative_path=json_relative_path,
        markdown_relative_path=markdown_relative_path,
        console_relative_path=console_relative_path,
        json_repo_path=_display_repo_path(project_root, resolved_json_path) if json_relative_path else None,
        markdown_repo_path=(
            _display_repo_path(project_root, resolved_markdown_path) if markdown_relative_path else None
        ),
        console_repo_path=(
            _display_repo_path(project_root, resolved_console_path) if console_relative_path else None
        ),
        status=str(summary.get("status", "")).strip() or None,
        checked_check_count=(
            int(summary.get("checked_check_count", 0) or 0) if summary else None
        ),
        clean_check_count=(
            int(summary.get("clean_check_count", 0) or 0) if summary else None
        ),
        drift_check_count=(
            int(summary.get("drift_check_count", 0) or 0) if summary else None
        ),
        helper_link_count=(
            int(summary.get("helper_link_count", 0) or 0) if summary else None
        ),
        helper_link_clean_count=(
            int(summary.get("helper_link_clean_count", 0) or 0) if summary else None
        ),
        release_id=str(active_contract.get("release_id", "")).strip() or None,
        delivery_status=str(active_contract.get("delivery_status", "")).strip() or None,
    )



def _resolve_optional_surface_health_refs(
    *,
    project_root: Path,
    output_dir: Path,
    json_path: Path | None,
    markdown_path: Path | None,
    console_path: Path | None,
    require_surface_health: bool,
) -> _OptionalSurfaceHealthRefs:
    resolved_json_path = _resolve_optional_entrypoints_path(
        project_root=project_root,
        output_dir=output_dir,
        path=json_path,
        default_filename=_SURFACE_HEALTH_JSON_FILENAME,
    )
    resolved_markdown_path = _resolve_optional_entrypoints_path(
        project_root=project_root,
        output_dir=output_dir,
        path=markdown_path,
        default_filename=_SURFACE_HEALTH_MARKDOWN_FILENAME,
    )
    resolved_console_path = _resolve_optional_entrypoints_path(
        project_root=project_root,
        output_dir=output_dir,
        path=console_path,
        default_filename=_SURFACE_HEALTH_CONSOLE_FILENAME,
    )

    json_relative_path = _maybe_relative_href_from_output_dir(output_dir, resolved_json_path)
    markdown_relative_path = _maybe_relative_href_from_output_dir(output_dir, resolved_markdown_path)
    console_relative_path = _maybe_relative_href_from_output_dir(output_dir, resolved_console_path)

    if require_surface_health and (
        not json_relative_path or not markdown_relative_path or not console_relative_path
    ):
        raise SingleBaseDeliveryFrontdoorError(
            "frontdoor helper links require current-surface-health JSON/Markdown/TXT snapshots to exist"
        )

    payload: Mapping[str, Any] = {}
    surface_health = {}
    active_contract = {}
    if json_relative_path:
        payload = load_json_mapping(resolved_json_path)
        surface_health = _mapping(payload.get("surface_health"))
        active_contract = _mapping(payload.get("active_contract"))

    return _OptionalSurfaceHealthRefs(
        json_relative_path=json_relative_path,
        markdown_relative_path=markdown_relative_path,
        console_relative_path=console_relative_path,
        json_repo_path=_display_repo_path(project_root, resolved_json_path) if json_relative_path else None,
        markdown_repo_path=(
            _display_repo_path(project_root, resolved_markdown_path) if markdown_relative_path else None
        ),
        console_repo_path=(
            _display_repo_path(project_root, resolved_console_path) if console_relative_path else None
        ),
        status=str(surface_health.get("status", "")).strip() or None,
        summary_text=str(surface_health.get("summary_text", "")).strip() or None,
        checked_check_count=(
            int(surface_health.get("checked_check_count", 0) or 0) if surface_health else None
        ),
        clean_check_count=(
            int(surface_health.get("clean_check_count", 0) or 0) if surface_health else None
        ),
        drift_check_count=(
            int(surface_health.get("drift_check_count", 0) or 0) if surface_health else None
        ),
        helper_link_count=(
            int(surface_health.get("helper_link_count", 0) or 0) if surface_health else None
        ),
        helper_link_clean_count=(
            int(surface_health.get("helper_link_clean_count", 0) or 0) if surface_health else None
        ),
        release_id=str(active_contract.get("release_id", "")).strip() or None,
        delivery_status=str(active_contract.get("delivery_status", "")).strip() or None,
    )



def _resolve_optional_entrypoints_path(
    *,
    project_root: Path,
    output_dir: Path,
    path: Path | None,
    default_filename: str,
) -> Path:
    candidate = Path(path) if path is not None else (output_dir / default_filename)
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()



def _maybe_relative_href_from_output_dir(output_dir: Path, candidate: Path) -> str | None:
    if not candidate.is_file():
        return None
    return os.path.relpath(candidate, output_dir).replace(os.sep, "/")



def _prefix_action_hrefs(*, actions_raw: Any, prefix: str) -> dict[str, str]:
    if not isinstance(actions_raw, Mapping):
        return {}
    prefixed: dict[str, str] = {}
    for key, value in actions_raw.items():
        href = str(value).strip()
        if not href:
            continue
        prefixed[str(key)] = f"{prefix}{href}"
    return prefixed



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



def _materialize_latest_bundle_alias(
    *,
    project_root: Path,
    output_dir: Path,
    landing_manifest_json_path: Path,
    landing_payload: Mapping[str, Any],
) -> _LatestBundleAliasBuild:
    current_landing = _mapping(landing_payload.get("current_landing"))
    current_release = _mapping(landing_payload.get("current_release"))
    exact_payload = _mapping(landing_payload.get("exact_full_scale_certified"))
    # Validation-only here: a non-allowlisted exact status must fail closed
    # before the alias bundle is built; the payload projection happens in
    # _build_latest_bundle_pointer_payload.
    normalize_non_authoritative_exact_status(
        exact_payload.get("status", "unknown"),
        context="landing_manifest.exact_full_scale_certified",
    )
    current_bundle_archive = _mapping(landing_payload.get("current_bundle_archive"))
    actions = _mapping(landing_payload.get("actions"))

    landing_dir = landing_manifest_json_path.parent.resolve()
    current_delivery_dir = _path_from_output_dir(output_dir, landing_dir)

    source_zip_relative = _require_action_href(
        actions,
        "download_current_bundle_zip",
        context="frontdoor latest-bundle alias",
    )
    source_pointer_json_relative = _require_action_href(
        actions,
        "current_bundle_pointer_json",
        context="frontdoor latest-bundle alias",
    )
    source_pointer_markdown_relative = _require_action_href(
        actions,
        "current_bundle_pointer_markdown",
        context="frontdoor latest-bundle alias",
    )

    source_zip_path = (landing_dir / source_zip_relative).resolve()
    source_pointer_json_path = (landing_dir / source_pointer_json_relative).resolve()
    source_pointer_markdown_path = (landing_dir / source_pointer_markdown_relative).resolve()
    if not source_zip_path.is_file():
        raise SingleBaseDeliveryFrontdoorError(
            f"frontdoor latest-bundle alias source ZIP is missing: {source_zip_path}"
        )
    if not source_pointer_json_path.is_file():
        raise SingleBaseDeliveryFrontdoorError(
            f"frontdoor latest-bundle alias source pointer JSON is missing: {source_pointer_json_path}"
        )
    if not source_pointer_markdown_path.is_file():
        raise SingleBaseDeliveryFrontdoorError(
            f"frontdoor latest-bundle alias source pointer Markdown is missing: {source_pointer_markdown_path}"
        )

    source_bundle_display = _join_relative(current_delivery_dir, source_zip_relative)
    source_pointer_json_display = _join_relative(current_delivery_dir, source_pointer_json_relative)
    source_pointer_markdown_display = _join_relative(current_delivery_dir, source_pointer_markdown_relative)

    zip_path = output_dir / _LATEST_BUNDLE_ZIP_FILENAME
    pointer_json_path = output_dir / _LATEST_BUNDLE_POINTER_JSON_FILENAME
    pointer_markdown_path = output_dir / _LATEST_BUNDLE_POINTER_MARKDOWN_FILENAME

    _atomic_copy_binary(source_zip_path, zip_path)

    pointer_payload = _build_latest_bundle_pointer_payload(
        project_root=project_root,
        landing_manifest_json_path=landing_manifest_json_path,
        current_landing=current_landing,
        current_release=current_release,
        exact_payload=exact_payload,
        current_bundle_archive=current_bundle_archive,
        archive_size_bytes=int(zip_path.stat().st_size),
        archive_sha256=(
            str(current_bundle_archive.get("archive_sha256", "")).strip()
            or sha256_file(zip_path)
        ),
        source_bundle_relative_path=source_bundle_display,
        source_pointer_json_relative_path=source_pointer_json_display,
        source_pointer_markdown_relative_path=source_pointer_markdown_display,
    )
    atomic_write_json(pointer_json_path, pointer_payload)
    _atomic_write_text(pointer_markdown_path, _render_latest_bundle_pointer_markdown(pointer_payload))

    current_bundle = _mapping(pointer_payload.get("current_bundle"))
    return _LatestBundleAliasBuild(
        zip_path=zip_path,
        pointer_json_path=pointer_json_path,
        pointer_markdown_path=pointer_markdown_path,
        zip_relative_path=_LATEST_BUNDLE_ZIP_FILENAME,
        pointer_json_relative_path=_LATEST_BUNDLE_POINTER_JSON_FILENAME,
        pointer_markdown_relative_path=_LATEST_BUNDLE_POINTER_MARKDOWN_FILENAME,
        archive_sha256=str(current_bundle.get("archive_sha256", "")),
        archive_size_bytes=int(current_bundle.get("archive_size_bytes", 0) or 0),
        payload_file_count=int(current_bundle.get("payload_file_count", 0) or 0),
        metadata_file_count=int(current_bundle.get("metadata_file_count", 0) or 0),
        included_entry_count=int(current_bundle.get("included_entry_count", 0) or 0),
        source_bundle_relative_path=source_bundle_display,
        source_pointer_json_relative_path=source_pointer_json_display,
        source_pointer_markdown_relative_path=source_pointer_markdown_display,
    )


def _build_latest_bundle_pointer_payload(
    *,
    project_root: Path,
    landing_manifest_json_path: Path,
    current_landing: Mapping[str, Any],
    current_release: Mapping[str, Any],
    exact_payload: Mapping[str, Any],
    current_bundle_archive: Mapping[str, Any],
    archive_size_bytes: int,
    archive_sha256: str,
    source_bundle_relative_path: str,
    source_pointer_json_relative_path: str,
    source_pointer_markdown_relative_path: str,
) -> dict[str, Any]:
    release_id = str(current_landing.get("release_id", current_release.get("release_id", "unknown_release")))
    base_id = str(current_landing.get("base_id", current_release.get("base_id", "unknown_base")))
    lot_size = int(current_landing.get("lot_size", current_release.get("lot_size", 0)) or 0)
    delivery_status = str(current_landing.get("delivery_status", current_release.get("delivery_status", "unknown")))
    scope_note = str(current_landing.get("scope_note", current_release.get("scope_note", "")))
    payload_file_count = int(current_bundle_archive.get("payload_file_count", 0) or 0)
    metadata_file_count = int(current_bundle_archive.get("metadata_file_count", 0) or 0)
    included_entry_count = int(current_bundle_archive.get("included_entry_count", payload_file_count + metadata_file_count) or 0)
    archive_root = str(current_bundle_archive.get("archive_root", "industrial_planner_current_single_base_delivery_bundle"))
    # V92: a non-allowlisted exact status fails closed before projection.
    exact_status = normalize_non_authoritative_exact_status(
        exact_payload.get("status", "unknown"),
        context="landing_manifest.exact_full_scale_certified",
    )
    exact_note = str(exact_payload.get("note", ""))

    return {
        "metadata": {
            "schema_version": _LATEST_BUNDLE_POINTER_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "source": _LATEST_BUNDLE_POINTER_SOURCE,
        },
        "current_bundle": {
            "release_id": release_id,
            "base_id": base_id,
            "lot_size": lot_size,
            "delivery_status": delivery_status,
            "bundle_zip": _LATEST_BUNDLE_ZIP_FILENAME,
            "pointer_json": _LATEST_BUNDLE_POINTER_JSON_FILENAME,
            "pointer_markdown": _LATEST_BUNDLE_POINTER_MARKDOWN_FILENAME,
            "archive_root": archive_root,
            "archive_sha256": archive_sha256,
            "archive_size_bytes": archive_size_bytes,
            "payload_file_count": payload_file_count,
            "metadata_file_count": metadata_file_count,
            "included_entry_count": included_entry_count,
            "source_current_bundle_zip": source_bundle_relative_path,
            "source_current_bundle_pointer_json": source_pointer_json_relative_path,
            "source_current_bundle_pointer_markdown": source_pointer_markdown_relative_path,
            "scope_note": scope_note,
        },
        "exact_full_scale_certified": {
            "status": exact_status,
            "note": exact_note,
        },
        "included_roots": {
            "release": (Path(archive_root) / "release").as_posix(),
            "meta": (Path(archive_root) / "meta").as_posix(),
        },
        "source_inputs": {
            "source_landing_manifest_json": _display_repo_path(project_root, landing_manifest_json_path),
            "source_current_bundle_zip": source_bundle_relative_path,
            "source_current_bundle_pointer_json": source_pointer_json_relative_path,
            "source_current_bundle_pointer_markdown": source_pointer_markdown_relative_path,
        },
        "notes": [
            scope_note,
            exact_note,
            (
                "This repo-front latest alias mirrors the stable current-delivery bundle under a shorter checked-in path, "
                "so script consumers can fetch the active single-base payload + metadata ZIP without remembering "
                "the current_delivery/downloads/ layout."
            ),
        ],
    }


def _render_latest_bundle_pointer_markdown(payload: Mapping[str, Any]) -> str:
    current_bundle = _mapping(payload.get("current_bundle"))
    exact_payload = _mapping(payload.get("exact_full_scale_certified"))
    notes = [str(note) for note in (payload.get("notes") or []) if str(note).strip()]

    lines = [
        "# Latest Single-Base Delivery Bundle ZIP Alias",
        "",
        f"- Release id: `{current_bundle.get('release_id', '')}`",
        f"- Base id: `{current_bundle.get('base_id', '')}`",
        f"- Lot size: `{current_bundle.get('lot_size', '')}`",
        f"- Delivery status: `{current_bundle.get('delivery_status', '')}`",
        f"- Bundle ZIP: `{current_bundle.get('bundle_zip', '')}`",
        f"- Pointer JSON: `{current_bundle.get('pointer_json', '')}`",
        f"- Source current bundle ZIP: `{current_bundle.get('source_current_bundle_zip', '')}`",
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



def _render_frontdoor_html(payload: Mapping[str, Any]) -> str:
    current = _mapping(payload.get("current_frontdoor"))
    exact_payload = _mapping(payload.get("exact_full_scale_certified"))
    entry_modes = _mapping(payload.get("entry_modes"))
    script_entrypoints = _mapping(payload.get("script_entrypoints"))
    surface_alignment = _mapping(payload.get("surface_alignment"))
    surface_health = _mapping(payload.get("surface_health"))
    browse_mode = _mapping(entry_modes.get("browse_first"))
    download_mode = _mapping(entry_modes.get("download_first"))
    quick_downloads = list(payload.get("quick_downloads") or [])
    download_groups = list(payload.get("download_groups") or [])
    notes = [str(note) for note in (payload.get("notes") or []) if str(note).strip()]

    helper_links = [
        _render_action_link("Active entrypoints JSON", script_entrypoints.get("json")),
        _render_action_link("Active entrypoints Markdown", script_entrypoints.get("markdown")),
        _render_action_link("Current surface health JSON", surface_health.get("json")),
        _render_action_link("Current surface health Markdown", surface_health.get("markdown")),
        _render_action_link("Current surface health console", surface_health.get("console")),
        _render_action_link("Surface alignment JSON", surface_alignment.get("json")),
        _render_action_link("Surface alignment Markdown", surface_alignment.get("markdown")),
        _render_action_link("Surface alignment console", surface_alignment.get("console")),
        _render_action_link("Frontdoor manifest JSON", current.get("frontdoor_manifest_json")),
        _render_action_link("Latest bundle pointer JSON", current.get("latest_bundle_pointer_json")),
        _render_action_link("Current delivery manifest", current.get("current_delivery_landing_manifest_json")),
        _render_action_link("Viewer manifest JSON", current.get("viewer_manifest_json")),
    ]
    helper_links_html = "\n".join(link for link in helper_links if link)

    quick_cards_html = "\n".join(_render_quick_download_card(entry) for entry in quick_downloads if isinstance(entry, Mapping))
    groups_html = "\n".join(_render_download_group(group) for group in download_groups if isinstance(group, Mapping))
    notes_html = "\n".join(f"<li>{_escape(note)}</li>" for note in notes)
    surface_alignment_status = str(surface_alignment.get("status", "")).strip() or "not_published"
    if surface_alignment.get("checked_check_count") is not None and surface_alignment.get("drift_check_count") is not None:
        surface_alignment_summary = (
            f"{surface_alignment.get('checked_check_count', 0)} checks / "
            f"{surface_alignment.get('drift_check_count', 0)} drift"
        )
    else:
        surface_alignment_summary = "summary not linked"
    surface_health_status = str(surface_health.get("status", "")).strip() or "not_published"
    surface_health_summary = str(surface_health.get("summary_text", "")).strip() or "snapshot not linked"

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
<title>IndustrialPlanner Active Single-Base Front Door</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #0d1117; color: #e6edf3; font-family: \"Segoe UI\", system-ui, sans-serif; }}
a {{ color: #58a6ff; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.page {{ max-width: 1220px; margin: 0 auto; padding: 28px 20px 48px; }}
.hero {{ background: linear-gradient(180deg, rgba(88,166,255,0.14), rgba(13,17,23,0.92)); border: 1px solid #30363d; border-radius: 22px; padding: 24px; margin-bottom: 18px; }}
.eyebrow {{ color: #8b949e; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 10px; }}
h1 {{ margin: 0 0 10px; font-size: 30px; }}
.lead {{ color: #c9d1d9; line-height: 1.65; max-width: 960px; }}
.helper-links {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }}
.button {{ display: inline-flex; align-items: center; justify-content: center; border: 1px solid #30363d; border-radius: 999px; padding: 10px 14px; background: #161b22; font-size: 14px; }}
.button.primary {{ background: #1f6feb; border-color: #1f6feb; color: #ffffff; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin: 18px 0; }}
.mode-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 14px; margin-top: 18px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 16px; padding: 16px; }}
.mode-card {{ background: rgba(22,27,34,0.96); border: 1px solid #30363d; border-radius: 18px; padding: 18px; }}
.mode-card.download {{ border-color: #1f6feb; box-shadow: inset 0 0 0 1px rgba(31,111,235,0.22); }}
.mode-eyebrow {{ color: #8b949e; font-size: 12px; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; }}
.mode-title {{ font-size: 22px; font-weight: 700; margin: 0 0 8px; }}
.mode-headline {{ font-size: 16px; font-weight: 600; margin: 0 0 10px; color: #c9d1d9; }}
.mode-description {{ color: #8b949e; line-height: 1.6; margin-bottom: 14px; }}
.mode-actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }}
.mode-highlights {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
.highlight {{ border: 1px solid #21262d; border-radius: 12px; padding: 10px 12px; background: rgba(13,17,23,0.55); }}
.highlight .label {{ color: #8b949e; font-size: 12px; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 4px; }}
.highlight .value {{ font-size: 14px; font-weight: 600; line-height: 1.5; }}
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
    <div class=\"eyebrow\">IndustrialPlanner · repo front door</div>
    <h1>{_escape(current.get('base_id', 'unknown_base'))} · {current.get('lot_size', '')}×{current.get('lot_size', '')}</h1>
    <p class=\"lead\">This checked-in homepage is now split into two explicit entry paths. Use <strong>Browse first</strong> when you want to inspect the active single-base layout in the viewer, or use <strong>Download first</strong> when you already know you want one stable ZIP for the current blueprint, verification sidecars, and release metadata. Both paths still stay inside the active <code>valley4_protocol_core</code> 70×70 contract and forward into the stable <code>{_escape(current.get('current_delivery_dir', 'current_delivery'))}/</code> bundle.</p>
    <div class=\"helper-links\">{helper_links_html}</div>
    <p class=\"muted\" style=\"margin-top:14px;\">Automation tip: prefer <code>{_escape(str(script_entrypoints.get('json', 'active_single_base_delivery_entrypoints.json')))}</code> when you want one machine-readable file that already aligns the current release, viewer, landing, and latest-bundle surfaces.</p>

    <div class=\"mode-grid\">
      {_render_entry_mode_card(browse_mode, variant='browse')}
      {_render_entry_mode_card(download_mode, variant='download')}
    </div>
  </section>

  <section class=\"grid\">
    <div class=\"card\"><div class=\"kicker\">Release id</div><div class=\"value\">{_escape(current.get('release_id', ''))}</div></div>
    <div class=\"card\"><div class=\"kicker\">Delivery status</div><div class=\"value\">{_escape(current.get('delivery_status', ''))}</div></div>
    <div class=\"card\"><div class=\"kicker\">Viewer geometry</div><div class=\"value\">{current.get('selected_facility_type_count', 0)} / {current.get('selected_pose_count', 0)}</div><div class=\"muted\">facility types / selected poses</div></div>
    <div class=\"card\"><div class=\"kicker\">Download surface</div><div class=\"value\">{current.get('quick_download_count', 0)} / {current.get('download_group_count', 0)}</div><div class=\"muted\">quick downloads / grouped sections</div></div>
    <div class=\"card\"><div class=\"kicker\">Surface health</div><div class=\"value\">{_escape(surface_health_status)}</div><div class=\"muted\">{_escape(surface_health_summary)}</div></div>
    <div class=\"card\"><div class=\"kicker\">Surface audit</div><div class=\"value\">{_escape(surface_alignment_status)}</div><div class=\"muted\">{_escape(surface_alignment_summary)}</div></div>
  </section>

  <section class=\"panel\" id=\"browse-first\">
    <h2>Browse-first path</h2>
    <p class=\"muted\"><span class=\"badge\">entry</span>stable current delivery page: <code>{_escape(current.get('current_delivery_index_html', 'current_delivery/index.html'))}</code></p>
    <p class=\"muted\" style=\"margin-top:10px;\"><span class=\"badge\">scope</span>{_escape(current.get('scope_note', ''))}</p>
    <p class=\"muted\" style=\"margin-top:10px;\"><span class=\"badge\">exact</span>full-scale 70×70 exact <code>CERTIFIED</code> status: <strong>{_escape(exact_payload.get('status', 'unknown'))}</strong>. {_escape(exact_payload.get('note', ''))}</p>
  </section>

  <section class=\"panel\" id=\"download-first\">
    <h2>Download-first essentials (individual files after the ZIP alias)</h2>
    <div class=\"quick-grid\">{quick_cards_html}</div>
  </section>

  <section class=\"panel\" id=\"download-groups\">
    <h2>Grouped downloads</h2>
    {groups_html}
  </section>

  <section class=\"panel\" id=\"surface-health\">
    <h2>Current surface health snapshot</h2>
    <p class=\"muted\"><span class=\"badge\">status</span><strong>{_escape(surface_health_status)}</strong></p>
    <p class=\"muted\" style=\"margin-top:10px;\"><span class=\"badge\">summary</span>{_escape(surface_health_summary)}</p>
    <p class=\"muted\" style=\"margin-top:10px;\">Use the compact JSON/Markdown/TXT snapshot when you only need the current clean/drift verdict and top-line counts without opening the full no-drift audit report.</p>
  </section>

  <section class=\"panel\" id=\"surface-alignment\">
    <h2>Current consumer-surface audit</h2>
    <p class=\"muted\"><span class=\"badge\">status</span><strong>{_escape(surface_alignment_status)}</strong></p>
    <p class=\"muted\" style=\"margin-top:10px;\"><span class=\"badge\">summary</span>{_escape(surface_alignment_summary)}</p>
    <p class=\"muted\" style=\"margin-top:10px;\">Use the linked JSON for automation and the Markdown/TXT summaries for quick reviewer-facing checks when you want to confirm that the repo-front helper links and the aggregate entrypoints manifest are still aligned.</p>
  </section>

  <section class=\"panel\">
    <h2>What this front door adds</h2>
    <ul>
      <li><code>{_escape(current.get('frontdoor_index_html', 'index.html'))}</code> — this higher-level repo entry page with explicit browse-first and download-first paths</li>
      <li><code>{_escape(current.get('frontdoor_manifest_json', 'frontdoor_manifest.json'))}</code> — machine-readable frontdoor summary, including dual entry-mode metadata</li>
      <li><code>{_escape(str(script_entrypoints.get('json', 'active_single_base_delivery_entrypoints.json')))}</code> — aggregate current-entrypoints manifest for script consumers that want one aligned file</li>
      <li><code>{_escape(str(surface_health.get('json', 'current_surface_health.json')))}</code> — compact current-surface snapshot for reviewers and CI consumers that only need the clean/drift verdict plus top-line counts</li>
      <li><code>{_escape(str(surface_alignment.get('json', '.artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json')))}</code> — no-drift audit summary for the checked-in consumer surface, so reviewers can immediately see whether the current entry layer is clean</li>
      <li><code>{_escape(current.get('latest_bundle_zip', _LATEST_BUNDLE_ZIP_FILENAME))}</code> — shorter top-level latest ZIP alias for the active single-base delivery bundle</li>
      <li><code>{_escape(current.get('latest_bundle_pointer_json', _LATEST_BUNDLE_POINTER_JSON_FILENAME))}</code> — machine-readable latest-bundle pointer for script consumers</li>
      <li><code>{_escape(current.get('current_delivery_dir', 'current_delivery'))}/</code> — stable current-delivery bundle with its own landing page, copied viewer assets, and the source ZIP alias under <code>downloads/</code></li>
      <li>Source landing manifest used for this page: <code>{_escape(current.get('source_landing_manifest_json', ''))}</code></li>
    </ul>
  </section>

  <section class=\"panel\">
    <h2>Current notes</h2>
    <ul>{notes_html}</ul>
  </section>

  <footer>
    Generated from the checked-in current delivery landing bundle for the active <code>valley4_protocol_core</code> 70×70 line. This front door is intentionally narrower than a future multi-base portal, keeps other bases as <code>future_scope</code>, and does not claim the full exact solver end-state has already been certified.
  </footer>
</div>
</body>
</html>
"""



def _render_entry_mode_card(mode: Mapping[str, Any], *, variant: str) -> str:
    primary_action = _mapping(mode.get("primary_action"))
    secondary_actions = [
        _mapping(action)
        for action in (mode.get("secondary_actions") or [])
        if isinstance(action, Mapping)
    ]
    highlights = [
        _mapping(highlight)
        for highlight in (mode.get("highlights") or [])
        if isinstance(highlight, Mapping)
    ]
    secondary_html = "\n".join(
        _render_action_link(
            str(action.get("label", "open")),
            action.get("href"),
        )
        for action in secondary_actions
    )
    highlights_html = "\n".join(
        (
            '<div class="highlight">'
            f'<div class="label">{_escape(highlight.get("label", ""))}</div>'
            f'<div class="value">{_escape(highlight.get("value", ""))}</div>'
            '</div>'
        )
        for highlight in highlights
    )
    classes = "mode-card download" if variant == "download" else "mode-card"
    return (
        f'<article class="{classes}">'
        f'<div class="mode-eyebrow">{_escape(str(mode.get("title", "entry")))}</div>'
        f'<div class="mode-title">{_escape(str(mode.get("headline", "")))}</div>'
        f'<div class="mode-description">{_escape(str(mode.get("description", "")))}</div>'
        f'<div class="mode-actions">{_render_action_link(str(primary_action.get("label", "Open")), primary_action.get("href"), primary=True)}{secondary_html}</div>'
        f'<div class="mode-highlights">{highlights_html}</div>'
        '</article>'
    )



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
        for bit in (
            [" · ".join(bit for bit in meta_bits if bit)]
            + ([role] if role else [])
            + ([f"sha256: {sha256[:12]}…"] if sha256 else [])
        )
        if bit
    )
    return (
        '<div class="entry">'
        f'<div><a href="{_escape(href)}">{_escape(label)}</a></div>'
        f'<div class="meta">{side}</div>'
        '</div>'
    )



def _resolve_repo_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    resolved = candidate if candidate.is_absolute() else project_root / candidate
    resolved = resolved.resolve()
    if not resolved.exists():
        raise SingleBaseDeliveryFrontdoorError(f"required path does not exist: {resolved}")
    return resolved



def _resolve_output_dir(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    resolved = candidate if candidate.is_absolute() else project_root / candidate
    resolved = resolved.resolve()
    if resolved.exists() and not resolved.is_dir():
        raise SingleBaseDeliveryFrontdoorError(
            f"frontdoor output path already exists and is not a directory: {resolved}"
        )
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved



def _display_repo_path(project_root: Path, path: Path) -> str:
    resolved = Path(path).resolve()
    project_root = Path(project_root).resolve()
    try:
        return resolved.relative_to(project_root).as_posix()
    except ValueError:
        return str(resolved)



def _path_from_output_dir(output_dir: Path, target_path: Path) -> str:
    relative = os.path.relpath(str(target_path), start=str(output_dir))
    return Path(relative).as_posix()



def _join_relative(prefix: str, leaf: str) -> str:
    return (Path(prefix) / leaf).as_posix() if prefix else leaf



def _atomic_copy_binary(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination_path.name}.tmp.", dir=str(destination_path.parent))
    try:
        with os.fdopen(fd, "wb") as handle, source_path.open("rb") as source_handle:
            shutil.copyfileobj(source_handle, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, destination_path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise



def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.tmp.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise



def _mapping(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}



def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)



def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
