"""Static viewer bundle builder for the active IndustrialPlanner single-base delivery release.

This helper resolves the checked-in current-release pointer, copies the active
release artifacts into a compact browser-consumable bundle, and materializes the
minimum viewer-side geometry payload required to inspect the release-associated canonical blueprint
without widening the support contract.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any, Mapping, Sequence

from src.io.output_schema import normalize_blueprint_payload
from src.io.serializer import (
    build_pose_lookup,
    coerce_facility_pools_payload,
    load_json_mapping,
    pose_lookup_key,
    recover_legacy_render_payload_from_blueprint,
)
from src.render.report_builder import (
    VIEWER_REPORT_FILENAME,
    build_viewer_report_from_blueprint_payload,
    write_viewer_report,
)
from src.search.exact_campaign import atomic_write_json

_VIEWER_MANIFEST_FILENAME = "release_viewer_manifest.json"
_VIEWER_MANIFEST_SOURCE = "industrial_planner_single_base_delivery_viewer_v1"
_VIEWER_MANIFEST_VERSION = "1.0.0"

_DEFAULT_POINTER_JSON = Path("data/examples/industrial_planner/active_single_base_delivery_release.json")
_DEFAULT_CANDIDATE_PLACEMENTS_JSON = Path("data/preprocessed/candidate_placements.json")
_DEFAULT_RULES_JSON = Path("rules/canonical_rules.json")
_DEFAULT_VIEWER_HTML = Path("src/render/web_viewer/index.html")
_DEFAULT_OUTPUT_DIR = Path(".artifacts/industrial_planner_single_base_delivery_viewer")

_RELEASE_DOWNLOAD_ROOT = Path("downloads/release")
_META_DOWNLOAD_ROOT = Path("downloads/meta")

_STAGE_GROUPS: dict[str, tuple[str, str]] = {
    "planning": ("canonical_provenance", "Canonical provenance"),
    "export": ("delivery_entrypoints", "Delivery entrypoints"),
    "validator": ("delivery_entrypoints", "Delivery entrypoints"),
    "throughput": ("delivery_entrypoints", "Delivery entrypoints"),
    "support_reports": ("support_reports", "Support reports"),
    "checked_in_support_suite": ("gate_summaries", "Gate summaries"),
    "checked_artifact_gate": ("gate_summaries", "Gate summaries"),
    "run_summary": ("delivery_entrypoints", "Delivery entrypoints"),
}

_GROUP_ORDER = (
    "delivery_entrypoints",
    "support_reports",
    "gate_summaries",
    "canonical_provenance",
    "metadata",
)

_GROUP_DESCRIPTIONS: dict[str, str] = {
    "delivery_entrypoints": "Primary delivery artifacts reviewers usually need first.",
    "support_reports": "Fresh single-base support surfaces that remain in-scope for the active contract.",
    "gate_summaries": "Checked-in inventory/gate verdicts proving the active support surface is still clean.",
    "canonical_provenance": "Canonical regeneration inputs and planning reports preserved for reproducibility.",
    "metadata": "Pointer/manifest/checksum files plus viewer-side metadata for this current release bundle.",
}


class SingleBaseDeliveryViewerBundleError(RuntimeError):
    """Raised when the active delivery release cannot be materialized as a viewer bundle."""


@dataclass(frozen=True)
class SingleBaseDeliveryViewerBundleResult:
    release_id: str
    base_id: str
    lot_size: int
    delivery_status: str
    output_dir: Path
    pointer_json_path: Path
    release_manifest_path: Path
    selected_facility_type_count: int
    selected_pose_count: int
    payload_download_count: int
    metadata_download_count: int
    quick_download_count: int
    exact_full_scale_certified_status: str

    @property
    def viewer_manifest_path(self) -> Path:
        return self.output_dir / _VIEWER_MANIFEST_FILENAME

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "base_id": self.base_id,
            "lot_size": self.lot_size,
            "delivery_status": self.delivery_status,
            "output_dir": str(self.output_dir),
            "pointer_json_path": str(self.pointer_json_path),
            "release_manifest_path": str(self.release_manifest_path),
            "selected_facility_type_count": self.selected_facility_type_count,
            "selected_pose_count": self.selected_pose_count,
            "payload_download_count": self.payload_download_count,
            "metadata_download_count": self.metadata_download_count,
            "quick_download_count": self.quick_download_count,
            "exact_full_scale_certified_status": self.exact_full_scale_certified_status,
            "viewer_manifest_path": str(self.viewer_manifest_path),
        }


@dataclass(frozen=True)
class _CopiedFile:
    label: str
    href: str
    source_path: Path
    output_path: Path
    kind: str
    stage: str | None = None
    required_for_delivery: bool | None = None
    role: str | None = None
    sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "label": self.label,
            "href": self.href,
            "source_path": str(self.source_path),
            "output_path": str(self.output_path),
            "kind": self.kind,
        }
        if self.stage is not None:
            payload["stage"] = self.stage
        if self.required_for_delivery is not None:
            payload["required_for_delivery"] = bool(self.required_for_delivery)
        if self.role is not None:
            payload["role"] = self.role
        if self.sha256 is not None:
            payload["sha256"] = self.sha256
        return payload


@dataclass(frozen=True)
class _ViewerPoolsBuild:
    payload: dict[str, Any]
    selected_facility_type_count: int
    selected_pose_count: int


def build_single_base_delivery_viewer_bundle(
    *,
    project_root: Path,
    pointer_json_path: Path = _DEFAULT_POINTER_JSON,
    output_dir: Path = _DEFAULT_OUTPUT_DIR,
    candidate_placements_path: Path = _DEFAULT_CANDIDATE_PLACEMENTS_JSON,
    rules_json_path: Path = _DEFAULT_RULES_JSON,
    viewer_html_path: Path = _DEFAULT_VIEWER_HTML,
) -> SingleBaseDeliveryViewerBundleResult:
    project_root = Path(project_root).resolve()
    pointer_json_path = _resolve_repo_path(project_root, pointer_json_path)
    candidate_placements_path = _resolve_repo_path(project_root, candidate_placements_path)
    rules_json_path = _resolve_repo_path(project_root, rules_json_path)
    viewer_html_path = _resolve_repo_path(project_root, viewer_html_path)
    output_dir = _resolve_output_path(project_root, output_dir)

    pointer_payload = load_json_mapping(pointer_json_path)
    current_release = _mapping(pointer_payload.get("current_release"))
    if not current_release:
        raise SingleBaseDeliveryViewerBundleError(
            f"pointer {pointer_json_path} does not contain a current_release mapping"
        )

    release_manifest_display = current_release.get("release_manifest_json")
    if not isinstance(release_manifest_display, str) or not release_manifest_display:
        raise SingleBaseDeliveryViewerBundleError(
            f"pointer {pointer_json_path} does not declare current_release.release_manifest_json"
        )
    release_manifest_path = _resolve_repo_path(project_root, Path(release_manifest_display))
    release_manifest_payload = load_json_mapping(release_manifest_path)

    release_info = _mapping(release_manifest_payload.get("release"))
    delivery_status = str(release_info.get("delivery_status", ""))
    if delivery_status != "ready_for_single_base_delivery":
        raise SingleBaseDeliveryViewerBundleError(
            "viewer bundle build requires a ready_for_single_base_delivery release manifest"
        )

    canonical_blueprint_path = _resolve_release_canonical_blueprint_path(
        project_root=project_root,
        release_manifest_payload=release_manifest_payload,
    )
    blueprint_payload = normalize_blueprint_payload(load_json_mapping(canonical_blueprint_path))

    full_candidate_placements_payload = load_json_mapping(candidate_placements_path)
    rules_payload = load_json_mapping(rules_json_path)
    viewer_pools_build = _build_minimal_viewer_pools(
        blueprint_payload=blueprint_payload,
        candidate_placements_payload=full_candidate_placements_payload,
        rules_payload=rules_payload,
    )
    legacy_payload = recover_legacy_render_payload_from_blueprint(
        blueprint_payload=blueprint_payload,
        facility_pools=viewer_pools_build.payload,
    )
    viewer_report_payload = build_viewer_report_from_blueprint_payload(
        blueprint_payload=blueprint_payload,
        facility_pools=viewer_pools_build.payload,
        rules_payload=rules_payload,
    )

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(viewer_html_path, output_dir / "index.html")
    atomic_write_json(output_dir / "optimal_blueprint.json", blueprint_payload)
    atomic_write_json(output_dir / "candidate_placements.json", viewer_pools_build.payload)
    atomic_write_json(output_dir / "final_solution.json", legacy_payload)
    write_viewer_report(output_dir / VIEWER_REPORT_FILENAME, viewer_report_payload)

    payload_downloads, quick_downloads = _copy_release_payload_artifacts(
        project_root=project_root,
        release_manifest_payload=release_manifest_payload,
        output_dir=output_dir,
    )
    metadata_downloads = _copy_metadata_artifacts(
        project_root=project_root,
        output_dir=output_dir,
        pointer_json_path=pointer_json_path,
        pointer_payload=pointer_payload,
        release_manifest_path=release_manifest_path,
        release_manifest_payload=release_manifest_payload,
    )

    viewer_manifest_payload = _build_viewer_manifest_payload(
        output_dir=output_dir,
        pointer_json_path=pointer_json_path,
        current_release=current_release,
        release_manifest_payload=release_manifest_payload,
        payload_downloads=payload_downloads,
        metadata_downloads=metadata_downloads,
        quick_downloads=quick_downloads,
        viewer_pools_build=viewer_pools_build,
    )
    atomic_write_json(output_dir / _VIEWER_MANIFEST_FILENAME, viewer_manifest_payload)

    exact_full_scale_certified = _mapping(release_manifest_payload.get("exact_full_scale_certified"))
    return SingleBaseDeliveryViewerBundleResult(
        release_id=str(release_info.get("release_id", current_release.get("release_id", "unknown_release"))),
        base_id=str(release_info.get("base_id", current_release.get("base_id", "unknown_base"))),
        lot_size=int(release_info.get("lot_size", current_release.get("lot_size", 0))),
        delivery_status=delivery_status,
        output_dir=output_dir,
        pointer_json_path=pointer_json_path,
        release_manifest_path=release_manifest_path,
        selected_facility_type_count=viewer_pools_build.selected_facility_type_count,
        selected_pose_count=viewer_pools_build.selected_pose_count,
        payload_download_count=len(payload_downloads),
        metadata_download_count=len(metadata_downloads),
        quick_download_count=len(quick_downloads),
        exact_full_scale_certified_status=str(exact_full_scale_certified.get("status", "unknown")),
    )


def _resolve_release_canonical_blueprint_path(
    *,
    project_root: Path,
    release_manifest_payload: Mapping[str, Any],
) -> Path:
    artifacts_raw = release_manifest_payload.get("artifacts")
    artifacts = list(artifacts_raw) if isinstance(artifacts_raw, Sequence) else []
    for artifact in artifacts:
        artifact_entry = _mapping(artifact)
        if str(artifact_entry.get("artifact_id", "")) != "canonical_fixture":
            continue
        release_path_display = artifact_entry.get("release_path")
        if not isinstance(release_path_display, str) or not release_path_display:
            break
        return _resolve_repo_path(project_root, Path(release_path_display))
    raise SingleBaseDeliveryViewerBundleError(
        "release manifest does not expose the canonical_fixture artifact required for viewer rendering"
    )



def _build_minimal_viewer_pools(
    *,
    blueprint_payload: Mapping[str, Any],
    candidate_placements_payload: Mapping[str, Any],
    rules_payload: Mapping[str, Any],
) -> _ViewerPoolsBuild:
    normalized_blueprint = normalize_blueprint_payload(blueprint_payload)
    normalized_pools = coerce_facility_pools_payload(candidate_placements_payload)
    pose_lookup = build_pose_lookup(normalized_pools)
    facility_templates = _mapping(rules_payload.get("facility_templates"))

    selected_by_type: dict[str, dict[tuple[str, int, int, int, str], Mapping[str, Any]]] = {}
    for facility in normalized_blueprint.get("facilities", []):
        facility_type = str(facility.get("facility_type", ""))
        key = pose_lookup_key(
            facility_type=facility_type,
            anchor_x=int((facility.get("anchor") or {}).get("x", 0)),
            anchor_y=int((facility.get("anchor") or {}).get("y", 0)),
            orientation=int(facility.get("orientation", 0)),
            port_mode=str(facility.get("port_mode", "default")),
        )
        matches = pose_lookup.get(key, ())
        if len(matches) == 1:
            _pose_idx, pose = matches[0]
            selected_pose = deepcopy(dict(pose))
        else:
            selected_pose = _synthesize_pose_from_blueprint(
                facility=facility,
                facility_templates=facility_templates,
            )
        selected_by_type.setdefault(facility_type, {})[key] = selected_pose

    minimal_pools = {
        "facility_pools": {
            facility_type: [
                selected_by_type[facility_type][key]
                for key in sorted(selected_by_type[facility_type].keys(), key=lambda item: item[1:])
            ]
            for facility_type in sorted(selected_by_type.keys())
        }
    }
    selected_pose_count = sum(len(pool) for pool in minimal_pools["facility_pools"].values())
    return _ViewerPoolsBuild(
        payload=minimal_pools,
        selected_facility_type_count=len(minimal_pools["facility_pools"]),
        selected_pose_count=selected_pose_count,
    )


def _synthesize_pose_from_blueprint(
    *,
    facility: Mapping[str, Any],
    facility_templates: Mapping[str, Any],
) -> dict[str, Any]:
    facility_type = str(facility.get("facility_type", ""))
    template = _mapping(facility_templates.get(facility_type))
    dimensions = _mapping(template.get("dimensions"))
    if not dimensions:
        raise SingleBaseDeliveryViewerBundleError(
            "viewer bundle cannot synthesize geometry for facility type "
            f"{facility_type!r}: rules.facility_templates dimensions are missing"
        )
    base_w = int(dimensions.get("w", 0))
    base_h = int(dimensions.get("h", 0))
    if base_w <= 0 or base_h <= 0:
        raise SingleBaseDeliveryViewerBundleError(
            "viewer bundle cannot synthesize geometry for facility type "
            f"{facility_type!r}: invalid dimensions {dimensions!r}"
        )

    orientation = int(facility.get("orientation", 0))
    width, height = (base_h, base_w) if orientation % 2 == 1 else (base_w, base_h)
    anchor = _mapping(facility.get("anchor"))
    anchor_x = int(anchor.get("x", 0))
    anchor_y = int(anchor.get("y", 0))
    active_ports = list(facility.get("active_ports") or [])

    return {
        "pose_id": f"viewer::{facility.get('instance_id', facility_type)}",
        "anchor": {"x": anchor_x, "y": anchor_y},
        "pose_params": {
            "orientation": orientation,
            "port_mode": str(facility.get("port_mode", "default")),
        },
        "occupied_cells": [
            [x, y]
            for y in range(anchor_y, anchor_y + height)
            for x in range(anchor_x, anchor_x + width)
        ],
        "input_port_cells": [
            {
                "x": int(port.get("x", 0)),
                "y": int(port.get("y", 0)),
                "dir": str(port.get("dir", "N")),
                "commodity": str(port.get("commodity", "[TBD]")),
            }
            for port in active_ports
            if str(port.get("type", "")) == "input"
        ],
        "output_port_cells": [
            {
                "x": int(port.get("x", 0)),
                "y": int(port.get("y", 0)),
                "dir": str(port.get("dir", "N")),
                "commodity": str(port.get("commodity", "[TBD]")),
            }
            for port in active_ports
            if str(port.get("type", "")) == "output"
        ],
        "power_coverage_cells": None,
    }



def _copy_release_payload_artifacts(
    *,
    project_root: Path,
    release_manifest_payload: Mapping[str, Any],
    output_dir: Path,
) -> tuple[list[_CopiedFile], list[dict[str, Any]]]:
    artifacts_raw = release_manifest_payload.get("artifacts")
    artifacts = list(artifacts_raw) if isinstance(artifacts_raw, Sequence) else []
    copied: list[_CopiedFile] = []
    quick_downloads: list[dict[str, Any]] = []
    delivery_entrypoints = _mapping(release_manifest_payload.get("delivery_entrypoints"))

    for artifact in artifacts:
        artifact_entry = _mapping(artifact)
        release_path_display = artifact_entry.get("release_path")
        if not isinstance(release_path_display, str) or not release_path_display:
            continue
        source_path = _resolve_repo_path(project_root, Path(release_path_display))
        relative_path = artifact_entry.get("relative_path")
        if isinstance(relative_path, str) and relative_path:
            target_relative = _RELEASE_DOWNLOAD_ROOT / Path(relative_path)
        else:
            target_relative = _RELEASE_DOWNLOAD_ROOT / source_path.name
        output_path = output_dir / target_relative
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, output_path)

        copied_file = _CopiedFile(
            label=str(artifact_entry.get("artifact_id", output_path.name)),
            href=target_relative.as_posix(),
            source_path=source_path,
            output_path=output_path,
            kind=_infer_file_kind(output_path),
            stage=str(artifact_entry.get("stage", "")) or None,
            required_for_delivery=bool(artifact_entry.get("required_for_delivery")),
            role=str(artifact_entry.get("role", "")) or None,
            sha256=str(artifact_entry.get("sha256", "")) or None,
        )
        copied.append(copied_file)

        artifact_id = str(artifact_entry.get("artifact_id", ""))
        if artifact_id in _quick_entrypoint_artifact_ids(delivery_entrypoints):
            quick_downloads.append(
                {
                    "id": artifact_id,
                    "label": _quick_label_from_artifact_id(artifact_id),
                    "href": copied_file.href,
                    "kind": copied_file.kind,
                    "stage": copied_file.stage,
                    "required_for_delivery": copied_file.required_for_delivery,
                    "role": copied_file.role,
                }
            )

    return copied, quick_downloads


def _copy_metadata_artifacts(
    *,
    project_root: Path,
    output_dir: Path,
    pointer_json_path: Path,
    pointer_payload: Mapping[str, Any],
    release_manifest_path: Path,
    release_manifest_payload: Mapping[str, Any],
) -> list[_CopiedFile]:
    copied: list[_CopiedFile] = []
    generated_files = _mapping(release_manifest_payload.get("generated_files"))

    def _copy_meta(source_path: Path, target_relative: Path, label: str) -> None:
        output_path = output_dir / target_relative
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, output_path)
        copied.append(
            _CopiedFile(
                label=label,
                href=target_relative.as_posix(),
                source_path=source_path,
                output_path=output_path,
                kind=_infer_file_kind(output_path),
                stage="metadata",
            )
        )

    _copy_meta(pointer_json_path, _META_DOWNLOAD_ROOT / pointer_json_path.name, "current_release_pointer_json")

    pointer_paths = _mapping(pointer_payload.get("pointer_paths"))
    pointer_markdown_display = pointer_paths.get("markdown")
    if isinstance(pointer_markdown_display, str) and pointer_markdown_display:
        pointer_markdown_path = _resolve_repo_path(project_root, Path(pointer_markdown_display))
        _copy_meta(pointer_markdown_path, _META_DOWNLOAD_ROOT / pointer_markdown_path.name, "current_release_pointer_markdown")

    _copy_meta(release_manifest_path, _META_DOWNLOAD_ROOT / release_manifest_path.name, "release_manifest_json")

    release_manifest_markdown_display = generated_files.get("release_manifest_markdown")
    if isinstance(release_manifest_markdown_display, str) and release_manifest_markdown_display:
        release_manifest_markdown_path = _resolve_repo_path(project_root, Path(release_manifest_markdown_display))
        _copy_meta(
            release_manifest_markdown_path,
            _META_DOWNLOAD_ROOT / release_manifest_markdown_path.name,
            "release_manifest_markdown",
        )

    sha256sums_display = generated_files.get("sha256sums")
    if isinstance(sha256sums_display, str) and sha256sums_display:
        sha256sums_path = _resolve_repo_path(project_root, Path(sha256sums_display))
        _copy_meta(sha256sums_path, _META_DOWNLOAD_ROOT / sha256sums_path.name, "sha256sums")

    release_index_json_display = generated_files.get("release_index_json")
    if isinstance(release_index_json_display, str) and release_index_json_display:
        release_index_json_path = _resolve_repo_path(project_root, Path(release_index_json_display))
        _copy_meta(release_index_json_path, _META_DOWNLOAD_ROOT / release_index_json_path.name, "release_index_json")

    release_index_markdown_display = generated_files.get("release_index_markdown")
    if isinstance(release_index_markdown_display, str) and release_index_markdown_display:
        release_index_markdown_path = _resolve_repo_path(project_root, Path(release_index_markdown_display))
        _copy_meta(
            release_index_markdown_path,
            _META_DOWNLOAD_ROOT / release_index_markdown_path.name,
            "release_index_markdown",
        )

    return copied


def _build_viewer_manifest_payload(
    *,
    output_dir: Path,
    pointer_json_path: Path,
    current_release: Mapping[str, Any],
    release_manifest_payload: Mapping[str, Any],
    payload_downloads: Sequence[_CopiedFile],
    metadata_downloads: Sequence[_CopiedFile],
    quick_downloads: Sequence[Mapping[str, Any]],
    viewer_pools_build: _ViewerPoolsBuild,
) -> dict[str, Any]:
    release_info = _mapping(release_manifest_payload.get("release"))
    source_run = _mapping(release_manifest_payload.get("source_run"))
    exact_full_scale_certified = _mapping(release_manifest_payload.get("exact_full_scale_certified"))

    download_groups = _group_downloads(
        payload_downloads=payload_downloads,
        metadata_downloads=metadata_downloads,
    )

    return {
        "metadata": {
            "schema_version": _VIEWER_MANIFEST_VERSION,
            "generated_at": _now_iso(),
            "source": _VIEWER_MANIFEST_SOURCE,
        },
        "current_release": {
            "release_id": str(release_info.get("release_id", current_release.get("release_id", "unknown_release"))),
            "base_id": str(release_info.get("base_id", current_release.get("base_id", "unknown_base"))),
            "lot_size": int(release_info.get("lot_size", current_release.get("lot_size", 0))),
            "delivery_status": str(release_info.get("delivery_status", current_release.get("delivery_status", "unknown"))),
            "release_dir": str(release_info.get("release_dir", current_release.get("release_dir", ""))),
            "scope_note": str(release_info.get("scope_note", current_release.get("scope_note", ""))),
        },
        "source_run": dict(source_run),
        "exact_full_scale_certified": dict(exact_full_scale_certified),
        "viewer_bundle": {
            "output_dir": str(output_dir),
            "pointer_json_path": str(pointer_json_path),
            "asset_paths": {
                "index_html": "index.html",
                "optimal_blueprint": "optimal_blueprint.json",
                "candidate_placements": "candidate_placements.json",
                "final_solution": "final_solution.json",
                "viewer_report": VIEWER_REPORT_FILENAME,
                "viewer_manifest": _VIEWER_MANIFEST_FILENAME,
            },
            "selected_facility_type_count": viewer_pools_build.selected_facility_type_count,
            "selected_pose_count": viewer_pools_build.selected_pose_count,
        },
        "quick_downloads": list(quick_downloads),
        "download_groups": download_groups,
        "payload_artifacts": [copied.to_dict() for copied in payload_downloads],
        "metadata_downloads": [copied.to_dict() for copied in metadata_downloads],
        "notes": [
            str(release_info.get("scope_note", current_release.get("scope_note", ""))),
            str(exact_full_scale_certified.get("note", "")),
        ],
    }


def _group_downloads(
    *,
    payload_downloads: Sequence[_CopiedFile],
    metadata_downloads: Sequence[_CopiedFile],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for group_id in _GROUP_ORDER:
        grouped[group_id] = {
            "group_id": group_id,
            "title": _group_title(group_id),
            "description": _GROUP_DESCRIPTIONS.get(group_id, ""),
            "entries": [],
        }

    for copied in payload_downloads:
        group_id, _group_title_value = _STAGE_GROUPS.get(copied.stage or "", ("canonical_provenance", "Canonical provenance"))
        grouped[group_id]["entries"].append(
            {
                "label": copied.label,
                "href": copied.href,
                "kind": copied.kind,
                "stage": copied.stage,
                "required_for_delivery": copied.required_for_delivery,
                "role": copied.role,
                "sha256": copied.sha256,
            }
        )

    for copied in metadata_downloads:
        grouped["metadata"]["entries"].append(
            {
                "label": copied.label,
                "href": copied.href,
                "kind": copied.kind,
                "stage": copied.stage,
                "required_for_delivery": False,
                "role": copied.role,
                "sha256": copied.sha256,
            }
        )

    ordered_groups: list[dict[str, Any]] = []
    for group_id in _GROUP_ORDER:
        entries = grouped[group_id]["entries"]
        if not entries:
            continue
        entries.sort(key=lambda item: (str(item.get("stage", "")), str(item.get("label", ""))))
        ordered_groups.append(grouped[group_id])
    return ordered_groups


def _group_title(group_id: str) -> str:
    for _stage, group in _STAGE_GROUPS.items():
        if group[0] == group_id:
            return group[1]
    if group_id == "metadata":
        return "Metadata"
    return group_id.replace("_", " ").title()


def _quick_entrypoint_artifact_ids(delivery_entrypoints: Mapping[str, Any]) -> set[str]:
    mapping: dict[str, str] = {
        "blueprint": "industrial_planner_blueprint",
        "compatibility_manifest": "industrial_planner_compatibility_manifest",
        "validation_report": "validation_report_json",
        "throughput_report": "throughput_report_json",
        "run_summary": "run_summary_json",
    }
    return {
        artifact_id
        for entrypoint_key, artifact_id in mapping.items()
        if isinstance(delivery_entrypoints.get(entrypoint_key), str)
    }


def _quick_label_from_artifact_id(artifact_id: str) -> str:
    labels = {
        "industrial_planner_blueprint": "Blueprint",
        "industrial_planner_compatibility_manifest": "Compatibility manifest",
        "validation_report_json": "Validation report",
        "throughput_report_json": "Throughput report",
        "run_summary_json": "Run summary",
    }
    return labels.get(artifact_id, artifact_id)


def _resolve_repo_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    resolved = candidate if candidate.is_absolute() else project_root / candidate
    resolved = resolved.resolve()
    if not resolved.exists():
        raise SingleBaseDeliveryViewerBundleError(f"required path does not exist: {resolved}")
    return resolved


def _resolve_output_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    return (candidate if candidate.is_absolute() else project_root / candidate).resolve()


def _mapping(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _infer_file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".md":
        return "markdown"
    if suffix == ".txt":
        return "text"
    if suffix == ".html":
        return "html"
    return suffix.lstrip(".") or "file"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
