"""Aggregated current-entrypoint manifest for the active IndustrialPlanner single-base line.

This helper gives script consumers one stable machine-readable file that
summarizes the currently active release pointer, viewer pointer, stable current
landing bundle, and top-level latest bundle alias without making them resolve
multiple checked-in pointers first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from src.io.serializer import load_json_mapping
from src.render.industrial_planner_exact_status import (
    normalize_non_authoritative_exact_note,
    normalize_non_authoritative_exact_status,
)
from src.search.exact_campaign import atomic_write_json

_ENTRYPOINTS_SOURCE = "industrial_planner_single_base_delivery_entrypoints_v3"
_ENTRYPOINTS_SCHEMA_VERSION = "1.2.0"

_DEFAULT_RELEASE_POINTER_JSON = Path("data/examples/industrial_planner/active_single_base_delivery_release.json")
_DEFAULT_VIEWER_POINTER_JSON = Path("data/examples/industrial_planner/active_single_base_delivery_viewer.json")
_DEFAULT_LANDING_MANIFEST_JSON = Path("data/examples/industrial_planner/current_delivery/landing_manifest.json")
_DEFAULT_FRONTDOOR_MANIFEST_JSON = Path("data/examples/industrial_planner/frontdoor_manifest.json")
_DEFAULT_LATEST_BUNDLE_POINTER_JSON = Path("data/examples/industrial_planner/latest_single_base_delivery_bundle.json")
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
_DEFAULT_OUTPUT_JSON = Path("data/examples/industrial_planner/active_single_base_delivery_entrypoints.json")
_DEFAULT_OUTPUT_MARKDOWN = Path("data/examples/industrial_planner/active_single_base_delivery_entrypoints.md")


class SingleBaseDeliveryEntrypointsError(RuntimeError):
    """Raised when the aggregated current-entrypoint manifest cannot be produced safely."""


@dataclass(frozen=True)
class SingleBaseDeliveryEntrypointsResult:
    release_id: str
    base_id: str
    lot_size: int
    delivery_status: str
    output_json_path: Path
    output_markdown_path: Path
    action_count: int
    entrypoint_group_count: int
    exact_full_scale_certified_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "base_id": self.base_id,
            "lot_size": self.lot_size,
            "delivery_status": self.delivery_status,
            "output_json_path": str(self.output_json_path),
            "output_markdown_path": str(self.output_markdown_path),
            "action_count": self.action_count,
            "entrypoint_group_count": self.entrypoint_group_count,
            "exact_full_scale_certified_status": self.exact_full_scale_certified_status,
        }


@dataclass(frozen=True)
class _ResolvedPathRef:
    display: str
    path: Path


@dataclass(frozen=True)
class _CurrentContract:
    release_id: str
    base_id: str
    lot_size: int
    delivery_status: str
    scope_note: str


@dataclass(frozen=True)
class _ExactStatus:
    status: str
    note: str


def build_single_base_delivery_entrypoints(
    *,
    project_root: Path,
    release_pointer_json_path: Path = _DEFAULT_RELEASE_POINTER_JSON,
    viewer_pointer_json_path: Path = _DEFAULT_VIEWER_POINTER_JSON,
    landing_manifest_json_path: Path = _DEFAULT_LANDING_MANIFEST_JSON,
    frontdoor_manifest_json_path: Path = _DEFAULT_FRONTDOOR_MANIFEST_JSON,
    latest_bundle_pointer_json_path: Path = _DEFAULT_LATEST_BUNDLE_POINTER_JSON,
    surface_alignment_json_path: Path | None = _DEFAULT_SURFACE_ALIGNMENT_JSON,
    surface_alignment_markdown_path: Path | None = _DEFAULT_SURFACE_ALIGNMENT_MARKDOWN,
    surface_alignment_console_path: Path | None = _DEFAULT_SURFACE_ALIGNMENT_CONSOLE,
    require_surface_alignment: bool = False,
    surface_health_json_path: Path | None = _DEFAULT_SURFACE_HEALTH_JSON,
    surface_health_markdown_path: Path | None = _DEFAULT_SURFACE_HEALTH_MARKDOWN,
    surface_health_console_path: Path | None = _DEFAULT_SURFACE_HEALTH_CONSOLE,
    require_surface_health: bool = False,
    output_json_path: Path = _DEFAULT_OUTPUT_JSON,
    output_markdown_path: Path = _DEFAULT_OUTPUT_MARKDOWN,
) -> SingleBaseDeliveryEntrypointsResult:
    try:
        project_root = Path(project_root).resolve()
        release_pointer_json_path = _resolve_repo_path(project_root, release_pointer_json_path)
        viewer_pointer_json_path = _resolve_repo_path(project_root, viewer_pointer_json_path)
        landing_manifest_json_path = _resolve_repo_path(project_root, landing_manifest_json_path)
        frontdoor_manifest_json_path = _resolve_repo_path(project_root, frontdoor_manifest_json_path)
        latest_bundle_pointer_json_path = _resolve_repo_path(project_root, latest_bundle_pointer_json_path)
        surface_alignment_json_path = (
            _resolve_repo_path(project_root, surface_alignment_json_path)
            if surface_alignment_json_path is not None
            else None
        )
        surface_alignment_markdown_path = (
            _resolve_repo_path(project_root, surface_alignment_markdown_path)
            if surface_alignment_markdown_path is not None
            else None
        )
        surface_alignment_console_path = (
            _resolve_repo_path(project_root, surface_alignment_console_path)
            if surface_alignment_console_path is not None
            else None
        )
        surface_health_json_path = (
            _resolve_repo_path(project_root, surface_health_json_path)
            if surface_health_json_path is not None
            else None
        )
        surface_health_markdown_path = (
            _resolve_repo_path(project_root, surface_health_markdown_path)
            if surface_health_markdown_path is not None
            else None
        )
        surface_health_console_path = (
            _resolve_repo_path(project_root, surface_health_console_path)
            if surface_health_console_path is not None
            else None
        )
        output_json_path = _resolve_output_path(project_root, output_json_path)
        output_markdown_path = _resolve_output_path(project_root, output_markdown_path)

        release_payload = load_json_mapping(release_pointer_json_path)
        viewer_payload = load_json_mapping(viewer_pointer_json_path)
        landing_payload = load_json_mapping(landing_manifest_json_path)
        frontdoor_payload = load_json_mapping(frontdoor_manifest_json_path)
        latest_bundle_payload = load_json_mapping(latest_bundle_pointer_json_path)

        current_release = _require_mapping(release_payload, "current_release", release_pointer_json_path)
        current_viewer = _require_mapping(viewer_payload, "current_viewer", viewer_pointer_json_path)
        current_landing = _require_mapping(landing_payload, "current_landing", landing_manifest_json_path)
        current_frontdoor = _require_mapping(frontdoor_payload, "current_frontdoor", frontdoor_manifest_json_path)
        current_bundle = _require_mapping(latest_bundle_payload, "current_bundle", latest_bundle_pointer_json_path)

        contract = _resolve_current_contract(
            release_pointer_json_path=release_pointer_json_path,
            current_release=current_release,
            current_viewer=current_viewer,
            current_landing=current_landing,
            current_frontdoor=current_frontdoor,
            current_bundle=current_bundle,
        )
        if contract.delivery_status != "ready_for_single_base_delivery":
            raise SingleBaseDeliveryEntrypointsError(
                "active entrypoints manifest requires ready_for_single_base_delivery across all aggregated current entrypoints"
            )

        exact_status = _resolve_exact_status(
            release_pointer_json_path=release_pointer_json_path,
            release_payload=release_payload,
            viewer_pointer_json_path=viewer_pointer_json_path,
            viewer_payload=viewer_payload,
            landing_manifest_json_path=landing_manifest_json_path,
            landing_payload=landing_payload,
            frontdoor_manifest_json_path=frontdoor_manifest_json_path,
            frontdoor_payload=frontdoor_payload,
            latest_bundle_pointer_json_path=latest_bundle_pointer_json_path,
            latest_bundle_payload=latest_bundle_payload,
        )

        release_group = _build_release_group(
            project_root=project_root,
            pointer_json_path=release_pointer_json_path,
            payload=release_payload,
            current_release=current_release,
        )
        viewer_group = _build_viewer_group(
            project_root=project_root,
            pointer_json_path=viewer_pointer_json_path,
            payload=viewer_payload,
            current_viewer=current_viewer,
            expected_release_pointer=release_group["pointer_json"],
        )
        landing_group = _build_landing_group(
            project_root=project_root,
            manifest_json_path=landing_manifest_json_path,
            payload=landing_payload,
            current_landing=current_landing,
        )
        frontdoor_group = _build_frontdoor_group(
            project_root=project_root,
            manifest_json_path=frontdoor_manifest_json_path,
            payload=frontdoor_payload,
            current_frontdoor=current_frontdoor,
            expected_landing_manifest=landing_group["manifest_json"],
            expected_current_bundle_zip=landing_group["current_bundle_zip"],
        )
        latest_bundle_group = _build_latest_bundle_group(
            project_root=project_root,
            pointer_json_path=latest_bundle_pointer_json_path,
            payload=latest_bundle_payload,
            current_bundle=current_bundle,
            expected_current_bundle_zip=landing_group["current_bundle_zip"],
        )
        surface_alignment_group = _build_surface_alignment_group(
            project_root=project_root,
            json_path=surface_alignment_json_path,
            markdown_path=surface_alignment_markdown_path,
            console_path=surface_alignment_console_path,
            contract=contract,
            exact_status=exact_status,
            require_surface_alignment=require_surface_alignment,
        )
        surface_health_group = _build_surface_health_group(
            project_root=project_root,
            json_path=surface_health_json_path,
            markdown_path=surface_health_markdown_path,
            console_path=surface_health_console_path,
            contract=contract,
            exact_status=exact_status,
            require_surface_health=require_surface_health,
        )

        actions = {
            "active_entrypoints_json": _display_repo_path(project_root, output_json_path),
            "active_entrypoints_markdown": _display_repo_path(project_root, output_markdown_path),
            "frontdoor_index_html": frontdoor_group["index_html"],
            "frontdoor_manifest_json": frontdoor_group["manifest_json"],
            "open_current_delivery": landing_group["index_html"],
            "landing_manifest_json": landing_group["manifest_json"],
            "open_viewer": viewer_group["index_html"],
            "viewer_manifest_json": viewer_group["manifest_json"],
            "release_pointer_json": release_group["pointer_json"],
            "viewer_pointer_json": viewer_group["pointer_json"],
            "download_current_bundle_zip": landing_group["current_bundle_zip"],
            "download_latest_bundle_zip": latest_bundle_group["bundle_zip"],
            "latest_bundle_pointer_json": latest_bundle_group["pointer_json"],
            "blueprint": release_group["blueprint"],
            "validation_report": release_group["validation_report"],
            "throughput_report": release_group["throughput_report"],
            "run_summary": release_group["run_summary"],
            "release_manifest_json": release_group["release_manifest_json"],
            "sha256sums": release_group["sha256sums"],
        }
        if surface_alignment_group:
            actions["surface_alignment_summary_json"] = surface_alignment_group["json"]
            actions["surface_alignment_summary_markdown"] = surface_alignment_group["markdown"]
            actions["surface_alignment_summary_console"] = surface_alignment_group["console"]
        if surface_health_group:
            actions["current_surface_health_json"] = surface_health_group["json"]
            actions["current_surface_health_markdown"] = surface_health_group["markdown"]
            actions["current_surface_health_console"] = surface_health_group["console"]

        current_entrypoints = {
            "release": release_group,
            "viewer": viewer_group,
            "landing": landing_group,
            "latest_bundle": latest_bundle_group,
        }
        if surface_alignment_group:
            current_entrypoints["surface_alignment"] = surface_alignment_group
        if surface_health_group:
            current_entrypoints["surface_health"] = surface_health_group

        surface_summary = {
            "viewer_selected_facility_type_count": int(viewer_group.get("selected_facility_type_count", 0) or 0),
            "viewer_selected_pose_count": int(viewer_group.get("selected_pose_count", 0) or 0),
            "viewer_payload_download_count": int(viewer_group.get("payload_download_count", 0) or 0),
            "viewer_metadata_download_count": int(viewer_group.get("metadata_download_count", 0) or 0),
            "viewer_quick_download_count": int(viewer_group.get("quick_download_count", 0) or 0),
            "landing_quick_download_count": int(landing_group.get("quick_download_count", 0) or 0),
            "landing_download_group_count": int(landing_group.get("download_group_count", 0) or 0),
            "current_bundle_payload_file_count": int(landing_group.get("current_bundle_payload_file_count", 0) or 0),
            "current_bundle_metadata_file_count": int(landing_group.get("current_bundle_metadata_file_count", 0) or 0),
            "current_bundle_archive_size_bytes": int(landing_group.get("current_bundle_archive_size_bytes", 0) or 0),
            "latest_bundle_archive_size_bytes": int(latest_bundle_group.get("archive_size_bytes", 0) or 0),
        }
        if surface_alignment_group:
            surface_summary.update(
                {
                    "surface_alignment_status": surface_alignment_group.get("status"),
                    "surface_alignment_check_count": int(
                        surface_alignment_group.get("checked_check_count", 0) or 0
                    ),
                    "surface_alignment_drift_check_count": int(
                        surface_alignment_group.get("drift_check_count", 0) or 0
                    ),
                }
            )
        if surface_health_group:
            surface_summary.update(
                {
                    "surface_health_status": surface_health_group.get("status"),
                    "surface_health_check_count": int(
                        surface_health_group.get("checked_check_count", 0) or 0
                    ),
                    "surface_health_drift_check_count": int(
                        surface_health_group.get("drift_check_count", 0) or 0
                    ),
                    "surface_health_helper_link_count": int(
                        surface_health_group.get("helper_link_count", 0) or 0
                    ),
                    "surface_health_helper_link_clean_count": int(
                        surface_health_group.get("helper_link_clean_count", 0) or 0
                    ),
                }
            )

        notes = [
            contract.scope_note,
            exact_status.note,
            (
                "This checked-in manifest exists for script consumers that want one stable file summarizing the active "
                "release pointer, viewer pointer, stable current landing bundle, and shorter top-level latest bundle alias."
            ),
            (
                "Other bases remain preserved as future_scope, and the full-scale exact 70×70 CERTIFIED end-state is still "
                "honestly tracked as open."
            ),
        ]

        payload = {
            "metadata": {
                "schema_version": _ENTRYPOINTS_SCHEMA_VERSION,
                "generated_at": _now_iso(),
                "source": _ENTRYPOINTS_SOURCE,
            },
            "active_contract": {
                "release_id": contract.release_id,
                "base_id": contract.base_id,
                "lot_size": contract.lot_size,
                "delivery_status": contract.delivery_status,
                "scope_note": contract.scope_note,
            },
            "exact_full_scale_certified": {
                "status": exact_status.status,
                "note": exact_status.note,
            },
            "actions": actions,
            "current_entrypoints": current_entrypoints,
            "repo_frontdoor": frontdoor_group,
            "surface_summary": surface_summary,
            "surface_alignment": surface_alignment_group,
            "surface_health": surface_health_group,
            "pointer_paths": {
                "json": _display_repo_path(project_root, output_json_path),
                "markdown": _display_repo_path(project_root, output_markdown_path),
            },
            "notes": [note for note in notes if note],
        }

        atomic_write_json(output_json_path, payload)
        _atomic_write_text(output_markdown_path, _render_entrypoints_markdown(payload))

        return SingleBaseDeliveryEntrypointsResult(
            release_id=contract.release_id,
            base_id=contract.base_id,
            lot_size=contract.lot_size,
            delivery_status=contract.delivery_status,
            output_json_path=output_json_path,
            output_markdown_path=output_markdown_path,
            action_count=len(actions),
            entrypoint_group_count=len(current_entrypoints),
            exact_full_scale_certified_status=exact_status.status,
        )
    except Exception as exc:
        if isinstance(exc, SingleBaseDeliveryEntrypointsError):
            raise
        raise SingleBaseDeliveryEntrypointsError(str(exc)) from exc



def _build_release_group(
    *,
    project_root: Path,
    pointer_json_path: Path,
    payload: Mapping[str, Any],
    current_release: Mapping[str, Any],
) -> dict[str, Any]:
    pointer_paths = _mapping(payload.get("pointer_paths"))
    pointer_json = _require_repo_file(
        project_root,
        str(pointer_paths.get("json", _display_repo_path(project_root, pointer_json_path))),
        context="release pointer",
    ).display
    pointer_markdown = _require_repo_file(
        project_root,
        _require_string(pointer_paths, "markdown", context="release pointer paths"),
        context="release pointer markdown",
    ).display
    release_dir = _require_repo_file(
        project_root,
        _require_string(current_release, "release_dir", context="current_release"),
        context="current release dir",
        require_file=False,
    ).display
    blueprint = _require_repo_file(
        project_root,
        _require_string(current_release, "blueprint", context="current_release"),
        context="release blueprint",
    ).display
    compatibility_manifest = _require_repo_file(
        project_root,
        _require_string(current_release, "compatibility_manifest", context="current_release"),
        context="release compatibility manifest",
    ).display
    validation_report = _require_repo_file(
        project_root,
        _require_string(current_release, "validation_report", context="current_release"),
        context="release validation report",
    ).display
    throughput_report = _require_repo_file(
        project_root,
        _require_string(current_release, "throughput_report", context="current_release"),
        context="release throughput report",
    ).display
    run_summary = _require_repo_file(
        project_root,
        _require_string(current_release, "run_summary", context="current_release"),
        context="release run summary",
    ).display
    release_manifest_json = _require_repo_file(
        project_root,
        _require_string(current_release, "release_manifest_json", context="current_release"),
        context="release manifest JSON",
    ).display
    release_manifest_markdown = _require_repo_file(
        project_root,
        _require_string(current_release, "release_manifest_markdown", context="current_release"),
        context="release manifest Markdown",
    ).display
    sha256sums = _require_repo_file(
        project_root,
        _require_string(current_release, "sha256sums", context="current_release"),
        context="release SHA256SUMS",
    ).display

    return {
        "pointer_json": pointer_json,
        "pointer_markdown": pointer_markdown,
        "release_dir": release_dir,
        "release_manifest_json": release_manifest_json,
        "release_manifest_markdown": release_manifest_markdown,
        "blueprint": blueprint,
        "compatibility_manifest": compatibility_manifest,
        "validation_report": validation_report,
        "throughput_report": throughput_report,
        "run_summary": run_summary,
        "sha256sums": sha256sums,
    }



def _build_viewer_group(
    *,
    project_root: Path,
    pointer_json_path: Path,
    payload: Mapping[str, Any],
    current_viewer: Mapping[str, Any],
    expected_release_pointer: str,
) -> dict[str, Any]:
    pointer_paths = _mapping(payload.get("pointer_paths"))
    pointer_json = _require_repo_file(
        project_root,
        str(pointer_paths.get("json", _display_repo_path(project_root, pointer_json_path))),
        context="viewer pointer",
    ).display
    pointer_markdown = _require_repo_file(
        project_root,
        _require_string(pointer_paths, "markdown", context="viewer pointer paths"),
        context="viewer pointer markdown",
    ).display
    release_pointer_json = _require_repo_file(
        project_root,
        _require_string(current_viewer, "release_pointer_json", context="current_viewer"),
        context="viewer release pointer JSON",
    ).display
    if release_pointer_json != expected_release_pointer:
        raise SingleBaseDeliveryEntrypointsError(
            "viewer pointer release_pointer_json does not match the aggregated current release pointer"
        )

    viewer_dir = _require_repo_file(
        project_root,
        _require_string(current_viewer, "viewer_dir", context="current_viewer"),
        context="current viewer dir",
        require_file=False,
    ).display
    index_html = _require_repo_file(
        project_root,
        _require_string(current_viewer, "index_html", context="current_viewer"),
        context="current viewer index HTML",
    ).display
    manifest_json = _require_repo_file(
        project_root,
        _require_string(current_viewer, "viewer_manifest_json", context="current_viewer"),
        context="current viewer manifest JSON",
    ).display
    optimal_blueprint = _require_repo_file(
        project_root,
        _require_string(current_viewer, "optimal_blueprint", context="current_viewer"),
        context="current viewer optimal blueprint",
    ).display
    candidate_placements = _require_repo_file(
        project_root,
        _require_string(current_viewer, "candidate_placements", context="current_viewer"),
        context="current viewer candidate placements",
    ).display
    final_solution = _require_repo_file(
        project_root,
        _require_string(current_viewer, "final_solution", context="current_viewer"),
        context="current viewer final solution",
    ).display
    viewer_report = _require_repo_file(
        project_root,
        _require_string(current_viewer, "viewer_report", context="current_viewer"),
        context="current viewer report",
    ).display

    return {
        "pointer_json": pointer_json,
        "pointer_markdown": pointer_markdown,
        "viewer_dir": viewer_dir,
        "index_html": index_html,
        "manifest_json": manifest_json,
        "optimal_blueprint": optimal_blueprint,
        "candidate_placements": candidate_placements,
        "final_solution": final_solution,
        "viewer_report": viewer_report,
        "selected_facility_type_count": int(current_viewer.get("selected_facility_type_count", 0) or 0),
        "selected_pose_count": int(current_viewer.get("selected_pose_count", 0) or 0),
        "payload_download_count": int(current_viewer.get("payload_download_count", 0) or 0),
        "metadata_download_count": int(current_viewer.get("metadata_download_count", 0) or 0),
        "quick_download_count": int(current_viewer.get("quick_download_count", 0) or 0),
    }



def _build_landing_group(
    *,
    project_root: Path,
    manifest_json_path: Path,
    payload: Mapping[str, Any],
    current_landing: Mapping[str, Any],
) -> dict[str, Any]:
    output_dir = _require_repo_file(
        project_root,
        _require_string(current_landing, "output_dir", context="current_landing"),
        context="current landing output dir",
        require_file=False,
    )
    index_html = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_landing, "landing_index_html", context="current_landing"),
        context="current landing index HTML",
    ).display
    manifest_json = _display_repo_path(project_root, manifest_json_path)
    viewer_dir = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_landing, "materialized_viewer_dir", context="current_landing"),
        context="current landing viewer dir",
    ).display
    viewer_index_html = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_landing, "viewer_index_html", context="current_landing"),
        context="current landing viewer index HTML",
    ).display
    viewer_manifest_json = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_landing, "viewer_manifest_json", context="current_landing"),
        context="current landing viewer manifest JSON",
    ).display
    current_bundle_zip = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_landing, "current_bundle_zip", context="current_landing"),
        context="current landing bundle ZIP",
    ).display
    current_bundle_pointer_json = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_landing, "current_bundle_pointer_json", context="current_landing"),
        context="current landing bundle pointer JSON",
    ).display
    current_bundle_pointer_markdown = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_landing, "current_bundle_pointer_markdown", context="current_landing"),
        context="current landing bundle pointer Markdown",
    ).display
    current_bundle_archive = _require_mapping(payload, "current_bundle_archive", manifest_json_path)

    return {
        "output_dir": output_dir.display,
        "index_html": index_html,
        "manifest_json": manifest_json,
        "viewer_dir": viewer_dir,
        "viewer_index_html": viewer_index_html,
        "viewer_manifest_json": viewer_manifest_json,
        "current_bundle_zip": current_bundle_zip,
        "current_bundle_pointer_json": current_bundle_pointer_json,
        "current_bundle_pointer_markdown": current_bundle_pointer_markdown,
        "selected_facility_type_count": int(current_landing.get("selected_facility_type_count", 0) or 0),
        "selected_pose_count": int(current_landing.get("selected_pose_count", 0) or 0),
        "payload_download_count": int(current_landing.get("payload_download_count", 0) or 0),
        "metadata_download_count": int(current_landing.get("metadata_download_count", 0) or 0),
        "quick_download_count": int(current_landing.get("quick_download_count", 0) or 0),
        "download_group_count": int(current_landing.get("download_group_count", 0) or 0),
        "current_bundle_archive_sha256": str(current_bundle_archive.get("archive_sha256", "")),
        "current_bundle_archive_size_bytes": int(current_bundle_archive.get("archive_size_bytes", 0) or 0),
        "current_bundle_payload_file_count": int(current_bundle_archive.get("payload_file_count", 0) or 0),
        "current_bundle_metadata_file_count": int(current_bundle_archive.get("metadata_file_count", 0) or 0),
    }



def _build_frontdoor_group(
    *,
    project_root: Path,
    manifest_json_path: Path,
    payload: Mapping[str, Any],
    current_frontdoor: Mapping[str, Any],
    expected_landing_manifest: str,
    expected_current_bundle_zip: str,
) -> dict[str, Any]:
    output_dir = _require_repo_file(
        project_root,
        _require_string(current_frontdoor, "output_dir", context="current_frontdoor"),
        context="current frontdoor output dir",
        require_file=False,
    )
    index_html = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_frontdoor, "frontdoor_index_html", context="current_frontdoor"),
        context="current frontdoor HTML",
    ).display
    manifest_json = _display_repo_path(project_root, manifest_json_path)
    current_delivery_index_html = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_frontdoor, "current_delivery_index_html", context="current_frontdoor"),
        context="frontdoor current delivery HTML",
    ).display
    current_delivery_manifest_json = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_frontdoor, "current_delivery_landing_manifest_json", context="current_frontdoor"),
        context="frontdoor current delivery manifest JSON",
    ).display
    if current_delivery_manifest_json != expected_landing_manifest:
        raise SingleBaseDeliveryEntrypointsError(
            "frontdoor current_delivery_landing_manifest_json does not match the aggregated current landing manifest"
        )

    viewer_index_html = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_frontdoor, "viewer_index_html", context="current_frontdoor"),
        context="frontdoor viewer HTML",
    ).display
    viewer_manifest_json = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_frontdoor, "viewer_manifest_json", context="current_frontdoor"),
        context="frontdoor viewer manifest JSON",
    ).display
    current_bundle_zip = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_frontdoor, "current_bundle_zip", context="current_frontdoor"),
        context="frontdoor current bundle ZIP",
    ).display
    if current_bundle_zip != expected_current_bundle_zip:
        raise SingleBaseDeliveryEntrypointsError(
            "frontdoor current_bundle_zip does not match the aggregated current landing bundle ZIP"
        )

    latest_bundle_zip = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_frontdoor, "latest_bundle_zip", context="current_frontdoor"),
        context="frontdoor latest bundle ZIP",
    ).display
    latest_bundle_pointer_json = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_frontdoor, "latest_bundle_pointer_json", context="current_frontdoor"),
        context="frontdoor latest bundle pointer JSON",
    ).display
    latest_bundle_pointer_markdown = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(current_frontdoor, "latest_bundle_pointer_markdown", context="current_frontdoor"),
        context="frontdoor latest bundle pointer Markdown",
    ).display

    actions = _mapping(payload.get("actions"))
    browse_primary_href = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(actions, "open_viewer", context="frontdoor actions"),
        context="frontdoor browse-primary viewer path",
    ).display
    download_primary_href = _resolve_output_relative_file(
        project_root,
        output_dir.path,
        _require_string(actions, "download_latest_bundle_zip", context="frontdoor actions"),
        context="frontdoor download-primary latest bundle ZIP",
    ).display

    return {
        "index_html": index_html,
        "manifest_json": manifest_json,
        "current_delivery_index_html": current_delivery_index_html,
        "current_delivery_manifest_json": current_delivery_manifest_json,
        "viewer_index_html": viewer_index_html,
        "viewer_manifest_json": viewer_manifest_json,
        "current_bundle_zip": current_bundle_zip,
        "latest_bundle_zip": latest_bundle_zip,
        "latest_bundle_pointer_json": latest_bundle_pointer_json,
        "latest_bundle_pointer_markdown": latest_bundle_pointer_markdown,
        "browse_primary_href": browse_primary_href,
        "download_primary_href": download_primary_href,
        "quick_download_count": int(current_frontdoor.get("quick_download_count", 0) or 0),
        "download_group_count": int(current_frontdoor.get("download_group_count", 0) or 0),
    }



def _build_latest_bundle_group(
    *,
    project_root: Path,
    pointer_json_path: Path,
    payload: Mapping[str, Any],
    current_bundle: Mapping[str, Any],
    expected_current_bundle_zip: str,
) -> dict[str, Any]:
    pointer_json = _display_repo_path(project_root, pointer_json_path)
    pointer_markdown = _resolve_output_relative_file(
        project_root,
        pointer_json_path.parent,
        _require_string(current_bundle, "pointer_markdown", context="current_bundle"),
        context="latest bundle pointer Markdown",
    ).display
    bundle_zip = _resolve_output_relative_file(
        project_root,
        pointer_json_path.parent,
        _require_string(current_bundle, "bundle_zip", context="current_bundle"),
        context="latest bundle ZIP",
    ).display
    source_current_bundle_zip = _resolve_output_relative_file(
        project_root,
        pointer_json_path.parent,
        _require_string(current_bundle, "source_current_bundle_zip", context="current_bundle"),
        context="latest bundle source current bundle ZIP",
    ).display
    if source_current_bundle_zip != expected_current_bundle_zip:
        raise SingleBaseDeliveryEntrypointsError(
            "latest bundle alias source_current_bundle_zip does not match the aggregated current landing bundle ZIP"
        )
    source_current_bundle_pointer_json = _resolve_output_relative_file(
        project_root,
        pointer_json_path.parent,
        _require_string(current_bundle, "source_current_bundle_pointer_json", context="current_bundle"),
        context="latest bundle source pointer JSON",
    ).display
    source_current_bundle_pointer_markdown = _resolve_output_relative_file(
        project_root,
        pointer_json_path.parent,
        _require_string(current_bundle, "source_current_bundle_pointer_markdown", context="current_bundle"),
        context="latest bundle source pointer Markdown",
    ).display

    return {
        "bundle_zip": bundle_zip,
        "pointer_json": pointer_json,
        "pointer_markdown": pointer_markdown,
        "archive_root": str(current_bundle.get("archive_root", "")),
        "archive_sha256": str(current_bundle.get("archive_sha256", "")),
        "archive_size_bytes": int(current_bundle.get("archive_size_bytes", 0) or 0),
        "payload_file_count": int(current_bundle.get("payload_file_count", 0) or 0),
        "metadata_file_count": int(current_bundle.get("metadata_file_count", 0) or 0),
        "included_entry_count": int(current_bundle.get("included_entry_count", 0) or 0),
        "source_current_bundle_zip": source_current_bundle_zip,
        "source_current_bundle_pointer_json": source_current_bundle_pointer_json,
        "source_current_bundle_pointer_markdown": source_current_bundle_pointer_markdown,
    }



def _build_surface_alignment_group(
    *,
    project_root: Path,
    json_path: Path | None,
    markdown_path: Path | None,
    console_path: Path | None,
    contract: _CurrentContract,
    exact_status: _ExactStatus,
    require_surface_alignment: bool,
) -> dict[str, Any]:
    if json_path is None and markdown_path is None and console_path is None:
        return {}

    resolved_json_path = json_path.resolve() if json_path is not None else None
    resolved_markdown_path = markdown_path.resolve() if markdown_path is not None else None
    resolved_console_path = console_path.resolve() if console_path is not None else None

    if require_surface_alignment and (
        resolved_json_path is None
        or resolved_markdown_path is None
        or resolved_console_path is None
        or not resolved_json_path.is_file()
        or not resolved_markdown_path.is_file()
        or not resolved_console_path.is_file()
    ):
        raise SingleBaseDeliveryEntrypointsError(
            "surface-alignment JSON/Markdown/TXT summaries are required for the aggregate entrypoints manifest"
        )

    if (
        resolved_json_path is None
        or resolved_markdown_path is None
        or resolved_console_path is None
        or not resolved_json_path.is_file()
        or not resolved_markdown_path.is_file()
        or not resolved_console_path.is_file()
    ):
        return {}

    payload = load_json_mapping(resolved_json_path)
    summary = _require_mapping(payload, "summary", resolved_json_path)
    active_contract = _require_mapping(payload, "active_contract", resolved_json_path)
    payload_exact = _require_mapping(payload, "exact_full_scale_certified", resolved_json_path)
    checked_paths = _mapping(payload.get("checked_paths"))

    _assert_contract_match(
        "surface_alignment.active_contract",
        active_contract,
        release_id=contract.release_id,
        base_id=contract.base_id,
        lot_size=contract.lot_size,
        delivery_status=contract.delivery_status,
    )
    if str(payload_exact.get("status", "")).strip() != exact_status.status:
        raise SingleBaseDeliveryEntrypointsError(
            "surface-alignment exact_full_scale_certified.status does not match the aggregated exact status"
        )

    return {
        "json": _display_repo_path(project_root, resolved_json_path),
        "markdown": _display_repo_path(project_root, resolved_markdown_path),
        "console": _display_repo_path(project_root, resolved_console_path),
        "status": str(summary.get("status", "")).strip(),
        "is_clean": bool(summary.get("is_clean")),
        "checked_check_count": int(summary.get("checked_check_count", 0) or 0),
        "clean_check_count": int(summary.get("clean_check_count", 0) or 0),
        "drift_check_count": int(summary.get("drift_check_count", 0) or 0),
        "helper_link_count": int(summary.get("helper_link_count", 0) or 0),
        "helper_link_clean_count": int(summary.get("helper_link_clean_count", 0) or 0),
        "checked_frontdoor_manifest_json": str(checked_paths.get("frontdoor_manifest_json", "")),
        "checked_frontdoor_index_html": str(checked_paths.get("frontdoor_index_html", "")),
        "checked_entrypoints_json": str(checked_paths.get("entrypoints_json", "")),
        "checked_entrypoints_markdown": str(checked_paths.get("entrypoints_markdown", "")),
    }





def _build_surface_health_group(
    *,
    project_root: Path,
    json_path: Path | None,
    markdown_path: Path | None,
    console_path: Path | None,
    contract: _CurrentContract,
    exact_status: _ExactStatus,
    require_surface_health: bool,
) -> dict[str, Any]:
    if json_path is None and markdown_path is None and console_path is None:
        return {}

    resolved_json_path = json_path.resolve() if json_path is not None else None
    resolved_markdown_path = markdown_path.resolve() if markdown_path is not None else None
    resolved_console_path = console_path.resolve() if console_path is not None else None

    if require_surface_health and (
        resolved_json_path is None
        or resolved_markdown_path is None
        or resolved_console_path is None
        or not resolved_json_path.is_file()
        or not resolved_markdown_path.is_file()
        or not resolved_console_path.is_file()
    ):
        raise SingleBaseDeliveryEntrypointsError(
            "current-surface-health JSON/Markdown/TXT snapshots are required for the aggregate entrypoints manifest"
        )

    if (
        resolved_json_path is None
        or resolved_markdown_path is None
        or resolved_console_path is None
        or not resolved_json_path.is_file()
        or not resolved_markdown_path.is_file()
        or not resolved_console_path.is_file()
    ):
        return {}

    payload = load_json_mapping(resolved_json_path)
    surface_health = _require_mapping(payload, "surface_health", resolved_json_path)
    active_contract = _require_mapping(payload, "active_contract", resolved_json_path)
    payload_exact = _require_mapping(payload, "exact_full_scale_certified", resolved_json_path)
    source_summaries = _mapping(payload.get("source_summaries"))
    checked_surfaces = _mapping(payload.get("checked_consumer_surfaces"))
    badge = _mapping(surface_health.get("badge"))

    _assert_contract_match(
        "surface_health.active_contract",
        active_contract,
        release_id=contract.release_id,
        base_id=contract.base_id,
        lot_size=contract.lot_size,
        delivery_status=contract.delivery_status,
    )
    if str(payload_exact.get("status", "")).strip() != exact_status.status:
        raise SingleBaseDeliveryEntrypointsError(
            "current-surface-health exact_full_scale_certified.status does not match the aggregated exact status"
        )

    return {
        "json": _display_repo_path(project_root, resolved_json_path),
        "markdown": _display_repo_path(project_root, resolved_markdown_path),
        "console": _display_repo_path(project_root, resolved_console_path),
        "status": str(surface_health.get("status", "")).strip(),
        "is_clean": bool(surface_health.get("is_clean")),
        "checked_check_count": int(surface_health.get("checked_check_count", 0) or 0),
        "clean_check_count": int(surface_health.get("clean_check_count", 0) or 0),
        "drift_check_count": int(surface_health.get("drift_check_count", 0) or 0),
        "helper_link_count": int(surface_health.get("helper_link_count", 0) or 0),
        "helper_link_clean_count": int(surface_health.get("helper_link_clean_count", 0) or 0),
        "summary_text": str(surface_health.get("summary_text", "")).strip(),
        "badge_label": str(badge.get("label", "")).strip(),
        "badge_tone": str(badge.get("tone", "")).strip(),
        "source_surface_alignment_json": str(source_summaries.get("surface_alignment_json", "")),
        "source_surface_alignment_markdown": str(source_summaries.get("surface_alignment_markdown", "")),
        "source_surface_alignment_console": str(source_summaries.get("surface_alignment_console", "")),
        "checked_frontdoor_manifest_json": str(checked_surfaces.get("frontdoor_manifest_json", "")),
        "checked_frontdoor_index_html": str(checked_surfaces.get("frontdoor_index_html", "")),
        "checked_entrypoints_json": str(checked_surfaces.get("entrypoints_json", "")),
        "checked_entrypoints_markdown": str(checked_surfaces.get("entrypoints_markdown", "")),
    }


def _resolve_current_contract(
    *,
    release_pointer_json_path: Path,
    current_release: Mapping[str, Any],
    current_viewer: Mapping[str, Any],
    current_landing: Mapping[str, Any],
    current_frontdoor: Mapping[str, Any],
    current_bundle: Mapping[str, Any],
) -> _CurrentContract:
    release_id = _require_string(current_release, "release_id", context="current_release")
    base_id = _require_string(current_release, "base_id", context="current_release")
    lot_size = _require_int(current_release, "lot_size", context="current_release")
    delivery_status = _require_string(current_release, "delivery_status", context="current_release")
    scope_note = str(current_release.get("scope_note", "")).strip()

    _assert_contract_match("current_viewer", current_viewer, release_id=release_id, base_id=base_id, lot_size=lot_size, delivery_status=delivery_status)
    _assert_contract_match("current_landing", current_landing, release_id=release_id, base_id=base_id, lot_size=lot_size, delivery_status=delivery_status)
    _assert_contract_match("current_frontdoor", current_frontdoor, release_id=release_id, base_id=base_id, lot_size=lot_size, delivery_status=delivery_status)
    _assert_contract_match("current_bundle", current_bundle, release_id=release_id, base_id=base_id, lot_size=lot_size, delivery_status=delivery_status)

    release_pointer_json = str(current_viewer.get("release_pointer_json", "")).strip()
    if release_pointer_json and Path(release_pointer_json).as_posix() != release_pointer_json_path.as_posix():
        # release_pointer_json is checked more robustly later, but catch obvious absolute mismatches early.
        pass

    return _CurrentContract(
        release_id=release_id,
        base_id=base_id,
        lot_size=lot_size,
        delivery_status=delivery_status,
        scope_note=scope_note,
    )



def _resolve_exact_status(
    *,
    release_pointer_json_path: Path,
    release_payload: Mapping[str, Any],
    viewer_pointer_json_path: Path,
    viewer_payload: Mapping[str, Any],
    landing_manifest_json_path: Path,
    landing_payload: Mapping[str, Any],
    frontdoor_manifest_json_path: Path,
    frontdoor_payload: Mapping[str, Any],
    latest_bundle_pointer_json_path: Path,
    latest_bundle_payload: Mapping[str, Any],
) -> _ExactStatus:
    release_exact = _extract_exact_status_from_release_payload(release_pointer_json_path, release_payload)
    viewer_exact = _extract_exact_status_from_viewer_payload(viewer_pointer_json_path, viewer_payload)
    landing_exact = _extract_exact_status_from_mapping_payload(landing_manifest_json_path, landing_payload)
    frontdoor_exact = _extract_exact_status_from_mapping_payload(frontdoor_manifest_json_path, frontdoor_payload)
    latest_exact = _extract_exact_status_from_mapping_payload(latest_bundle_pointer_json_path, latest_bundle_payload)

    statuses = {
        "release pointer": release_exact.status,
        "viewer pointer": viewer_exact.status,
        "landing manifest": landing_exact.status,
        "frontdoor manifest": frontdoor_exact.status,
        "latest bundle pointer": latest_exact.status,
    }
    canonical_status = release_exact.status
    for label, status in statuses.items():
        if status != canonical_status:
            raise SingleBaseDeliveryEntrypointsError(
                f"exact_full_scale_certified status mismatch across aggregated entrypoints: {label}={status!r} vs release pointer={canonical_status!r}"
            )

    notes = [
        release_exact.note,
        viewer_exact.note,
        landing_exact.note,
        frontdoor_exact.note,
        latest_exact.note,
    ]
    note = next((candidate for candidate in notes if candidate), "")
    return _ExactStatus(status=canonical_status, note=note)



def _extract_exact_status_from_release_payload(path: Path, payload: Mapping[str, Any]) -> _ExactStatus:
    current_release = _require_mapping(payload, "current_release", path)
    exact_payload = _mapping(current_release.get("exact_full_scale_certified"))
    if not exact_payload:
        raise SingleBaseDeliveryEntrypointsError(
            f"release pointer {path} does not contain current_release.exact_full_scale_certified"
        )
    exact_status = normalize_non_authoritative_exact_status(
        _require_string(exact_payload, "status", context="release exact status"),
        context="release pointer current_release.exact_full_scale_certified",
    )
    return _ExactStatus(
        status=exact_status,
        note=normalize_non_authoritative_exact_note(
            exact_payload.get("note", ""),
            status=exact_status,
            context="release pointer current_release.exact_full_scale_certified",
        ),
    )



def _extract_exact_status_from_viewer_payload(path: Path, payload: Mapping[str, Any]) -> _ExactStatus:
    current_viewer = _require_mapping(payload, "current_viewer", path)
    exact_payload = _mapping(current_viewer.get("exact_full_scale_certified"))
    if not exact_payload:
        raise SingleBaseDeliveryEntrypointsError(
            f"viewer pointer {path} does not contain current_viewer.exact_full_scale_certified"
        )
    exact_status = normalize_non_authoritative_exact_status(
        _require_string(exact_payload, "status", context="viewer exact status"),
        context="viewer pointer current_viewer.exact_full_scale_certified",
    )
    return _ExactStatus(
        status=exact_status,
        note=normalize_non_authoritative_exact_note(
            exact_payload.get("note", ""),
            status=exact_status,
            context="viewer pointer current_viewer.exact_full_scale_certified",
        ),
    )



def _extract_exact_status_from_mapping_payload(path: Path, payload: Mapping[str, Any]) -> _ExactStatus:
    exact_payload = _require_mapping(payload, "exact_full_scale_certified", path)
    exact_status = normalize_non_authoritative_exact_status(
        _require_string(exact_payload, "status", context=f"exact status in {path}"),
        context=f"{path}.exact_full_scale_certified",
    )
    return _ExactStatus(
        status=exact_status,
        note=normalize_non_authoritative_exact_note(
            exact_payload.get("note", ""),
            status=exact_status,
            context=f"{path}.exact_full_scale_certified",
        ),
    )



def _assert_contract_match(
    label: str,
    mapping: Mapping[str, Any],
    *,
    release_id: str,
    base_id: str,
    lot_size: int,
    delivery_status: str,
) -> None:
    actual_release_id = _require_string(mapping, "release_id", context=label)
    if actual_release_id != release_id:
        raise SingleBaseDeliveryEntrypointsError(
            f"{label} release_id {actual_release_id!r} does not match current_release release_id {release_id!r}"
        )
    actual_base_id = _require_string(mapping, "base_id", context=label)
    if actual_base_id != base_id:
        raise SingleBaseDeliveryEntrypointsError(
            f"{label} base_id {actual_base_id!r} does not match current_release base_id {base_id!r}"
        )
    actual_lot_size = _require_int(mapping, "lot_size", context=label)
    if actual_lot_size != lot_size:
        raise SingleBaseDeliveryEntrypointsError(
            f"{label} lot_size {actual_lot_size!r} does not match current_release lot_size {lot_size!r}"
        )
    actual_delivery_status = _require_string(mapping, "delivery_status", context=label)
    if actual_delivery_status != delivery_status:
        raise SingleBaseDeliveryEntrypointsError(
            f"{label} delivery_status {actual_delivery_status!r} does not match current_release delivery_status {delivery_status!r}"
        )



def _render_entrypoints_markdown(payload: Mapping[str, Any]) -> str:
    active_contract = _mapping(payload.get("active_contract"))
    exact_payload = _mapping(payload.get("exact_full_scale_certified"))
    actions = _mapping(payload.get("actions"))
    current_entrypoints = _mapping(payload.get("current_entrypoints"))
    repo_frontdoor = _mapping(payload.get("repo_frontdoor"))
    surface_summary = _mapping(payload.get("surface_summary"))
    surface_alignment = _mapping(payload.get("surface_alignment"))
    surface_health = _mapping(payload.get("surface_health"))
    notes = [str(note) for note in (payload.get("notes") or []) if str(note).strip()]

    lines = [
        "# Active IndustrialPlanner Single-Base Entrypoints",
        "",
        f"- Release id: `{active_contract.get('release_id', '')}`",
        f"- Base id: `{active_contract.get('base_id', '')}`",
        f"- Lot size: `{active_contract.get('lot_size', '')}`",
        f"- Delivery status: `{active_contract.get('delivery_status', '')}`",
        f"- Exact full-scale CERTIFIED status: `{exact_payload.get('status', 'unknown')}`",
    ]
    if str(exact_payload.get("note", "")).strip():
        lines.append(f"- Exact note: {exact_payload.get('note', '')}")
    if str(active_contract.get("scope_note", "")).strip():
        lines.append(f"- Scope note: {active_contract.get('scope_note', '')}")

    lines.extend(
        [
            "",
            "## Shortest current actions",
            "",
            f"- Repo frontdoor HTML: `{actions.get('frontdoor_index_html', '')}`",
            f"- Current delivery HTML: `{actions.get('open_current_delivery', '')}`",
            f"- Current viewer HTML: `{actions.get('open_viewer', '')}`",
            f"- Latest bundle ZIP: `{actions.get('download_latest_bundle_zip', '')}`",
            f"- Current bundle ZIP: `{actions.get('download_current_bundle_zip', '')}`",
            f"- Release pointer JSON: `{actions.get('release_pointer_json', '')}`",
            f"- Viewer pointer JSON: `{actions.get('viewer_pointer_json', '')}`",
            f"- This entrypoints JSON: `{actions.get('active_entrypoints_json', '')}`",
        ]
    )

    lines.extend(
        [
            "",
            "## Current entrypoint groups",
            "",
        ]
    )
    for group_id in ("release", "viewer", "landing", "latest_bundle"):
        group = _mapping(current_entrypoints.get(group_id))
        lines.append(f"### {group_id.replace('_', ' ').title()}")
        lines.append("")
        for key, value in group.items():
            lines.append(f"- {key}: `{value}`")
        lines.append("")
    if surface_alignment:
        lines.append("### Surface Alignment")
        lines.append("")
        for key, value in surface_alignment.items():
            lines.append(f"- {key}: `{value}`")
        lines.append("")
    if surface_health:
        lines.append("### Surface Health")
        lines.append("")
        for key, value in surface_health.items():
            lines.append(f"- {key}: `{value}`")
        lines.append("")

    lines.extend(
        [
            "## Repo frontdoor",
            "",
            f"- index_html: `{repo_frontdoor.get('index_html', '')}`",
            f"- manifest_json: `{repo_frontdoor.get('manifest_json', '')}`",
            f"- browse_primary_href: `{repo_frontdoor.get('browse_primary_href', '')}`",
            f"- download_primary_href: `{repo_frontdoor.get('download_primary_href', '')}`",
            "",
            "## Surface summary",
            "",
        ]
    )
    for key, value in surface_summary.items():
        lines.append(f"- {key}: `{value}`")
    if surface_alignment:
        lines.extend(
            [
                "",
                "## Current consumer-surface audit",
                "",
                f"- JSON: `{surface_alignment.get('json', '')}`",
                f"- Markdown: `{surface_alignment.get('markdown', '')}`",
                f"- Console: `{surface_alignment.get('console', '')}`",
                f"- Status: `{surface_alignment.get('status', '')}`",
                f"- Checks: `{surface_alignment.get('checked_check_count', '')}`",
                f"- Drift checks: `{surface_alignment.get('drift_check_count', '')}`",
            ]
        )
    if surface_health:
        lines.extend(
            [
                "",
                "## Current surface health snapshot",
                "",
                f"- JSON: `{surface_health.get('json', '')}`",
                f"- Markdown: `{surface_health.get('markdown', '')}`",
                f"- Console: `{surface_health.get('console', '')}`",
                f"- Status: `{surface_health.get('status', '')}`",
                f"- Summary: `{surface_health.get('summary_text', '')}`",
                f"- Checks: `{surface_health.get('checked_check_count', '')}`",
                f"- Drift checks: `{surface_health.get('drift_check_count', '')}`",
            ]
        )
    if notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in notes)
    lines.append("")
    return "\n".join(lines)



def _require_mapping(payload: Mapping[str, Any], key: str, path: Path) -> Mapping[str, Any]:
    mapping = _mapping(payload.get(key))
    if mapping:
        return mapping
    raise SingleBaseDeliveryEntrypointsError(f"{path} does not contain a {key} mapping")



def _require_string(mapping: Mapping[str, Any], key: str, *, context: str) -> str:
    value = str(mapping.get(key, "")).strip()
    if value:
        return value
    raise SingleBaseDeliveryEntrypointsError(f"{context} is missing {key}")



def _require_int(mapping: Mapping[str, Any], key: str, *, context: str) -> int:
    value = mapping.get(key)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SingleBaseDeliveryEntrypointsError(f"{context} is missing integer {key}") from exc



def _require_repo_file(
    project_root: Path,
    relative_or_absolute_path: str,
    *,
    context: str,
    require_file: bool = True,
) -> _ResolvedPathRef:
    candidate = _resolve_repo_path(project_root, Path(relative_or_absolute_path))
    if require_file:
        if not candidate.is_file():
            raise SingleBaseDeliveryEntrypointsError(f"{context} is missing: {candidate}")
    else:
        if not candidate.exists():
            raise SingleBaseDeliveryEntrypointsError(f"{context} is missing: {candidate}")
    return _ResolvedPathRef(display=_display_repo_path(project_root, candidate), path=candidate)



def _resolve_output_relative_file(project_root: Path, base_dir: Path, relative_path: str, *, context: str) -> _ResolvedPathRef:
    candidate = (base_dir / relative_path).resolve()
    if not candidate.exists():
        raise SingleBaseDeliveryEntrypointsError(f"{context} is missing: {candidate}")
    return _ResolvedPathRef(display=_display_repo_path(project_root, candidate), path=candidate)



def _resolve_repo_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()



def _resolve_output_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()



def _display_repo_path(project_root: Path, path: Path) -> str:
    resolved_path = Path(path).resolve()
    try:
        return resolved_path.relative_to(project_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()



def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}



def _atomic_write_text(path: Path, text: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(destination.parent),
        delete=False,
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    try:
        os.replace(temp_path, destination)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise



def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
