"""Versioned delivery release builder for the active IndustrialPlanner single-base contract.

This script packages a delivery-ready run from
`scripts/run_industrial_planner_single_base_e2e.py` into one versioned release
bundle, writes a fixed release manifest plus checksums, refreshes a
human/machine-readable pointer to the currently active single-base delivery
release, and can refresh the matching checked-in current-viewer bundle/pointer
for the same release id. It intentionally stays within the active
`valley4_protocol_core` 70×70 contract and does not reactivate any
`future_scope` bases.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_industrial_planner_single_base_e2e import run_single_base_e2e_workflow  # noqa: E402
from src.render.industrial_planner_single_base_delivery_landing import (  # noqa: E402
    SingleBaseDeliveryLandingBundleError,
    build_single_base_delivery_landing_bundle,
)
from src.render.industrial_planner_single_base_delivery_frontdoor import (  # noqa: E402
    SingleBaseDeliveryFrontdoorError,
    build_single_base_delivery_frontdoor,
)
from src.render.industrial_planner_single_base_delivery_entrypoints import (  # noqa: E402
    SingleBaseDeliveryEntrypointsError,
    build_single_base_delivery_entrypoints,
)
from src.render.industrial_planner_single_base_delivery_surface_alignment import (  # noqa: E402
    SingleBaseDeliverySurfaceAlignmentError,
    build_single_base_delivery_surface_alignment_result,
    write_single_base_delivery_surface_alignment_outputs,
)
from src.render.industrial_planner_single_base_delivery_surface_health import (  # noqa: E402
    SingleBaseDeliverySurfaceHealthError,
    build_single_base_delivery_surface_health,
)
from src.render.industrial_planner_single_base_delivery_viewer import (  # noqa: E402
    SingleBaseDeliveryViewerBundleError,
    build_single_base_delivery_viewer_bundle,
)
from src.adapters.industrial_planner import DEFAULT_BASE_ID  # noqa: E402
from src.search.exact_campaign import atomic_write_json, now_iso, sha256_file  # noqa: E402

_ACTIVE_LOT_SIZE = 70
_RELEASE_SCHEMA_VERSION = "1.0.0"
_RELEASE_SOURCE = "industrial_planner_single_base_delivery_release_v1"
_POINTER_SOURCE = "industrial_planner_single_base_delivery_pointer_v1"
_INDEX_SOURCE = "industrial_planner_single_base_delivery_release_index_v1"
_RELEASE_MANIFEST_JSON_FILENAME = "release_manifest.json"
_RELEASE_MANIFEST_MARKDOWN_FILENAME = "release_manifest.md"
_SHA256SUMS_FILENAME = "SHA256SUMS.txt"
_DEFAULT_SOURCE_RUN_DIR = PROJECT_ROOT / ".artifacts" / "industrial_planner_single_base_e2e"
_DEFAULT_RELEASE_ROOT = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "releases"
_DEFAULT_POINTER_JSON_PATH = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_release.json"
)
_DEFAULT_POINTER_MARKDOWN_PATH = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_release.md"
)
_DEFAULT_INDEX_JSON_PATH = _DEFAULT_RELEASE_ROOT / "release_index.json"
_DEFAULT_INDEX_MARKDOWN_PATH = _DEFAULT_RELEASE_ROOT / "release_index.md"
_DEFAULT_VIEWER_ROOT = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "viewers"
_DEFAULT_VIEWER_POINTER_JSON_PATH = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_viewer.json"
)
_DEFAULT_VIEWER_POINTER_MARKDOWN_PATH = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "active_single_base_delivery_viewer.md"
)
_DEFAULT_VIEWER_INDEX_JSON_PATH = _DEFAULT_VIEWER_ROOT / "viewer_index.json"
_DEFAULT_VIEWER_INDEX_MARKDOWN_PATH = _DEFAULT_VIEWER_ROOT / "viewer_index.md"
_DEFAULT_VIEWER_CANDIDATE_PLACEMENTS_PATH = PROJECT_ROOT / "data" / "preprocessed" / "candidate_placements.json"
_DEFAULT_VIEWER_RULES_JSON_PATH = PROJECT_ROOT / "rules" / "canonical_rules.json"
_DEFAULT_VIEWER_HTML_PATH = PROJECT_ROOT / "src" / "render" / "web_viewer" / "index.html"
_DEFAULT_LANDING_OUTPUT_DIR = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "current_delivery"
_DEFAULT_FRONTDOOR_OUTPUT_DIR = PROJECT_ROOT / "data" / "examples" / "industrial_planner"
_ENTRYPOINTS_JSON_FILENAME = "active_single_base_delivery_entrypoints.json"
_ENTRYPOINTS_MARKDOWN_FILENAME = "active_single_base_delivery_entrypoints.md"
_DEFAULT_SURFACE_ALIGNMENT_JSON_PATH = (
    PROJECT_ROOT / ".artifacts" / "industrial_planner_single_base_delivery_surface_alignment" / "surface_alignment_summary.json"
)
_DEFAULT_SURFACE_ALIGNMENT_MARKDOWN_PATH = (
    PROJECT_ROOT / ".artifacts" / "industrial_planner_single_base_delivery_surface_alignment" / "surface_alignment_summary.md"
)
_DEFAULT_SURFACE_ALIGNMENT_CONSOLE_PATH = (
    PROJECT_ROOT / ".artifacts" / "industrial_planner_single_base_delivery_surface_alignment" / "surface_alignment_summary.txt"
)
_DEFAULT_SURFACE_HEALTH_JSON_PATH = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "current_surface_health.json"
)
_DEFAULT_SURFACE_HEALTH_MARKDOWN_PATH = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "current_surface_health.md"
)
_DEFAULT_SURFACE_HEALTH_CONSOLE_PATH = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "current_surface_health.txt"
)
_SCOPE_NOTE = (
    "Current release scope is intentionally limited to the active IndustrialPlanner contract "
    "`valley4_protocol_core` (70×70). Other bases and the outer-deployment path remain preserved "
    "as `future_scope` and are not widened by this release builder."
)
_VIEWER_POINTER_SOURCE = "industrial_planner_single_base_delivery_viewer_pointer_v1"
_VIEWER_INDEX_SOURCE = "industrial_planner_single_base_delivery_viewer_index_v1"
_VIEWER_MANIFEST_JSON_FILENAME = "release_viewer_manifest.json"
_FRONTDOOR_MANIFEST_JSON_FILENAME = "frontdoor_manifest.json"
_FRONTDOOR_INDEX_HTML_FILENAME = "index.html"
_LATEST_BUNDLE_ZIP_FILENAME = "industrial_planner_latest_single_base_delivery_bundle.zip"
_LATEST_BUNDLE_POINTER_JSON_FILENAME = "latest_single_base_delivery_bundle.json"
_LATEST_BUNDLE_POINTER_MARKDOWN_FILENAME = "latest_single_base_delivery_bundle.md"


class SingleBaseDeliveryReleaseError(RuntimeError):
    """Raised when a versioned release cannot be produced safely."""


@dataclass(frozen=True)
class ReleaseSourceFileSpec:
    relative_path: str
    artifact_id: str
    stage: str
    role: str
    required_for_delivery: bool = True


@dataclass(frozen=True)
class ReleasedArtifact:
    artifact_id: str
    stage: str
    role: str
    required_for_delivery: bool
    relative_path: str
    source_path: Path
    release_path: Path
    sha256: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "stage": self.stage,
            "role": self.role,
            "required_for_delivery": self.required_for_delivery,
            "relative_path": self.relative_path,
            "source_path": _display_path(self.source_path),
            "release_path": _display_path(self.release_path),
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class SingleBaseDeliveryReleaseResult:
    release_id: str
    base_id: str
    source_run_dir: Path
    release_dir: Path
    release_manifest_json_path: Path
    release_manifest_markdown_path: Path
    sha256sums_path: Path
    pointer_json_path: Path
    pointer_markdown_path: Path
    index_json_path: Path | None
    index_markdown_path: Path | None
    delivery_status: str
    exact_full_scale_certified_status: str
    payload_artifact_count: int
    required_payload_artifact_count: int
    viewer_bundle_status: str = "skipped"
    viewer_output_dir: Path | None = None
    viewer_manifest_path: Path | None = None
    viewer_pointer_json_path: Path | None = None
    viewer_pointer_markdown_path: Path | None = None
    viewer_index_json_path: Path | None = None
    viewer_index_markdown_path: Path | None = None
    viewer_selected_facility_type_count: int | None = None
    viewer_selected_pose_count: int | None = None
    viewer_payload_download_count: int | None = None
    viewer_metadata_download_count: int | None = None
    viewer_quick_download_count: int | None = None
    landing_bundle_status: str = "skipped"
    landing_output_dir: Path | None = None
    landing_manifest_path: Path | None = None
    landing_index_html_path: Path | None = None
    landing_quick_download_count: int | None = None
    landing_download_group_count: int | None = None
    frontdoor_bundle_status: str = "skipped"
    frontdoor_output_dir: Path | None = None
    frontdoor_manifest_path: Path | None = None
    frontdoor_index_html_path: Path | None = None
    frontdoor_quick_download_count: int | None = None
    frontdoor_download_group_count: int | None = None
    entrypoints_bundle_status: str = "skipped"
    entrypoints_json_path: Path | None = None
    entrypoints_markdown_path: Path | None = None
    entrypoints_action_count: int | None = None
    entrypoints_group_count: int | None = None
    surface_alignment_status: str = "skipped"
    surface_alignment_json_path: Path | None = None
    surface_alignment_markdown_path: Path | None = None
    surface_alignment_console_path: Path | None = None
    surface_alignment_check_count: int | None = None
    surface_alignment_drift_check_count: int | None = None
    surface_health_status: str = "skipped"
    surface_health_json_path: Path | None = None
    surface_health_markdown_path: Path | None = None
    surface_health_console_path: Path | None = None
    surface_health_check_count: int | None = None
    surface_health_drift_check_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "base_id": self.base_id,
            "source_run_dir": _display_path(self.source_run_dir),
            "release_dir": _display_path(self.release_dir),
            "release_manifest_json_path": _display_path(self.release_manifest_json_path),
            "release_manifest_markdown_path": _display_path(self.release_manifest_markdown_path),
            "sha256sums_path": _display_path(self.sha256sums_path),
            "pointer_json_path": _display_path(self.pointer_json_path),
            "pointer_markdown_path": _display_path(self.pointer_markdown_path),
            "index_json_path": _display_path(self.index_json_path) if self.index_json_path is not None else None,
            "index_markdown_path": _display_path(self.index_markdown_path) if self.index_markdown_path is not None else None,
            "delivery_status": self.delivery_status,
            "exact_full_scale_certified_status": self.exact_full_scale_certified_status,
            "payload_artifact_count": self.payload_artifact_count,
            "required_payload_artifact_count": self.required_payload_artifact_count,
            "viewer_bundle_status": self.viewer_bundle_status,
            "viewer_output_dir": _display_path(self.viewer_output_dir),
            "viewer_manifest_path": _display_path(self.viewer_manifest_path),
            "viewer_pointer_json_path": _display_path(self.viewer_pointer_json_path),
            "viewer_pointer_markdown_path": _display_path(self.viewer_pointer_markdown_path),
            "viewer_index_json_path": _display_path(self.viewer_index_json_path),
            "viewer_index_markdown_path": _display_path(self.viewer_index_markdown_path),
            "viewer_selected_facility_type_count": self.viewer_selected_facility_type_count,
            "viewer_selected_pose_count": self.viewer_selected_pose_count,
            "viewer_payload_download_count": self.viewer_payload_download_count,
            "viewer_metadata_download_count": self.viewer_metadata_download_count,
            "viewer_quick_download_count": self.viewer_quick_download_count,
            "landing_bundle_status": self.landing_bundle_status,
            "landing_output_dir": _display_path(self.landing_output_dir),
            "landing_manifest_path": _display_path(self.landing_manifest_path),
            "landing_index_html_path": _display_path(self.landing_index_html_path),
            "landing_quick_download_count": self.landing_quick_download_count,
            "landing_download_group_count": self.landing_download_group_count,
            "frontdoor_bundle_status": self.frontdoor_bundle_status,
            "frontdoor_output_dir": _display_path(self.frontdoor_output_dir),
            "frontdoor_manifest_path": _display_path(self.frontdoor_manifest_path),
            "frontdoor_index_html_path": _display_path(self.frontdoor_index_html_path),
            "frontdoor_quick_download_count": self.frontdoor_quick_download_count,
            "frontdoor_download_group_count": self.frontdoor_download_group_count,
            "entrypoints_bundle_status": self.entrypoints_bundle_status,
            "entrypoints_json_path": _display_path(self.entrypoints_json_path),
            "entrypoints_markdown_path": _display_path(self.entrypoints_markdown_path),
            "entrypoints_action_count": self.entrypoints_action_count,
            "entrypoints_group_count": self.entrypoints_group_count,
            "surface_alignment_status": self.surface_alignment_status,
            "surface_alignment_json_path": _display_path(self.surface_alignment_json_path),
            "surface_alignment_markdown_path": _display_path(self.surface_alignment_markdown_path),
            "surface_alignment_console_path": _display_path(self.surface_alignment_console_path),
            "surface_alignment_check_count": self.surface_alignment_check_count,
            "surface_alignment_drift_check_count": self.surface_alignment_drift_check_count,
            "surface_health_status": self.surface_health_status,
            "surface_health_json_path": _display_path(self.surface_health_json_path),
            "surface_health_markdown_path": _display_path(self.surface_health_markdown_path),
            "surface_health_console_path": _display_path(self.surface_health_console_path),
            "surface_health_check_count": self.surface_health_check_count,
            "surface_health_drift_check_count": self.surface_health_drift_check_count,
        }

    def to_console_text(self) -> str:
        lines = [
            "IndustrialPlanner single-base delivery release built successfully.",
            f"- release id: {self.release_id}",
            f"- base id: {self.base_id}",
            f"- source run dir: {_display_path(self.source_run_dir)}",
            f"- release dir: {_display_path(self.release_dir)}",
            f"- delivery status: {self.delivery_status}",
            f"- exact full-scale CERTIFIED status: {self.exact_full_scale_certified_status}",
            f"- payload artifacts: {self.payload_artifact_count} ({self.required_payload_artifact_count} required)",
            f"- manifest: {_display_path(self.release_manifest_json_path)}",
            f"- checksums: {_display_path(self.sha256sums_path)}",
            f"- active pointer: {_display_path(self.pointer_json_path)}",
            f"- viewer bundle: {self.viewer_bundle_status}",
            f"- current landing: {self.landing_bundle_status}",
            f"- repo front door: {self.frontdoor_bundle_status}",
            f"- active entrypoints: {self.entrypoints_bundle_status}",
            f"- surface alignment audit: {self.surface_alignment_status}",
            f"- current surface health: {self.surface_health_status}",
        ]
        if self.index_json_path is not None:
            lines.append(f"- release index: {_display_path(self.index_json_path)}")
        if self.viewer_output_dir is not None:
            lines.append(f"- viewer output dir: {_display_path(self.viewer_output_dir)}")
        if self.viewer_manifest_path is not None:
            lines.append(f"- viewer manifest: {_display_path(self.viewer_manifest_path)}")
        if self.viewer_pointer_json_path is not None:
            lines.append(f"- active viewer pointer: {_display_path(self.viewer_pointer_json_path)}")
        if self.viewer_index_json_path is not None:
            lines.append(f"- viewer index: {_display_path(self.viewer_index_json_path)}")
        if self.viewer_selected_facility_type_count is not None and self.viewer_selected_pose_count is not None:
            lines.append(
                "- viewer geometry: "
                f"{self.viewer_selected_facility_type_count} facility types / {self.viewer_selected_pose_count} poses"
            )
        if self.landing_output_dir is not None:
            lines.append(f"- current landing dir: {_display_path(self.landing_output_dir)}")
        if self.landing_index_html_path is not None:
            lines.append(f"- current landing HTML: {_display_path(self.landing_index_html_path)}")
        if self.landing_manifest_path is not None:
            lines.append(f"- current landing manifest: {_display_path(self.landing_manifest_path)}")
        if self.landing_quick_download_count is not None and self.landing_download_group_count is not None:
            lines.append(
                "- current landing downloads: "
                f"{self.landing_quick_download_count} quick / {self.landing_download_group_count} grouped sections"
            )
        if self.frontdoor_output_dir is not None:
            lines.append(f"- repo front door dir: {_display_path(self.frontdoor_output_dir)}")
        if self.frontdoor_index_html_path is not None:
            lines.append(f"- repo front door HTML: {_display_path(self.frontdoor_index_html_path)}")
        if self.frontdoor_manifest_path is not None:
            lines.append(f"- repo front door manifest: {_display_path(self.frontdoor_manifest_path)}")
        if self.frontdoor_quick_download_count is not None and self.frontdoor_download_group_count is not None:
            lines.append(
                "- repo front door downloads: "
                f"{self.frontdoor_quick_download_count} quick / {self.frontdoor_download_group_count} grouped sections"
            )
        if self.entrypoints_json_path is not None:
            lines.append(f"- active entrypoints JSON: {_display_path(self.entrypoints_json_path)}")
        if self.entrypoints_markdown_path is not None:
            lines.append(f"- active entrypoints Markdown: {_display_path(self.entrypoints_markdown_path)}")
        if self.entrypoints_group_count is not None and self.entrypoints_action_count is not None:
            lines.append(
                "- active entrypoints surface: "
                f"{self.entrypoints_group_count} grouped current entrypoints / {self.entrypoints_action_count} stable actions"
            )
        if self.surface_alignment_json_path is not None:
            lines.append(f"- surface alignment JSON: {_display_path(self.surface_alignment_json_path)}")
        if self.surface_alignment_markdown_path is not None:
            lines.append(f"- surface alignment Markdown: {_display_path(self.surface_alignment_markdown_path)}")
        if self.surface_alignment_console_path is not None:
            lines.append(f"- surface alignment console: {_display_path(self.surface_alignment_console_path)}")
        if self.surface_alignment_check_count is not None and self.surface_alignment_drift_check_count is not None:
            lines.append(
                "- surface alignment checks: "
                f"{self.surface_alignment_check_count} checked / {self.surface_alignment_drift_check_count} drift"
            )
        return "\n".join(lines)


@dataclass(frozen=True)
class _PathBackup:
    kind: str
    data: bytes | None = None


_RELEASE_SOURCE_FILE_SPECS: tuple[ReleaseSourceFileSpec, ...] = (
    ReleaseSourceFileSpec(
        relative_path="canonical/full_demand_recipe_capacity_canonical_blueprint.json",
        artifact_id="canonical_fixture",
        stage="planning",
        role="Regenerated canonical single-base source blueprint used to produce the released export.",
    ),
    ReleaseSourceFileSpec(
        relative_path="canonical/full_demand_fixture_plan_report.json",
        artifact_id="fixture_plan_report_json",
        stage="planning",
        role="Machine-readable planning report describing how the canonical fixture was regenerated.",
    ),
    ReleaseSourceFileSpec(
        relative_path="canonical/full_demand_fixture_plan_report.md",
        artifact_id="fixture_plan_report_markdown",
        stage="planning",
        role="Operator-facing planning report for the canonical fixture regeneration step.",
    ),
    ReleaseSourceFileSpec(
        relative_path="bundle/industrial_planner.blueprint.json",
        artifact_id="industrial_planner_blueprint",
        stage="export",
        role="Actual IndustrialPlanner delivery blueprint for import.",
    ),
    ReleaseSourceFileSpec(
        relative_path="bundle/industrial_planner.compatibility_manifest.json",
        artifact_id="industrial_planner_compatibility_manifest",
        stage="export",
        role="Export-side compatibility manifest that explains target translation details and warnings.",
    ),
    ReleaseSourceFileSpec(
        relative_path="bundle/validation_report.json",
        artifact_id="validation_report_json",
        stage="validator",
        role="Machine-readable offline import/layout validation report for the released blueprint.",
    ),
    ReleaseSourceFileSpec(
        relative_path="bundle/validation_report.md",
        artifact_id="validation_report_markdown",
        stage="validator",
        role="Human-readable offline import/layout validation report for the released blueprint.",
    ),
    ReleaseSourceFileSpec(
        relative_path="bundle/throughput_report.json",
        artifact_id="throughput_report_json",
        stage="throughput",
        role="Machine-readable static recipe/capacity audit sidecar for the released blueprint.",
    ),
    ReleaseSourceFileSpec(
        relative_path="bundle/throughput_report.md",
        artifact_id="throughput_report_markdown",
        stage="throughput",
        role="Human-readable static recipe/capacity audit sidecar for the released blueprint.",
    ),
    ReleaseSourceFileSpec(
        relative_path="support_suite/full_demand_base_support_matrix.json",
        artifact_id="fresh_support_canonical_matrix_json",
        stage="support_reports",
        role="Machine-readable active single-base canonical support matrix regenerated during the release run.",
    ),
    ReleaseSourceFileSpec(
        relative_path="support_suite/full_demand_base_support_matrix.md",
        artifact_id="fresh_support_canonical_matrix_markdown",
        stage="support_reports",
        role="Human-readable active single-base canonical support matrix regenerated during the release run.",
    ),
    ReleaseSourceFileSpec(
        relative_path="support_suite/full_demand_deployment_path_matrix.json",
        artifact_id="fresh_support_deployment_matrix_json",
        stage="support_reports",
        role="Machine-readable companion deployment-path matrix that preserves dormant outer-path metadata as `future_scope`.",
    ),
    ReleaseSourceFileSpec(
        relative_path="support_suite/full_demand_deployment_path_matrix.md",
        artifact_id="fresh_support_deployment_matrix_markdown",
        stage="support_reports",
        role="Human-readable companion deployment-path matrix that preserves dormant outer-path metadata as `future_scope`.",
    ),
    ReleaseSourceFileSpec(
        relative_path="support_suite/full_demand_support_overview.json",
        artifact_id="fresh_support_overview_json",
        stage="support_reports",
        role="Machine-readable umbrella summary of the fresh single-base support surface for this release.",
    ),
    ReleaseSourceFileSpec(
        relative_path="support_suite/full_demand_support_overview.md",
        artifact_id="fresh_support_overview_markdown",
        stage="support_reports",
        role="Human-readable umbrella summary of the fresh single-base support surface for this release.",
    ),
    ReleaseSourceFileSpec(
        relative_path="checks/support_suite_inventory_summary.json",
        artifact_id="support_suite_inventory_summary_json",
        stage="checked_in_support_suite",
        role="Machine-readable verdict proving the checked-in support-suite inventory is still clean.",
    ),
    ReleaseSourceFileSpec(
        relative_path="checks/support_suite_inventory_summary.md",
        artifact_id="support_suite_inventory_summary_markdown",
        stage="checked_in_support_suite",
        role="Human-readable verdict proving the checked-in support-suite inventory is still clean.",
    ),
    ReleaseSourceFileSpec(
        relative_path="checks/support_suite_inventory_summary.txt",
        artifact_id="support_suite_inventory_summary_console",
        stage="checked_in_support_suite",
        role="Plain-text console summary for the checked-in support-suite inventory verdict.",
        required_for_delivery=False,
    ),
    ReleaseSourceFileSpec(
        relative_path="checks/checked_artifact_suite_summary.json",
        artifact_id="checked_artifact_suite_summary_json",
        stage="checked_artifact_gate",
        role="Machine-readable repo-level checked-artifact gate verdict.",
    ),
    ReleaseSourceFileSpec(
        relative_path="checks/checked_artifact_suite_summary.md",
        artifact_id="checked_artifact_suite_summary_markdown",
        stage="checked_artifact_gate",
        role="Human-readable repo-level checked-artifact gate verdict.",
    ),
    ReleaseSourceFileSpec(
        relative_path="checks/checked_artifact_suite_summary.txt",
        artifact_id="checked_artifact_suite_summary_console",
        stage="checked_artifact_gate",
        role="Plain-text console summary for the repo-level checked-artifact gate verdict.",
        required_for_delivery=False,
    ),
    ReleaseSourceFileSpec(
        relative_path="run_summary.json",
        artifact_id="run_summary_json",
        stage="run_summary",
        role="Machine-readable top-level summary for the source single-base end-to-end run.",
    ),
    ReleaseSourceFileSpec(
        relative_path="run_summary.md",
        artifact_id="run_summary_markdown",
        stage="run_summary",
        role="Human-readable top-level summary for the source single-base end-to-end run.",
    ),
    ReleaseSourceFileSpec(
        relative_path="run_summary.txt",
        artifact_id="run_summary_console",
        stage="run_summary",
        role="Plain-text console summary for the source single-base end-to-end run.",
        required_for_delivery=False,
    ),
)


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()



def _default_release_id(base_id: str = DEFAULT_BASE_ID) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{base_id}_{_ACTIVE_LOT_SIZE}x{_ACTIVE_LOT_SIZE}_{stamp}"



def _normalize_release_id(release_id: str | None, *, base_id: str) -> str:
    if release_id is None or not str(release_id).strip():
        return _default_release_id(base_id)
    normalized = str(release_id).strip().replace(" ", "_")
    if not normalized:
        raise SingleBaseDeliveryReleaseError("release_id must not be empty")
    return normalized



def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SingleBaseDeliveryReleaseError(f"required JSON file is missing: {_display_path(path)}") from exc
    except json.JSONDecodeError as exc:
        raise SingleBaseDeliveryReleaseError(f"invalid JSON in {_display_path(path)}: {exc}") from exc



def _validate_ready_run_summary(summary: Mapping[str, Any], *, expected_base_id: str) -> None:
    problems: list[str] = []
    overall_status = str(summary.get("overall_status", "")).strip()
    deliverable_status = str(summary.get("deliverable_status", "")).strip()
    requested_base_id = str(summary.get("requested_base_id", "")).strip()
    active_contract_base_id = str(summary.get("active_contract_base_id", "")).strip()
    requested_base_is_active_contract = bool(summary.get("requested_base_is_active_contract"))
    validation = summary.get("validation") if isinstance(summary.get("validation"), Mapping) else {}
    throughput = summary.get("throughput") if isinstance(summary.get("throughput"), Mapping) else {}
    checked_support = (
        summary.get("checked_in_support_suite_inventory")
        if isinstance(summary.get("checked_in_support_suite_inventory"), Mapping)
        else {}
    )
    checked_artifact = (
        summary.get("checked_artifact_suite")
        if isinstance(summary.get("checked_artifact_suite"), Mapping)
        else {}
    )
    exact_certified = (
        summary.get("exact_full_scale_certified")
        if isinstance(summary.get("exact_full_scale_certified"), Mapping)
        else {}
    )

    if overall_status != "success":
        problems.append(f"overall_status must be 'success', got {overall_status!r}")
    if deliverable_status != "ready_for_single_base_delivery":
        problems.append(
            "deliverable_status must be 'ready_for_single_base_delivery', "
            f"got {deliverable_status!r}"
        )
    if requested_base_id != expected_base_id:
        problems.append(f"requested_base_id must be {expected_base_id!r}, got {requested_base_id!r}")
    if active_contract_base_id != expected_base_id:
        problems.append(
            f"active_contract_base_id must be {expected_base_id!r}, got {active_contract_base_id!r}"
        )
    if not requested_base_is_active_contract:
        problems.append("requested_base_is_active_contract must be true")
    if not bool(validation.get("is_import_compatible")):
        problems.append("validation.is_import_compatible must be true")
    if not bool(validation.get("is_layout_healthy")):
        problems.append("validation.is_layout_healthy must be true")
    if str(throughput.get("status", "")).strip() != "proven_equivalent":
        problems.append(
            "throughput.status must be 'proven_equivalent', "
            f"got {str(throughput.get('status', '')).strip()!r}"
        )
    if str(checked_support.get("status", "")).strip() != "clean":
        problems.append(
            "checked_in_support_suite_inventory.status must be 'clean', "
            f"got {str(checked_support.get('status', '')).strip()!r}"
        )
    if str(checked_artifact.get("status", "")).strip() != "clean":
        problems.append(
            "checked_artifact_suite.status must be 'clean', "
            f"got {str(checked_artifact.get('status', '')).strip()!r}"
        )
    # V81: the run summary is not a certified authority. Until this release
    # path consumes the canonical certified_surface verifier verdict, a
    # self-claimed CERTIFIED status must fail closed instead of propagating
    # into the release manifest and active pointer.
    if str(exact_certified.get("status", "")).strip().upper() == "CERTIFIED":
        problems.append(
            "run_summary.exact_full_scale_certified.status may not claim 'CERTIFIED' "
            "on the single-base release path; exact CERTIFIED publication must be "
            "produced by the canonical certified_delivery_manifest/certified_surface verifier"
        )

    if problems:
        details = "\n".join(f"- {problem}" for problem in problems)
        raise SingleBaseDeliveryReleaseError(
            "single-base delivery release requires a delivery-ready source run summary:\n" + details
        )



def _copy_release_payload(
    *,
    source_run_dir: Path,
    release_dir: Path,
) -> tuple[ReleasedArtifact, ...]:
    artifacts: list[ReleasedArtifact] = []
    missing_required: list[str] = []

    for spec in _RELEASE_SOURCE_FILE_SPECS:
        source_path = source_run_dir / spec.relative_path
        if not source_path.exists():
            if spec.required_for_delivery:
                missing_required.append(spec.relative_path)
            continue
        release_path = release_dir / spec.relative_path
        release_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, release_path)
        artifacts.append(
            ReleasedArtifact(
                artifact_id=spec.artifact_id,
                stage=spec.stage,
                role=spec.role,
                required_for_delivery=spec.required_for_delivery,
                relative_path=spec.relative_path,
                source_path=source_path,
                release_path=release_path,
                sha256=sha256_file(release_path),
                size_bytes=int(release_path.stat().st_size),
            )
        )

    if missing_required:
        missing_lines = "\n".join(f"- {relative_path}" for relative_path in missing_required)
        raise SingleBaseDeliveryReleaseError(
            "source run is missing required payload files for the release bundle:\n" + missing_lines
        )

    return tuple(artifacts)



def _build_release_manifest_payload(
    *,
    summary: Mapping[str, Any],
    release_id: str,
    base_id: str,
    source_run_dir: Path,
    release_dir: Path,
    pointer_json_path: Path,
    pointer_markdown_path: Path,
    index_json_path: Path | None,
    index_markdown_path: Path | None,
    artifacts: tuple[ReleasedArtifact, ...],
) -> dict[str, Any]:
    artifact_by_id = {artifact.artifact_id: artifact for artifact in artifacts}
    exact_payload = summary.get("exact_full_scale_certified")
    if not isinstance(exact_payload, Mapping):
        exact_payload = {
            "status": "unknown",
            "note": "source run summary did not provide exact full-scale certification state",
        }

    release_command = [
        "python scripts/build_industrial_planner_single_base_delivery_release.py",
        f"--source-run-dir {_display_path(source_run_dir)}",
        f"--release-root {_display_path(release_dir.parent)}",
        f"--release-id {release_id}",
        f"--pointer-json {_display_path(pointer_json_path)}",
        f"--pointer-markdown {_display_path(pointer_markdown_path)}",
    ]
    if index_json_path is not None:
        release_command.append(f"--index-json {_display_path(index_json_path)}")
    if index_markdown_path is not None:
        release_command.append(f"--index-markdown {_display_path(index_markdown_path)}")

    payload = {
        "metadata": {
            "schema_version": _RELEASE_SCHEMA_VERSION,
            "generated_at": now_iso(),
            "source": _RELEASE_SOURCE,
        },
        "release": {
            "release_id": release_id,
            "base_id": base_id,
            "lot_size": _ACTIVE_LOT_SIZE,
            "delivery_status": str(summary.get("deliverable_status", "")),
            "release_dir": _display_path(release_dir),
            "source_run_dir": _display_path(source_run_dir),
            "scope_note": _SCOPE_NOTE,
        },
        "delivery_entrypoints": {
            "blueprint": _display_path(artifact_by_id["industrial_planner_blueprint"].release_path),
            "compatibility_manifest": _display_path(
                artifact_by_id["industrial_planner_compatibility_manifest"].release_path
            ),
            "validation_report": _display_path(artifact_by_id["validation_report_json"].release_path),
            "throughput_report": _display_path(artifact_by_id["throughput_report_json"].release_path),
            "run_summary": _display_path(artifact_by_id["run_summary_json"].release_path),
        },
        "source_run": {
            "overall_status": str(summary.get("overall_status", "")),
            "failure_stage": summary.get("failure_stage"),
            "failure_classification": summary.get("failure_classification"),
            "deliverable_status": str(summary.get("deliverable_status", "")),
            "requested_base_id": str(summary.get("requested_base_id", "")),
            "active_contract_base_id": str(summary.get("active_contract_base_id", "")),
            "requested_base_is_active_contract": bool(summary.get("requested_base_is_active_contract")),
            "planning_status": str(
                (summary.get("planning") or {}).get("status", "")
                if isinstance(summary.get("planning"), Mapping)
                else ""
            ),
            "export_status": str(
                (summary.get("export_bundle") or {}).get("status", "")
                if isinstance(summary.get("export_bundle"), Mapping)
                else ""
            ),
            "validation_status": str(
                (summary.get("validation") or {}).get("delivery_validation_status", "")
                if isinstance(summary.get("validation"), Mapping)
                else ""
            ),
            "throughput_status": str(
                (summary.get("throughput") or {}).get("status", "")
                if isinstance(summary.get("throughput"), Mapping)
                else ""
            ),
            "fresh_support_status": str(
                (summary.get("fresh_support_suite") or {}).get("status", "")
                if isinstance(summary.get("fresh_support_suite"), Mapping)
                else ""
            ),
            "checked_in_support_status": str(
                (summary.get("checked_in_support_suite_inventory") or {}).get("status", "")
                if isinstance(summary.get("checked_in_support_suite_inventory"), Mapping)
                else ""
            ),
            "checked_artifact_status": str(
                (summary.get("checked_artifact_suite") or {}).get("status", "")
                if isinstance(summary.get("checked_artifact_suite"), Mapping)
                else ""
            ),
        },
        "exact_full_scale_certified": {
            "status": str(exact_payload.get("status", "")),
            "note": str(exact_payload.get("note", "")),
        },
        "artifacts": [artifact.to_dict() for artifact in artifacts],
        "generated_files": {
            "release_manifest_json": _display_path(release_dir / _RELEASE_MANIFEST_JSON_FILENAME),
            "release_manifest_markdown": _display_path(release_dir / _RELEASE_MANIFEST_MARKDOWN_FILENAME),
            "sha256sums": _display_path(release_dir / _SHA256SUMS_FILENAME),
            "active_pointer_json": _display_path(pointer_json_path),
            "active_pointer_markdown": _display_path(pointer_markdown_path),
            "release_index_json": _display_path(index_json_path),
            "release_index_markdown": _display_path(index_markdown_path),
        },
        "reproducibility": {
            "e2e_command": (
                "python scripts/run_industrial_planner_single_base_e2e.py "
                f"--run-dir {_display_path(source_run_dir)}"
            ),
            "release_command": " ".join(release_command),
        },
        "notes": [
            "This release captures only the active `valley4_protocol_core` 70×70 delivery surface.",
            "Other bases remain preserved `future_scope` metadata and are not reactivated here.",
            str(exact_payload.get("note", "")),
        ],
    }
    return payload



def _render_release_manifest_markdown(payload: Mapping[str, Any]) -> str:
    release = payload.get("release", {}) if isinstance(payload.get("release"), Mapping) else {}
    entrypoints = (
        payload.get("delivery_entrypoints", {})
        if isinstance(payload.get("delivery_entrypoints"), Mapping)
        else {}
    )
    source_run = payload.get("source_run", {}) if isinstance(payload.get("source_run"), Mapping) else {}
    exact_payload = (
        payload.get("exact_full_scale_certified", {})
        if isinstance(payload.get("exact_full_scale_certified"), Mapping)
        else {}
    )
    metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), Mapping) else {}
    reproducibility = (
        payload.get("reproducibility", {})
        if isinstance(payload.get("reproducibility"), Mapping)
        else {}
    )
    artifacts = payload.get("artifacts", []) if isinstance(payload.get("artifacts"), list) else []
    notes = payload.get("notes", []) if isinstance(payload.get("notes"), list) else []

    lines = [
        "# IndustrialPlanner Single-Base Delivery Release",
        "",
        str(release.get("scope_note", _SCOPE_NOTE)),
        "",
        f"- Release id: `{release.get('release_id', '')}`",
        f"- Base id: `{release.get('base_id', '')}`",
        f"- Lot size: `{release.get('lot_size', '')}`",
        f"- Delivery status: `{release.get('delivery_status', '')}`",
        f"- Release dir: `{release.get('release_dir', '')}`",
        f"- Source run dir: `{release.get('source_run_dir', '')}`",
        f"- Manifest generated at: `{metadata.get('generated_at', '')}`",
        f"- Full-scale exact `CERTIFIED` status: `{exact_payload.get('status', '')}`",
        f"- Exact-status note: {exact_payload.get('note', '')}",
        "",
        "## Delivery entrypoints",
        "",
        f"- Blueprint: `{entrypoints.get('blueprint', '')}`",
        f"- Compatibility manifest: `{entrypoints.get('compatibility_manifest', '')}`",
        f"- Validation report: `{entrypoints.get('validation_report', '')}`",
        f"- Throughput report: `{entrypoints.get('throughput_report', '')}`",
        f"- Source run summary: `{entrypoints.get('run_summary', '')}`",
        "",
        "## Source run gate summary",
        "",
        "| Gate | Status |",
        "|---|---|",
        f"| overall_status | `{source_run.get('overall_status', '')}` |",
        f"| deliverable_status | `{source_run.get('deliverable_status', '')}` |",
        f"| planning | `{source_run.get('planning_status', '')}` |",
        f"| export | `{source_run.get('export_status', '')}` |",
        f"| validator | `{source_run.get('validation_status', '')}` |",
        f"| throughput | `{source_run.get('throughput_status', '')}` |",
        f"| fresh support reports | `{source_run.get('fresh_support_status', '')}` |",
        f"| checked-in support inventory | `{source_run.get('checked_in_support_status', '')}` |",
        f"| checked-artifact gate | `{source_run.get('checked_artifact_status', '')}` |",
        "",
        "## Reproducibility commands",
        "",
        "```bash",
        str(reproducibility.get("e2e_command", "")).strip(),
        str(reproducibility.get("release_command", "")).strip(),
        "```",
        "",
        "## Payload artifacts",
        "",
        "| Artifact | Required | Stage | Path | SHA256 |",
        "|---|---|---|---|---|",
    ]
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{artifact.get('artifact_id', '')}`",
                    "yes" if bool(artifact.get("required_for_delivery")) else "no",
                    f"`{artifact.get('stage', '')}`",
                    f"`{artifact.get('release_path', '')}`",
                    f"`{artifact.get('sha256', '')}`",
                ]
            )
            + " |"
        )
    if notes:
        lines.extend(["", "## Notes", ""])
        for note in notes:
            lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)



def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")



def _write_sha256sums(
    *,
    release_dir: Path,
    artifacts: tuple[ReleasedArtifact, ...],
    include_paths: tuple[Path, ...],
) -> Path:
    lines: list[str] = []
    for artifact in sorted(artifacts, key=lambda item: item.relative_path):
        lines.append(f"{artifact.sha256}  {artifact.relative_path}")
    for extra_path in sorted(include_paths, key=lambda path: path.name):
        relative_path = extra_path.relative_to(release_dir).as_posix()
        lines.append(f"{sha256_file(extra_path)}  {relative_path}")
    path = release_dir / _SHA256SUMS_FILENAME
    _write_text(path, "\n".join(lines) + "\n")
    return path



def _build_pointer_payload(
    *,
    release_payload: Mapping[str, Any],
    pointer_json_path: Path,
    pointer_markdown_path: Path,
) -> dict[str, Any]:
    release = release_payload.get("release", {}) if isinstance(release_payload.get("release"), Mapping) else {}
    entrypoints = (
        release_payload.get("delivery_entrypoints", {})
        if isinstance(release_payload.get("delivery_entrypoints"), Mapping)
        else {}
    )
    exact_payload = (
        release_payload.get("exact_full_scale_certified", {})
        if isinstance(release_payload.get("exact_full_scale_certified"), Mapping)
        else {}
    )
    generated_files = (
        release_payload.get("generated_files", {})
        if isinstance(release_payload.get("generated_files"), Mapping)
        else {}
    )
    return {
        "metadata": {
            "schema_version": _RELEASE_SCHEMA_VERSION,
            "updated_at": now_iso(),
            "source": _POINTER_SOURCE,
        },
        "current_release": {
            "release_id": str(release.get("release_id", "")),
            "base_id": str(release.get("base_id", "")),
            "lot_size": int(release.get("lot_size", 0) or 0),
            "delivery_status": str(release.get("delivery_status", "")),
            "release_dir": str(release.get("release_dir", "")),
            "blueprint": str(entrypoints.get("blueprint", "")),
            "compatibility_manifest": str(entrypoints.get("compatibility_manifest", "")),
            "validation_report": str(entrypoints.get("validation_report", "")),
            "throughput_report": str(entrypoints.get("throughput_report", "")),
            "run_summary": str(entrypoints.get("run_summary", "")),
            "release_manifest_json": str(generated_files.get("release_manifest_json", "")),
            "release_manifest_markdown": str(generated_files.get("release_manifest_markdown", "")),
            "sha256sums": str(generated_files.get("sha256sums", "")),
            "exact_full_scale_certified": {
                "status": str(exact_payload.get("status", "")),
                "note": str(exact_payload.get("note", "")),
            },
            "scope_note": str(release.get("scope_note", _SCOPE_NOTE)),
        },
        "pointer_paths": {
            "json": _display_path(pointer_json_path),
            "markdown": _display_path(pointer_markdown_path),
        },
    }



def _render_pointer_markdown(pointer_payload: Mapping[str, Any]) -> str:
    current = (
        pointer_payload.get("current_release", {})
        if isinstance(pointer_payload.get("current_release"), Mapping)
        else {}
    )
    exact_payload = (
        current.get("exact_full_scale_certified", {})
        if isinstance(current.get("exact_full_scale_certified"), Mapping)
        else {}
    )
    return "\n".join(
        [
            "# Active IndustrialPlanner Single-Base Delivery Release",
            "",
            str(current.get("scope_note", _SCOPE_NOTE)),
            "",
            f"- Release id: `{current.get('release_id', '')}`",
            f"- Base id: `{current.get('base_id', '')}`",
            f"- Lot size: `{current.get('lot_size', '')}`",
            f"- Delivery status: `{current.get('delivery_status', '')}`",
            f"- Release dir: `{current.get('release_dir', '')}`",
            f"- Blueprint: `{current.get('blueprint', '')}`",
            f"- Compatibility manifest: `{current.get('compatibility_manifest', '')}`",
            f"- Validation report: `{current.get('validation_report', '')}`",
            f"- Throughput report: `{current.get('throughput_report', '')}`",
            f"- Run summary: `{current.get('run_summary', '')}`",
            f"- Release manifest: `{current.get('release_manifest_json', '')}`",
            f"- SHA256SUMS: `{current.get('sha256sums', '')}`",
            f"- Full-scale exact `CERTIFIED` status: `{exact_payload.get('status', '')}`",
            f"- Exact-status note: {exact_payload.get('note', '')}",
            "",
        ]
    )



def _read_text_if_exists(path: Path) -> _PathBackup:
    if not path.exists():
        return _PathBackup(kind="missing")
    if path.is_dir():
        return _PathBackup(kind="directory")
    return _PathBackup(kind="file", data=path.read_bytes())



def _restore_text_backup(path: Path, backup_text: _PathBackup) -> None:
    if backup_text.kind == "missing":
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        return
    if backup_text.kind == "directory":
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        path.mkdir(parents=True, exist_ok=True)
        return
    if backup_text.kind != "file":
        raise SingleBaseDeliveryReleaseError(f"unsupported backup kind for {path}: {backup_text.kind!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(backup_text.data or b"")



def _backup_directory_if_exists(path: Path | None) -> Path | None:
    if path is None or not path.exists() or not path.is_dir():
        return None
    backup_dir = Path(tempfile.mkdtemp(prefix=f".{path.name}.backup.", dir=str(path.parent)))
    shutil.rmtree(backup_dir)
    shutil.copytree(path, backup_dir)
    return backup_dir



def _restore_directory_backup(*, path: Path | None, backup_dir: Path | None) -> None:
    if path is None:
        _remove_tree_if_exists(backup_dir)
        return
    if path.exists():
        _remove_tree_if_exists(path)
    if backup_dir is not None and backup_dir.exists():
        shutil.move(str(backup_dir), str(path))



def _discard_directory_backup(backup_dir: Path | None) -> None:
    _remove_tree_if_exists(backup_dir)



def _remove_tree_if_exists(path: Path | None) -> None:
    if path is None or not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()



def _build_viewer_pointer_payload(
    *,
    viewer_output_dir: Path,
    viewer_manifest_payload: Mapping[str, Any],
    viewer_pointer_json_path: Path,
    viewer_pointer_markdown_path: Path,
    release_pointer_json_path: Path,
    release_pointer_markdown_path: Path,
) -> dict[str, Any]:
    current_release = (
        viewer_manifest_payload.get("current_release", {})
        if isinstance(viewer_manifest_payload.get("current_release"), Mapping)
        else {}
    )
    exact_payload = (
        viewer_manifest_payload.get("exact_full_scale_certified", {})
        if isinstance(viewer_manifest_payload.get("exact_full_scale_certified"), Mapping)
        else {}
    )
    viewer_bundle = (
        viewer_manifest_payload.get("viewer_bundle", {})
        if isinstance(viewer_manifest_payload.get("viewer_bundle"), Mapping)
        else {}
    )
    asset_paths = (
        viewer_bundle.get("asset_paths", {})
        if isinstance(viewer_bundle.get("asset_paths"), Mapping)
        else {}
    )
    quick_downloads_raw = viewer_manifest_payload.get("quick_downloads")
    quick_downloads = list(quick_downloads_raw) if isinstance(quick_downloads_raw, list) else []

    def _asset_repo_path(key: str, default: str) -> str:
        relative = asset_paths.get(key)
        relative_path = str(relative).strip() if isinstance(relative, str) and str(relative).strip() else default
        return str(_display_path((viewer_output_dir / Path(relative_path)).resolve()))

    normalized_quick_downloads: list[dict[str, Any]] = []
    for entry in quick_downloads:
        if not isinstance(entry, Mapping):
            continue
        href = str(entry.get("href", "")).strip()
        if not href:
            continue
        normalized_quick_downloads.append(
            {
                "id": str(entry.get("id", "")),
                "label": str(entry.get("label", "")),
                "path": str(_display_path((viewer_output_dir / Path(href)).resolve())),
                "kind": str(entry.get("kind", "")),
                "stage": str(entry.get("stage", "")),
                "required_for_delivery": bool(entry.get("required_for_delivery")),
                "role": str(entry.get("role", "")),
            }
        )

    return {
        "metadata": {
            "schema_version": _RELEASE_SCHEMA_VERSION,
            "updated_at": now_iso(),
            "source": _VIEWER_POINTER_SOURCE,
        },
        "current_viewer": {
            "release_id": str(current_release.get("release_id", "")),
            "base_id": str(current_release.get("base_id", "")),
            "lot_size": int(current_release.get("lot_size", 0) or 0),
            "delivery_status": str(current_release.get("delivery_status", "")),
            "viewer_dir": str(_display_path(viewer_output_dir)),
            "index_html": _asset_repo_path("index_html", "index.html"),
            "viewer_manifest_json": str(_display_path((viewer_output_dir / _VIEWER_MANIFEST_JSON_FILENAME).resolve())),
            "optimal_blueprint": _asset_repo_path("optimal_blueprint", "optimal_blueprint.json"),
            "candidate_placements": _asset_repo_path("candidate_placements", "candidate_placements.json"),
            "final_solution": _asset_repo_path("final_solution", "final_solution.json"),
            "viewer_report": _asset_repo_path("viewer_report", "viewer_report.json"),
            "selected_facility_type_count": int(viewer_bundle.get("selected_facility_type_count", 0) or 0),
            "selected_pose_count": int(viewer_bundle.get("selected_pose_count", 0) or 0),
            "payload_download_count": len(
                viewer_manifest_payload.get("payload_artifacts")
                if isinstance(viewer_manifest_payload.get("payload_artifacts"), list)
                else []
            ),
            "metadata_download_count": len(
                viewer_manifest_payload.get("metadata_downloads")
                if isinstance(viewer_manifest_payload.get("metadata_downloads"), list)
                else []
            ),
            "quick_download_count": len(normalized_quick_downloads),
            "quick_downloads": normalized_quick_downloads,
            "exact_full_scale_certified": {
                "status": str(exact_payload.get("status", "")),
                "note": str(exact_payload.get("note", "")),
            },
            "scope_note": str(current_release.get("scope_note", _SCOPE_NOTE)),
            "release_pointer_json": _display_path(release_pointer_json_path),
            "release_pointer_markdown": _display_path(release_pointer_markdown_path),
        },
        "pointer_paths": {
            "json": _display_path(viewer_pointer_json_path),
            "markdown": _display_path(viewer_pointer_markdown_path),
        },
    }



def _render_viewer_pointer_markdown(pointer_payload: Mapping[str, Any]) -> str:
    current = (
        pointer_payload.get("current_viewer", {})
        if isinstance(pointer_payload.get("current_viewer"), Mapping)
        else {}
    )
    exact_payload = (
        current.get("exact_full_scale_certified", {})
        if isinstance(current.get("exact_full_scale_certified"), Mapping)
        else {}
    )
    return "\n".join(
        [
            "# Active IndustrialPlanner Single-Base Delivery Viewer",
            "",
            str(current.get("scope_note", _SCOPE_NOTE)),
            "",
            f"- Release id: `{current.get('release_id', '')}`",
            f"- Base id: `{current.get('base_id', '')}`",
            f"- Lot size: `{current.get('lot_size', '')}`",
            f"- Delivery status: `{current.get('delivery_status', '')}`",
            f"- Viewer dir: `{current.get('viewer_dir', '')}`",
            f"- Viewer HTML: `{current.get('index_html', '')}`",
            f"- Viewer manifest: `{current.get('viewer_manifest_json', '')}`",
            f"- Optimal blueprint: `{current.get('optimal_blueprint', '')}`",
            f"- Candidate placements: `{current.get('candidate_placements', '')}`",
            f"- Final solution: `{current.get('final_solution', '')}`",
            f"- Viewer report: `{current.get('viewer_report', '')}`",
            f"- Selected facility types: `{current.get('selected_facility_type_count', '')}`",
            f"- Selected poses: `{current.get('selected_pose_count', '')}`",
            f"- Payload downloads: `{current.get('payload_download_count', '')}`",
            f"- Metadata downloads: `{current.get('metadata_download_count', '')}`",
            f"- Quick downloads: `{current.get('quick_download_count', '')}`",
            f"- Release pointer JSON: `{current.get('release_pointer_json', '')}`",
            f"- Release pointer Markdown: `{current.get('release_pointer_markdown', '')}`",
            f"- Full-scale exact `CERTIFIED` status: `{exact_payload.get('status', '')}`",
            f"- Exact-status note: {exact_payload.get('note', '')}",
            "",
        ]
    )



def _build_viewer_index_payload(
    *,
    viewer_root: Path,
    current_release_id: str,
    index_json_path: Path | None,
    index_markdown_path: Path | None,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for manifest_path in sorted(viewer_root.glob(f"*/{_VIEWER_MANIFEST_JSON_FILENAME}")):
        viewer_manifest = _load_json(manifest_path)
        current_release = (
            viewer_manifest.get("current_release", {})
            if isinstance(viewer_manifest.get("current_release"), Mapping)
            else {}
        )
        exact_payload = (
            viewer_manifest.get("exact_full_scale_certified", {})
            if isinstance(viewer_manifest.get("exact_full_scale_certified"), Mapping)
            else {}
        )
        viewer_bundle = (
            viewer_manifest.get("viewer_bundle", {})
            if isinstance(viewer_manifest.get("viewer_bundle"), Mapping)
            else {}
        )
        asset_paths = (
            viewer_bundle.get("asset_paths", {})
            if isinstance(viewer_bundle.get("asset_paths"), Mapping)
            else {}
        )
        metadata = (
            viewer_manifest.get("metadata", {}) if isinstance(viewer_manifest.get("metadata"), Mapping) else {}
        )
        output_dir = manifest_path.parent.resolve()
        index_html_relative = str(asset_paths.get("index_html", "index.html"))
        entries.append(
            {
                "release_id": str(current_release.get("release_id", manifest_path.parent.name)),
                "base_id": str(current_release.get("base_id", "")),
                "lot_size": int(current_release.get("lot_size", 0) or 0),
                "delivery_status": str(current_release.get("delivery_status", "")),
                "viewer_dir": str(_display_path(output_dir)),
                "index_html": str(_display_path((output_dir / Path(index_html_relative)).resolve())),
                "viewer_manifest_json": str(_display_path(manifest_path.resolve())),
                "generated_at": str(metadata.get("generated_at", "")),
                "exact_full_scale_certified_status": str(exact_payload.get("status", "")),
                "selected_facility_type_count": int(viewer_bundle.get("selected_facility_type_count", 0) or 0),
                "selected_pose_count": int(viewer_bundle.get("selected_pose_count", 0) or 0),
            }
        )

    entries.sort(key=lambda entry: (entry.get("generated_at", ""), entry.get("release_id", "")), reverse=True)
    return {
        "metadata": {
            "schema_version": _RELEASE_SCHEMA_VERSION,
            "updated_at": now_iso(),
            "source": _VIEWER_INDEX_SOURCE,
        },
        "viewer_root": _display_path(viewer_root),
        "current_release_id": current_release_id,
        "viewer_count": len(entries),
        "index_paths": {
            "json": _display_path(index_json_path),
            "markdown": _display_path(index_markdown_path),
        },
        "viewers": entries,
    }



def _render_viewer_index_markdown(payload: Mapping[str, Any]) -> str:
    viewers = payload.get("viewers", []) if isinstance(payload.get("viewers"), list) else []
    lines = [
        "# IndustrialPlanner Single-Base Delivery Viewer Index",
        "",
        f"- Viewer root: `{payload.get('viewer_root', '')}`",
        f"- Current release id: `{payload.get('current_release_id', '')}`",
        f"- Viewer count: `{payload.get('viewer_count', '')}`",
        "",
        "| Release id | Base | Lot size | Delivery status | Exact full-scale CERTIFIED | Generated at | Viewer HTML |",
        "|---|---|---:|---|---|---|---|",
    ]
    for entry in viewers:
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{entry.get('release_id', '')}`",
                    f"`{entry.get('base_id', '')}`",
                    str(entry.get("lot_size", "")),
                    f"`{entry.get('delivery_status', '')}`",
                    f"`{entry.get('exact_full_scale_certified_status', '')}`",
                    f"`{entry.get('generated_at', '')}`",
                    f"`{entry.get('index_html', '')}`",
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)



def _build_release_index_payload(
    *,
    release_root: Path,
    current_release_id: str,
    index_json_path: Path | None,
    index_markdown_path: Path | None,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for manifest_path in sorted(release_root.glob(f"*/{_RELEASE_MANIFEST_JSON_FILENAME}")):
        manifest_payload = _load_json(manifest_path)
        release = manifest_payload.get("release", {}) if isinstance(manifest_payload.get("release"), Mapping) else {}
        exact_payload = (
            manifest_payload.get("exact_full_scale_certified", {})
            if isinstance(manifest_payload.get("exact_full_scale_certified"), Mapping)
            else {}
        )
        entrypoints = (
            manifest_payload.get("delivery_entrypoints", {})
            if isinstance(manifest_payload.get("delivery_entrypoints"), Mapping)
            else {}
        )
        metadata = (
            manifest_payload.get("metadata", {}) if isinstance(manifest_payload.get("metadata"), Mapping) else {}
        )
        release_id = str(release.get("release_id", manifest_path.parent.name))
        entries.append(
            {
                "release_id": release_id,
                "base_id": str(release.get("base_id", "")),
                "lot_size": int(release.get("lot_size", 0) or 0),
                "delivery_status": str(release.get("delivery_status", "")),
                "release_dir": str(release.get("release_dir", _display_path(manifest_path.parent))),
                "blueprint": str(entrypoints.get("blueprint", "")),
                "generated_at": str(metadata.get("generated_at", "")),
                "exact_full_scale_certified_status": str(exact_payload.get("status", "")),
            }
        )
    entries.sort(key=lambda entry: (entry.get("generated_at", ""), entry.get("release_id", "")), reverse=True)
    return {
        "metadata": {
            "schema_version": _RELEASE_SCHEMA_VERSION,
            "updated_at": now_iso(),
            "source": _INDEX_SOURCE,
        },
        "release_root": _display_path(release_root),
        "current_release_id": current_release_id,
        "release_count": len(entries),
        "index_paths": {
            "json": _display_path(index_json_path),
            "markdown": _display_path(index_markdown_path),
        },
        "releases": entries,
    }



def _render_release_index_markdown(payload: Mapping[str, Any]) -> str:
    releases = payload.get("releases", []) if isinstance(payload.get("releases"), list) else []
    lines = [
        "# IndustrialPlanner Single-Base Delivery Release Index",
        "",
        f"- Release root: `{payload.get('release_root', '')}`",
        f"- Current release id: `{payload.get('current_release_id', '')}`",
        f"- Release count: `{payload.get('release_count', '')}`",
        "",
        "| Release id | Base | Lot size | Delivery status | Exact full-scale CERTIFIED | Generated at | Blueprint |",
        "|---|---|---:|---|---|---|---|",
    ]
    for entry in releases:
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{entry.get('release_id', '')}`",
                    f"`{entry.get('base_id', '')}`",
                    str(entry.get("lot_size", "")),
                    f"`{entry.get('delivery_status', '')}`",
                    f"`{entry.get('exact_full_scale_certified_status', '')}`",
                    f"`{entry.get('generated_at', '')}`",
                    f"`{entry.get('blueprint', '')}`",
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)



def build_single_base_delivery_release(
    *,
    source_run_dir: Path = _DEFAULT_SOURCE_RUN_DIR,
    release_root: Path = _DEFAULT_RELEASE_ROOT,
    release_id: str | None = None,
    pointer_json_path: Path = _DEFAULT_POINTER_JSON_PATH,
    pointer_markdown_path: Path = _DEFAULT_POINTER_MARKDOWN_PATH,
    index_json_path: Path | None = _DEFAULT_INDEX_JSON_PATH,
    index_markdown_path: Path | None = _DEFAULT_INDEX_MARKDOWN_PATH,
    viewer_root: Path = _DEFAULT_VIEWER_ROOT,
    viewer_pointer_json_path: Path = _DEFAULT_VIEWER_POINTER_JSON_PATH,
    viewer_pointer_markdown_path: Path = _DEFAULT_VIEWER_POINTER_MARKDOWN_PATH,
    viewer_index_json_path: Path | None = _DEFAULT_VIEWER_INDEX_JSON_PATH,
    viewer_index_markdown_path: Path | None = _DEFAULT_VIEWER_INDEX_MARKDOWN_PATH,
    viewer_candidate_placements_path: Path = _DEFAULT_VIEWER_CANDIDATE_PLACEMENTS_PATH,
    viewer_rules_json_path: Path = _DEFAULT_VIEWER_RULES_JSON_PATH,
    viewer_html_path: Path = _DEFAULT_VIEWER_HTML_PATH,
    landing_output_dir: Path | None = _DEFAULT_LANDING_OUTPUT_DIR,
    frontdoor_output_dir: Path | None = _DEFAULT_FRONTDOOR_OUTPUT_DIR,
    entrypoints_json_path: Path | None = None,
    entrypoints_markdown_path: Path | None = None,
    surface_alignment_json_path: Path | None = _DEFAULT_SURFACE_ALIGNMENT_JSON_PATH,
    surface_alignment_markdown_path: Path | None = _DEFAULT_SURFACE_ALIGNMENT_MARKDOWN_PATH,
    surface_alignment_console_path: Path | None = _DEFAULT_SURFACE_ALIGNMENT_CONSOLE_PATH,
    surface_health_json_path: Path | None = _DEFAULT_SURFACE_HEALTH_JSON_PATH,
    surface_health_markdown_path: Path | None = _DEFAULT_SURFACE_HEALTH_MARKDOWN_PATH,
    surface_health_console_path: Path | None = _DEFAULT_SURFACE_HEALTH_CONSOLE_PATH,
    base_id: str = DEFAULT_BASE_ID,
    refresh_run: bool = False,
    overwrite: bool = False,
    build_viewer_bundle: bool = True,
    build_landing_bundle: bool = True,
    build_frontdoor: bool = True,
    build_entrypoints: bool = True,
    audit_surface_alignment: bool = True,
) -> SingleBaseDeliveryReleaseResult:
    source_run_dir = Path(source_run_dir)
    release_root = Path(release_root)
    pointer_json_path = Path(pointer_json_path)
    pointer_markdown_path = Path(pointer_markdown_path)
    resolved_index_json_path = Path(index_json_path) if index_json_path is not None else None
    resolved_index_markdown_path = Path(index_markdown_path) if index_markdown_path is not None else None
    resolved_viewer_root = Path(viewer_root)
    resolved_viewer_pointer_json_path = Path(viewer_pointer_json_path)
    resolved_viewer_pointer_markdown_path = Path(viewer_pointer_markdown_path)
    resolved_viewer_index_json_path = Path(viewer_index_json_path) if viewer_index_json_path is not None else None
    resolved_viewer_index_markdown_path = (
        Path(viewer_index_markdown_path) if viewer_index_markdown_path is not None else None
    )
    resolved_viewer_candidate_placements_path = Path(viewer_candidate_placements_path)
    resolved_viewer_rules_json_path = Path(viewer_rules_json_path)
    resolved_viewer_html_path = Path(viewer_html_path)
    resolved_landing_output_dir = Path(landing_output_dir) if landing_output_dir is not None else None
    resolved_frontdoor_output_dir = Path(frontdoor_output_dir) if frontdoor_output_dir is not None else None
    resolved_entrypoints_json_path = Path(entrypoints_json_path) if entrypoints_json_path is not None else None
    resolved_entrypoints_markdown_path = Path(entrypoints_markdown_path) if entrypoints_markdown_path is not None else None
    resolved_surface_alignment_json_path = (
        Path(surface_alignment_json_path) if surface_alignment_json_path is not None else None
    )
    resolved_surface_alignment_markdown_path = (
        Path(surface_alignment_markdown_path) if surface_alignment_markdown_path is not None else None
    )
    resolved_surface_alignment_console_path = (
        Path(surface_alignment_console_path) if surface_alignment_console_path is not None else None
    )
    resolved_surface_health_json_path = (
        Path(surface_health_json_path) if surface_health_json_path is not None else None
    )
    resolved_surface_health_markdown_path = (
        Path(surface_health_markdown_path) if surface_health_markdown_path is not None else None
    )
    resolved_surface_health_console_path = (
        Path(surface_health_console_path) if surface_health_console_path is not None else None
    )
    resolved_release_id = _normalize_release_id(release_id, base_id=base_id)
    release_dir = release_root / resolved_release_id
    viewer_output_dir = resolved_viewer_root / resolved_release_id if build_viewer_bundle else None
    if build_landing_bundle and not build_viewer_bundle:
        raise SingleBaseDeliveryReleaseError(
            "current landing bundle refresh requires build_viewer_bundle=True so the active viewer pointer stays in sync"
        )
    if build_frontdoor and not build_landing_bundle:
        raise SingleBaseDeliveryReleaseError(
            "repo front door refresh requires build_landing_bundle=True so the stable current landing stays in sync"
        )
    if build_entrypoints and not build_frontdoor:
        raise SingleBaseDeliveryReleaseError(
            "active entrypoints refresh requires build_frontdoor=True so the repo-front current entry stays in sync"
        )
    if audit_surface_alignment and not build_entrypoints:
        raise SingleBaseDeliveryReleaseError(
            "surface alignment audit requires build_entrypoints=True so the repo-front and aggregate current-entrypoint surfaces stay in sync"
        )
    resolved_build_landing_bundle = build_viewer_bundle and build_landing_bundle and resolved_landing_output_dir is not None
    resolved_build_frontdoor = resolved_build_landing_bundle and build_frontdoor and resolved_frontdoor_output_dir is not None
    resolved_build_entrypoints = resolved_build_frontdoor and build_entrypoints
    if resolved_build_entrypoints and resolved_frontdoor_output_dir is not None:
        if resolved_entrypoints_json_path is None:
            resolved_entrypoints_json_path = resolved_frontdoor_output_dir / _ENTRYPOINTS_JSON_FILENAME
        if resolved_entrypoints_markdown_path is None:
            resolved_entrypoints_markdown_path = resolved_frontdoor_output_dir / _ENTRYPOINTS_MARKDOWN_FILENAME
    resolved_audit_surface_alignment = resolved_build_entrypoints and audit_surface_alignment
    if resolved_audit_surface_alignment and (
        resolved_surface_alignment_json_path is None
        or resolved_surface_alignment_markdown_path is None
        or resolved_surface_alignment_console_path is None
    ):
        raise SingleBaseDeliveryReleaseError(
            "surface alignment audit requires JSON/Markdown/console output paths when the audit is enabled"
        )
    resolved_build_surface_health = resolved_audit_surface_alignment
    if resolved_build_surface_health and (
        resolved_surface_health_json_path is None
        or resolved_surface_health_markdown_path is None
        or resolved_surface_health_console_path is None
    ):
        raise SingleBaseDeliveryReleaseError(
            "current surface health build requires JSON/Markdown/console output paths when the surface alignment audit is enabled"
        )

    tracked_paths: list[Path] = [pointer_json_path, pointer_markdown_path]
    if resolved_index_json_path is not None:
        tracked_paths.append(resolved_index_json_path)
    if resolved_index_markdown_path is not None:
        tracked_paths.append(resolved_index_markdown_path)
    if build_viewer_bundle:
        tracked_paths.extend(
            [
                resolved_viewer_pointer_json_path,
                resolved_viewer_pointer_markdown_path,
            ]
        )
        if resolved_viewer_index_json_path is not None:
            tracked_paths.append(resolved_viewer_index_json_path)
        if resolved_viewer_index_markdown_path is not None:
            tracked_paths.append(resolved_viewer_index_markdown_path)
    if resolved_build_frontdoor and resolved_frontdoor_output_dir is not None:
        tracked_paths.extend(
            [
                resolved_frontdoor_output_dir / _FRONTDOOR_MANIFEST_JSON_FILENAME,
                resolved_frontdoor_output_dir / _FRONTDOOR_INDEX_HTML_FILENAME,
                resolved_frontdoor_output_dir / _LATEST_BUNDLE_ZIP_FILENAME,
                resolved_frontdoor_output_dir / _LATEST_BUNDLE_POINTER_JSON_FILENAME,
                resolved_frontdoor_output_dir / _LATEST_BUNDLE_POINTER_MARKDOWN_FILENAME,
            ]
        )
    if resolved_build_entrypoints:
        if resolved_entrypoints_json_path is not None:
            tracked_paths.append(resolved_entrypoints_json_path)
        if resolved_entrypoints_markdown_path is not None:
            tracked_paths.append(resolved_entrypoints_markdown_path)
    if resolved_audit_surface_alignment:
        if resolved_surface_alignment_json_path is not None:
            tracked_paths.append(resolved_surface_alignment_json_path)
        if resolved_surface_alignment_markdown_path is not None:
            tracked_paths.append(resolved_surface_alignment_markdown_path)
        if resolved_surface_alignment_console_path is not None:
            tracked_paths.append(resolved_surface_alignment_console_path)
    if resolved_build_surface_health:
        if resolved_surface_health_json_path is not None:
            tracked_paths.append(resolved_surface_health_json_path)
        if resolved_surface_health_markdown_path is not None:
            tracked_paths.append(resolved_surface_health_markdown_path)
        if resolved_surface_health_console_path is not None:
            tracked_paths.append(resolved_surface_health_console_path)
    file_backups = {path: _read_text_if_exists(path) for path in tracked_paths}
    landing_dir_existed_before = bool(
        resolved_build_landing_bundle and resolved_landing_output_dir is not None and resolved_landing_output_dir.exists()
    )
    landing_output_dir_backup = _backup_directory_if_exists(resolved_landing_output_dir) if resolved_build_landing_bundle else None

    release_dir_created = False
    viewer_bundle_status = "skipped"
    viewer_manifest_path: Path | None = None
    viewer_selected_facility_type_count: int | None = None
    viewer_selected_pose_count: int | None = None
    viewer_payload_download_count: int | None = None
    viewer_metadata_download_count: int | None = None
    viewer_quick_download_count: int | None = None
    landing_bundle_status = "skipped"
    landing_manifest_path: Path | None = None
    landing_index_html_path: Path | None = None
    landing_quick_download_count: int | None = None
    landing_download_group_count: int | None = None
    frontdoor_bundle_status = "skipped"
    frontdoor_manifest_path: Path | None = None
    frontdoor_index_html_path: Path | None = None
    frontdoor_quick_download_count: int | None = None
    frontdoor_download_group_count: int | None = None
    entrypoints_bundle_status = "skipped"
    resolved_entrypoints_json_output_path: Path | None = None
    resolved_entrypoints_markdown_output_path: Path | None = None
    entrypoints_action_count: int | None = None
    entrypoints_group_count: int | None = None
    surface_alignment_status = "skipped"
    resolved_surface_alignment_json_output_path: Path | None = None
    resolved_surface_alignment_markdown_output_path: Path | None = None
    resolved_surface_alignment_console_output_path: Path | None = None
    surface_alignment_check_count: int | None = None
    surface_alignment_drift_check_count: int | None = None
    surface_health_status = "skipped"
    resolved_surface_health_json_output_path: Path | None = None
    resolved_surface_health_markdown_output_path: Path | None = None
    resolved_surface_health_console_output_path: Path | None = None
    surface_health_check_count: int | None = None
    surface_health_drift_check_count: int | None = None

    try:
        if refresh_run:
            if source_run_dir.exists():
                shutil.rmtree(source_run_dir)
            run_single_base_e2e_workflow(run_dir=source_run_dir, base_id=base_id)

        run_summary_path = source_run_dir / "run_summary.json"
        summary = _load_json(run_summary_path)
        _validate_ready_run_summary(summary, expected_base_id=base_id)

        if release_dir.exists():
            if not overwrite:
                raise SingleBaseDeliveryReleaseError(
                    f"release directory already exists: {_display_path(release_dir)}"
                )
            shutil.rmtree(release_dir)
        if viewer_output_dir is not None and viewer_output_dir.exists():
            if not overwrite:
                raise SingleBaseDeliveryReleaseError(
                    f"viewer directory already exists: {_display_path(viewer_output_dir)}"
                )
            shutil.rmtree(viewer_output_dir)

        release_dir.mkdir(parents=True, exist_ok=True)
        release_dir_created = True

        artifacts = _copy_release_payload(source_run_dir=source_run_dir, release_dir=release_dir)
        release_payload = _build_release_manifest_payload(
            summary=summary,
            release_id=resolved_release_id,
            base_id=base_id,
            source_run_dir=source_run_dir,
            release_dir=release_dir,
            pointer_json_path=pointer_json_path,
            pointer_markdown_path=pointer_markdown_path,
            index_json_path=resolved_index_json_path,
            index_markdown_path=resolved_index_markdown_path,
            artifacts=artifacts,
        )

        release_manifest_json_path = release_dir / _RELEASE_MANIFEST_JSON_FILENAME
        release_manifest_markdown_path = release_dir / _RELEASE_MANIFEST_MARKDOWN_FILENAME
        atomic_write_json(release_manifest_json_path, release_payload)
        _write_text(release_manifest_markdown_path, _render_release_manifest_markdown(release_payload))
        sha256sums_path = _write_sha256sums(
            release_dir=release_dir,
            artifacts=artifacts,
            include_paths=(release_manifest_json_path, release_manifest_markdown_path),
        )

        pointer_payload = _build_pointer_payload(
            release_payload=release_payload,
            pointer_json_path=pointer_json_path,
            pointer_markdown_path=pointer_markdown_path,
        )
        atomic_write_json(pointer_json_path, pointer_payload)
        _write_text(pointer_markdown_path, _render_pointer_markdown(pointer_payload))

        if resolved_index_json_path is not None or resolved_index_markdown_path is not None:
            index_payload = _build_release_index_payload(
                release_root=release_root,
                current_release_id=resolved_release_id,
                index_json_path=resolved_index_json_path,
                index_markdown_path=resolved_index_markdown_path,
            )
            if resolved_index_json_path is not None:
                atomic_write_json(resolved_index_json_path, index_payload)
            if resolved_index_markdown_path is not None:
                _write_text(resolved_index_markdown_path, _render_release_index_markdown(index_payload))

        if build_viewer_bundle:
            viewer_bundle_status = "building"
            try:
                viewer_result = build_single_base_delivery_viewer_bundle(
                    project_root=PROJECT_ROOT,
                    pointer_json_path=pointer_json_path,
                    output_dir=viewer_output_dir if viewer_output_dir is not None else resolved_viewer_root,
                    candidate_placements_path=resolved_viewer_candidate_placements_path,
                    rules_json_path=resolved_viewer_rules_json_path,
                    viewer_html_path=resolved_viewer_html_path,
                )
            except SingleBaseDeliveryViewerBundleError as exc:
                raise SingleBaseDeliveryReleaseError(
                    f"viewer bundle build failed for release {resolved_release_id!r}: {exc}"
                ) from exc

            viewer_manifest_path = viewer_result.viewer_manifest_path
            viewer_manifest_payload = _load_json(viewer_manifest_path)
            viewer_selected_facility_type_count = viewer_result.selected_facility_type_count
            viewer_selected_pose_count = viewer_result.selected_pose_count
            viewer_payload_download_count = viewer_result.payload_download_count
            viewer_metadata_download_count = viewer_result.metadata_download_count
            viewer_quick_download_count = viewer_result.quick_download_count

            viewer_pointer_payload = _build_viewer_pointer_payload(
                viewer_output_dir=viewer_result.output_dir,
                viewer_manifest_payload=viewer_manifest_payload,
                viewer_pointer_json_path=resolved_viewer_pointer_json_path,
                viewer_pointer_markdown_path=resolved_viewer_pointer_markdown_path,
                release_pointer_json_path=pointer_json_path,
                release_pointer_markdown_path=pointer_markdown_path,
            )
            atomic_write_json(resolved_viewer_pointer_json_path, viewer_pointer_payload)
            _write_text(
                resolved_viewer_pointer_markdown_path,
                _render_viewer_pointer_markdown(viewer_pointer_payload),
            )

            if resolved_viewer_index_json_path is not None or resolved_viewer_index_markdown_path is not None:
                viewer_index_payload = _build_viewer_index_payload(
                    viewer_root=resolved_viewer_root,
                    current_release_id=resolved_release_id,
                    index_json_path=resolved_viewer_index_json_path,
                    index_markdown_path=resolved_viewer_index_markdown_path,
                )
                if resolved_viewer_index_json_path is not None:
                    atomic_write_json(resolved_viewer_index_json_path, viewer_index_payload)
                if resolved_viewer_index_markdown_path is not None:
                    _write_text(
                        resolved_viewer_index_markdown_path,
                        _render_viewer_index_markdown(viewer_index_payload),
                    )
            viewer_bundle_status = "built"

            if resolved_build_landing_bundle:
                landing_bundle_status = "building"
                try:
                    landing_result = build_single_base_delivery_landing_bundle(
                        project_root=PROJECT_ROOT,
                        viewer_pointer_json_path=resolved_viewer_pointer_json_path,
                        output_dir=(
                            resolved_landing_output_dir
                            if resolved_landing_output_dir is not None
                            else _DEFAULT_LANDING_OUTPUT_DIR
                        ),
                    )
                except SingleBaseDeliveryLandingBundleError as exc:
                    raise SingleBaseDeliveryReleaseError(
                        f"landing bundle build failed for release {resolved_release_id!r}: {exc}"
                    ) from exc

                landing_manifest_path = landing_result.landing_manifest_path
                landing_index_html_path = landing_result.landing_index_html_path
                landing_quick_download_count = landing_result.quick_download_count
                landing_download_group_count = landing_result.download_group_count
                landing_bundle_status = "built"

                if resolved_build_frontdoor:
                    frontdoor_bundle_status = "building"
                    try:
                        frontdoor_result = build_single_base_delivery_frontdoor(
                            project_root=PROJECT_ROOT,
                            landing_manifest_json_path=landing_manifest_path,
                            output_dir=(
                                resolved_frontdoor_output_dir
                                if resolved_frontdoor_output_dir is not None
                                else _DEFAULT_FRONTDOOR_OUTPUT_DIR
                            ),
                            surface_alignment_json_path=None,
                            surface_alignment_markdown_path=None,
                            surface_alignment_console_path=None,
                            surface_health_json_path=None,
                            surface_health_markdown_path=None,
                            surface_health_console_path=None,
                        )
                    except SingleBaseDeliveryFrontdoorError as exc:
                        raise SingleBaseDeliveryReleaseError(
                            f"frontdoor build failed for release {resolved_release_id!r}: {exc}"
                        ) from exc

                    frontdoor_manifest_path = frontdoor_result.frontdoor_manifest_path
                    frontdoor_index_html_path = frontdoor_result.frontdoor_index_html_path
                    frontdoor_quick_download_count = frontdoor_result.quick_download_count
                    frontdoor_download_group_count = frontdoor_result.download_group_count
                    frontdoor_bundle_status = "built"

                    if resolved_build_entrypoints:
                        entrypoints_bundle_status = "building"
                        try:
                            entrypoints_result = build_single_base_delivery_entrypoints(
                                project_root=PROJECT_ROOT,
                                release_pointer_json_path=pointer_json_path,
                                viewer_pointer_json_path=resolved_viewer_pointer_json_path,
                                landing_manifest_json_path=landing_manifest_path,
                                frontdoor_manifest_json_path=frontdoor_manifest_path,
                                latest_bundle_pointer_json_path=(
                                    resolved_frontdoor_output_dir / _LATEST_BUNDLE_POINTER_JSON_FILENAME
                                    if resolved_frontdoor_output_dir is not None
                                    else _DEFAULT_FRONTDOOR_OUTPUT_DIR / _LATEST_BUNDLE_POINTER_JSON_FILENAME
                                ),
                                surface_alignment_json_path=None,
                                surface_alignment_markdown_path=None,
                                surface_alignment_console_path=None,
                                surface_health_json_path=None,
                                surface_health_markdown_path=None,
                                surface_health_console_path=None,
                                output_json_path=(
                                    resolved_entrypoints_json_path
                                    if resolved_entrypoints_json_path is not None
                                    else _DEFAULT_FRONTDOOR_OUTPUT_DIR / _ENTRYPOINTS_JSON_FILENAME
                                ),
                                output_markdown_path=(
                                    resolved_entrypoints_markdown_path
                                    if resolved_entrypoints_markdown_path is not None
                                    else _DEFAULT_FRONTDOOR_OUTPUT_DIR / _ENTRYPOINTS_MARKDOWN_FILENAME
                                ),
                            )
                        except SingleBaseDeliveryEntrypointsError as exc:
                            raise SingleBaseDeliveryReleaseError(
                                f"active entrypoints build failed for release {resolved_release_id!r}: {exc}"
                            ) from exc

                        resolved_entrypoints_json_output_path = entrypoints_result.output_json_path
                        resolved_entrypoints_markdown_output_path = entrypoints_result.output_markdown_path
                        entrypoints_action_count = entrypoints_result.action_count
                        entrypoints_group_count = entrypoints_result.entrypoint_group_count
                        entrypoints_bundle_status = "built"

                        try:
                            frontdoor_result = build_single_base_delivery_frontdoor(
                                project_root=PROJECT_ROOT,
                                landing_manifest_json_path=landing_manifest_path,
                                output_dir=(
                                    resolved_frontdoor_output_dir
                                    if resolved_frontdoor_output_dir is not None
                                    else _DEFAULT_FRONTDOOR_OUTPUT_DIR
                                ),
                                entrypoints_json_path=resolved_entrypoints_json_output_path,
                                entrypoints_markdown_path=resolved_entrypoints_markdown_output_path,
                                require_entrypoints=True,
                                surface_alignment_json_path=None,
                                surface_alignment_markdown_path=None,
                                surface_alignment_console_path=None,
                                surface_health_json_path=None,
                                surface_health_markdown_path=None,
                                surface_health_console_path=None,
                            )
                        except SingleBaseDeliveryFrontdoorError as exc:
                            raise SingleBaseDeliveryReleaseError(
                                f"frontdoor refresh after active entrypoints build failed for release {resolved_release_id!r}: {exc}"
                            ) from exc

                        frontdoor_manifest_path = frontdoor_result.frontdoor_manifest_path
                        frontdoor_index_html_path = frontdoor_result.frontdoor_index_html_path
                        frontdoor_quick_download_count = frontdoor_result.quick_download_count
                        frontdoor_download_group_count = frontdoor_result.download_group_count

                        if resolved_audit_surface_alignment:
                            surface_alignment_status = "auditing"
                            try:
                                surface_alignment_result = build_single_base_delivery_surface_alignment_result(
                                    project_root=PROJECT_ROOT,
                                    frontdoor_manifest_json_path=frontdoor_manifest_path,
                                    entrypoints_json_path=(
                                        resolved_entrypoints_json_output_path
                                        if resolved_entrypoints_json_output_path is not None
                                        else (
                                            resolved_entrypoints_json_path
                                            if resolved_entrypoints_json_path is not None
                                            else _DEFAULT_FRONTDOOR_OUTPUT_DIR / _ENTRYPOINTS_JSON_FILENAME
                                        )
                                    ),
                                    entrypoints_markdown_path=(
                                        resolved_entrypoints_markdown_output_path
                                        if resolved_entrypoints_markdown_output_path is not None
                                        else (
                                            resolved_entrypoints_markdown_path
                                            if resolved_entrypoints_markdown_path is not None
                                            else _DEFAULT_FRONTDOOR_OUTPUT_DIR / _ENTRYPOINTS_MARKDOWN_FILENAME
                                        )
                                    ),
                                    surface_alignment_json_path=(
                                        resolved_surface_alignment_json_path
                                        if resolved_surface_alignment_json_path is not None
                                        else _DEFAULT_SURFACE_ALIGNMENT_JSON_PATH
                                    ),
                                    surface_alignment_markdown_path=(
                                        resolved_surface_alignment_markdown_path
                                        if resolved_surface_alignment_markdown_path is not None
                                        else _DEFAULT_SURFACE_ALIGNMENT_MARKDOWN_PATH
                                    ),
                                    surface_alignment_console_path=(
                                        resolved_surface_alignment_console_path
                                        if resolved_surface_alignment_console_path is not None
                                        else _DEFAULT_SURFACE_ALIGNMENT_CONSOLE_PATH
                                    ),
                                    require_surface_alignment_visibility=False,
                                    require_surface_health_visibility=False,
                                )
                                surface_alignment_outputs = write_single_base_delivery_surface_alignment_outputs(
                                    surface_alignment_result,
                                    json_output_path=(
                                        resolved_surface_alignment_json_path
                                        if resolved_surface_alignment_json_path is not None
                                        else _DEFAULT_SURFACE_ALIGNMENT_JSON_PATH
                                    ),
                                    markdown_output_path=(
                                        resolved_surface_alignment_markdown_path
                                        if resolved_surface_alignment_markdown_path is not None
                                        else _DEFAULT_SURFACE_ALIGNMENT_MARKDOWN_PATH
                                    ),
                                    console_output_path=(
                                        resolved_surface_alignment_console_path
                                        if resolved_surface_alignment_console_path is not None
                                        else _DEFAULT_SURFACE_ALIGNMENT_CONSOLE_PATH
                                    ),
                                )
                            except (SingleBaseDeliverySurfaceAlignmentError, OSError, ValueError) as exc:
                                raise SingleBaseDeliveryReleaseError(
                                    f"surface alignment audit failed for release {resolved_release_id!r}: {exc}"
                                ) from exc

                            resolved_surface_alignment_json_output_path = surface_alignment_outputs.json_output_path
                            resolved_surface_alignment_markdown_output_path = surface_alignment_outputs.markdown_output_path
                            resolved_surface_alignment_console_output_path = surface_alignment_outputs.console_output_path
                            surface_alignment_check_count = surface_alignment_result.checked_check_count
                            surface_alignment_drift_check_count = surface_alignment_result.drift_check_count
                            if not surface_alignment_result.is_clean:
                                raise SingleBaseDeliveryReleaseError(
                                    f"surface alignment audit failed for release {resolved_release_id!r}: drift_detected"
                                )

                            try:
                                entrypoints_result = build_single_base_delivery_entrypoints(
                                    project_root=PROJECT_ROOT,
                                    release_pointer_json_path=pointer_json_path,
                                    viewer_pointer_json_path=resolved_viewer_pointer_json_path,
                                    landing_manifest_json_path=landing_manifest_path,
                                    frontdoor_manifest_json_path=frontdoor_manifest_path,
                                    latest_bundle_pointer_json_path=(
                                        resolved_frontdoor_output_dir / _LATEST_BUNDLE_POINTER_JSON_FILENAME
                                        if resolved_frontdoor_output_dir is not None
                                        else _DEFAULT_FRONTDOOR_OUTPUT_DIR / _LATEST_BUNDLE_POINTER_JSON_FILENAME
                                    ),
                                    surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                                    surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                                    surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                                    require_surface_alignment=True,
                                    surface_health_json_path=None,
                                    surface_health_markdown_path=None,
                                    surface_health_console_path=None,
                                    output_json_path=(
                                        resolved_entrypoints_json_output_path
                                        if resolved_entrypoints_json_output_path is not None
                                        else (
                                            resolved_entrypoints_json_path
                                            if resolved_entrypoints_json_path is not None
                                            else _DEFAULT_FRONTDOOR_OUTPUT_DIR / _ENTRYPOINTS_JSON_FILENAME
                                        )
                                    ),
                                    output_markdown_path=(
                                        resolved_entrypoints_markdown_output_path
                                        if resolved_entrypoints_markdown_output_path is not None
                                        else (
                                            resolved_entrypoints_markdown_path
                                            if resolved_entrypoints_markdown_path is not None
                                            else _DEFAULT_FRONTDOOR_OUTPUT_DIR / _ENTRYPOINTS_MARKDOWN_FILENAME
                                        )
                                    ),
                                )
                            except SingleBaseDeliveryEntrypointsError as exc:
                                raise SingleBaseDeliveryReleaseError(
                                    f"active entrypoints refresh after surface alignment audit failed for release {resolved_release_id!r}: {exc}"
                                ) from exc

                            resolved_entrypoints_json_output_path = entrypoints_result.output_json_path
                            resolved_entrypoints_markdown_output_path = entrypoints_result.output_markdown_path
                            entrypoints_action_count = entrypoints_result.action_count
                            entrypoints_group_count = entrypoints_result.entrypoint_group_count

                            try:
                                frontdoor_result = build_single_base_delivery_frontdoor(
                                    project_root=PROJECT_ROOT,
                                    landing_manifest_json_path=landing_manifest_path,
                                    output_dir=(
                                        resolved_frontdoor_output_dir
                                        if resolved_frontdoor_output_dir is not None
                                        else _DEFAULT_FRONTDOOR_OUTPUT_DIR
                                    ),
                                    entrypoints_json_path=resolved_entrypoints_json_output_path,
                                    entrypoints_markdown_path=resolved_entrypoints_markdown_output_path,
                                    require_entrypoints=True,
                                    surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                                    surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                                    surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                                    require_surface_alignment=True,
                                    surface_health_json_path=None,
                                    surface_health_markdown_path=None,
                                    surface_health_console_path=None,
                                )
                            except SingleBaseDeliveryFrontdoorError as exc:
                                raise SingleBaseDeliveryReleaseError(
                                    f"frontdoor refresh after surface alignment audit failed for release {resolved_release_id!r}: {exc}"
                                ) from exc

                            frontdoor_manifest_path = frontdoor_result.frontdoor_manifest_path
                            frontdoor_index_html_path = frontdoor_result.frontdoor_index_html_path
                            frontdoor_quick_download_count = frontdoor_result.quick_download_count
                            frontdoor_download_group_count = frontdoor_result.download_group_count

                            try:
                                surface_alignment_result = build_single_base_delivery_surface_alignment_result(
                                    project_root=PROJECT_ROOT,
                                    frontdoor_manifest_json_path=frontdoor_manifest_path,
                                    entrypoints_json_path=resolved_entrypoints_json_output_path,
                                    entrypoints_markdown_path=resolved_entrypoints_markdown_output_path,
                                    surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                                    surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                                    surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                                    require_surface_alignment_visibility=True,
                                    require_surface_health_visibility=False,
                                )
                                surface_alignment_outputs = write_single_base_delivery_surface_alignment_outputs(
                                    surface_alignment_result,
                                    json_output_path=resolved_surface_alignment_json_output_path,
                                    markdown_output_path=resolved_surface_alignment_markdown_output_path,
                                    console_output_path=resolved_surface_alignment_console_output_path,
                                )
                            except (SingleBaseDeliverySurfaceAlignmentError, OSError, ValueError) as exc:
                                raise SingleBaseDeliveryReleaseError(
                                    f"surface alignment audit refresh failed for release {resolved_release_id!r}: {exc}"
                                ) from exc

                            resolved_surface_alignment_json_output_path = surface_alignment_outputs.json_output_path
                            resolved_surface_alignment_markdown_output_path = surface_alignment_outputs.markdown_output_path
                            resolved_surface_alignment_console_output_path = surface_alignment_outputs.console_output_path
                            surface_alignment_check_count = surface_alignment_result.checked_check_count
                            surface_alignment_drift_check_count = surface_alignment_result.drift_check_count
                            if not surface_alignment_result.is_clean:
                                raise SingleBaseDeliveryReleaseError(
                                    f"surface alignment audit refresh failed for release {resolved_release_id!r}: drift_detected"
                                )

                            try:
                                entrypoints_result = build_single_base_delivery_entrypoints(
                                    project_root=PROJECT_ROOT,
                                    release_pointer_json_path=pointer_json_path,
                                    viewer_pointer_json_path=resolved_viewer_pointer_json_path,
                                    landing_manifest_json_path=landing_manifest_path,
                                    frontdoor_manifest_json_path=frontdoor_manifest_path,
                                    latest_bundle_pointer_json_path=(
                                        resolved_frontdoor_output_dir / _LATEST_BUNDLE_POINTER_JSON_FILENAME
                                        if resolved_frontdoor_output_dir is not None
                                        else _DEFAULT_FRONTDOOR_OUTPUT_DIR / _LATEST_BUNDLE_POINTER_JSON_FILENAME
                                    ),
                                    surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                                    surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                                    surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                                    require_surface_alignment=True,
                                    surface_health_json_path=None,
                                    surface_health_markdown_path=None,
                                    surface_health_console_path=None,
                                    output_json_path=resolved_entrypoints_json_output_path,
                                    output_markdown_path=resolved_entrypoints_markdown_output_path,
                                )
                            except SingleBaseDeliveryEntrypointsError as exc:
                                raise SingleBaseDeliveryReleaseError(
                                    f"active entrypoints closing refresh after surface alignment audit failed for release {resolved_release_id!r}: {exc}"
                                ) from exc

                            resolved_entrypoints_json_output_path = entrypoints_result.output_json_path
                            resolved_entrypoints_markdown_output_path = entrypoints_result.output_markdown_path
                            entrypoints_action_count = entrypoints_result.action_count
                            entrypoints_group_count = entrypoints_result.entrypoint_group_count

                            try:
                                frontdoor_result = build_single_base_delivery_frontdoor(
                                    project_root=PROJECT_ROOT,
                                    landing_manifest_json_path=landing_manifest_path,
                                    output_dir=(
                                        resolved_frontdoor_output_dir
                                        if resolved_frontdoor_output_dir is not None
                                        else _DEFAULT_FRONTDOOR_OUTPUT_DIR
                                    ),
                                    entrypoints_json_path=resolved_entrypoints_json_output_path,
                                    entrypoints_markdown_path=resolved_entrypoints_markdown_output_path,
                                    require_entrypoints=True,
                                    surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                                    surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                                    surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                                    require_surface_alignment=True,
                                    surface_health_json_path=None,
                                    surface_health_markdown_path=None,
                                    surface_health_console_path=None,
                                )
                            except SingleBaseDeliveryFrontdoorError as exc:
                                raise SingleBaseDeliveryReleaseError(
                                    f"frontdoor closing refresh after surface alignment audit failed for release {resolved_release_id!r}: {exc}"
                                ) from exc

                            frontdoor_manifest_path = frontdoor_result.frontdoor_manifest_path
                            frontdoor_index_html_path = frontdoor_result.frontdoor_index_html_path
                            frontdoor_quick_download_count = frontdoor_result.quick_download_count
                            frontdoor_download_group_count = frontdoor_result.download_group_count

                            previous_surface_alignment_check_count = surface_alignment_check_count
                            previous_surface_alignment_drift_check_count = surface_alignment_drift_check_count

                            try:
                                surface_alignment_result = build_single_base_delivery_surface_alignment_result(
                                    project_root=PROJECT_ROOT,
                                    frontdoor_manifest_json_path=frontdoor_manifest_path,
                                    entrypoints_json_path=resolved_entrypoints_json_output_path,
                                    entrypoints_markdown_path=resolved_entrypoints_markdown_output_path,
                                    surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                                    surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                                    surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                                    require_surface_alignment_visibility=True,
                                    require_surface_health_visibility=False,
                                )
                                surface_alignment_outputs = write_single_base_delivery_surface_alignment_outputs(
                                    surface_alignment_result,
                                    json_output_path=resolved_surface_alignment_json_output_path,
                                    markdown_output_path=resolved_surface_alignment_markdown_output_path,
                                    console_output_path=resolved_surface_alignment_console_output_path,
                                )
                            except (SingleBaseDeliverySurfaceAlignmentError, OSError, ValueError) as exc:
                                raise SingleBaseDeliveryReleaseError(
                                    f"surface alignment closing audit failed for release {resolved_release_id!r}: {exc}"
                                ) from exc

                            resolved_surface_alignment_json_output_path = surface_alignment_outputs.json_output_path
                            resolved_surface_alignment_markdown_output_path = surface_alignment_outputs.markdown_output_path
                            resolved_surface_alignment_console_output_path = surface_alignment_outputs.console_output_path
                            surface_alignment_check_count = surface_alignment_result.checked_check_count
                            surface_alignment_drift_check_count = surface_alignment_result.drift_check_count
                            if not surface_alignment_result.is_clean:
                                raise SingleBaseDeliveryReleaseError(
                                    f"surface alignment closing audit failed for release {resolved_release_id!r}: drift_detected"
                                )
                            if (
                                previous_surface_alignment_check_count is not None
                                and previous_surface_alignment_drift_check_count is not None
                                and (
                                    surface_alignment_check_count != previous_surface_alignment_check_count
                                    or surface_alignment_drift_check_count
                                    != previous_surface_alignment_drift_check_count
                                )
                            ):
                                raise SingleBaseDeliveryReleaseError(
                                    f"surface alignment closing audit failed for release {resolved_release_id!r}: audit metadata did not converge after the final frontdoor/entrypoints refresh"
                                )
                            surface_alignment_status = "clean"

        if resolved_build_surface_health:
            surface_health_status = "building"
            try:
                surface_health_result = build_single_base_delivery_surface_health(
                    project_root=PROJECT_ROOT,
                    surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                    surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                    surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                    output_json_path=resolved_surface_health_json_path,
                    output_markdown_path=resolved_surface_health_markdown_path,
                    output_console_path=resolved_surface_health_console_path,
                )
            except SingleBaseDeliverySurfaceHealthError as exc:
                raise SingleBaseDeliveryReleaseError(
                    f"current surface health build failed for release {resolved_release_id!r}: {exc}"
                ) from exc

            resolved_surface_health_json_output_path = surface_health_result.output_json_path
            resolved_surface_health_markdown_output_path = surface_health_result.output_markdown_path
            resolved_surface_health_console_output_path = surface_health_result.output_console_path
            surface_health_check_count = surface_health_result.checked_check_count
            surface_health_drift_check_count = surface_health_result.drift_check_count
            surface_health_status = surface_health_result.status

            if resolved_build_entrypoints and resolved_build_frontdoor:
                try:
                    entrypoints_result = build_single_base_delivery_entrypoints(
                        project_root=PROJECT_ROOT,
                        release_pointer_json_path=pointer_json_path,
                        viewer_pointer_json_path=resolved_viewer_pointer_json_path,
                        landing_manifest_json_path=landing_manifest_path,
                        frontdoor_manifest_json_path=frontdoor_manifest_path,
                        latest_bundle_pointer_json_path=(
                            resolved_frontdoor_output_dir / _LATEST_BUNDLE_POINTER_JSON_FILENAME
                            if resolved_frontdoor_output_dir is not None
                            else _DEFAULT_FRONTDOOR_OUTPUT_DIR / _LATEST_BUNDLE_POINTER_JSON_FILENAME
                        ),
                        surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                        surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                        surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                        require_surface_alignment=True,
                        surface_health_json_path=resolved_surface_health_json_output_path,
                        surface_health_markdown_path=resolved_surface_health_markdown_output_path,
                        surface_health_console_path=resolved_surface_health_console_output_path,
                        require_surface_health=True,
                        output_json_path=resolved_entrypoints_json_output_path,
                        output_markdown_path=resolved_entrypoints_markdown_output_path,
                    )
                except SingleBaseDeliveryEntrypointsError as exc:
                    raise SingleBaseDeliveryReleaseError(
                        f"active entrypoints refresh after current surface health build failed for release {resolved_release_id!r}: {exc}"
                    ) from exc

                resolved_entrypoints_json_output_path = entrypoints_result.output_json_path
                resolved_entrypoints_markdown_output_path = entrypoints_result.output_markdown_path
                entrypoints_action_count = entrypoints_result.action_count
                entrypoints_group_count = entrypoints_result.entrypoint_group_count

                try:
                    frontdoor_result = build_single_base_delivery_frontdoor(
                        project_root=PROJECT_ROOT,
                        landing_manifest_json_path=landing_manifest_path,
                        output_dir=(
                            resolved_frontdoor_output_dir
                            if resolved_frontdoor_output_dir is not None
                            else _DEFAULT_FRONTDOOR_OUTPUT_DIR
                        ),
                        entrypoints_json_path=resolved_entrypoints_json_output_path,
                        entrypoints_markdown_path=resolved_entrypoints_markdown_output_path,
                        require_entrypoints=True,
                        surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                        surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                        surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                        require_surface_alignment=True,
                        surface_health_json_path=resolved_surface_health_json_output_path,
                        surface_health_markdown_path=resolved_surface_health_markdown_output_path,
                        surface_health_console_path=resolved_surface_health_console_output_path,
                        require_surface_health=True,
                    )
                except SingleBaseDeliveryFrontdoorError as exc:
                    raise SingleBaseDeliveryReleaseError(
                        f"frontdoor refresh after current surface health build failed for release {resolved_release_id!r}: {exc}"
                    ) from exc

                frontdoor_manifest_path = frontdoor_result.frontdoor_manifest_path
                frontdoor_index_html_path = frontdoor_result.frontdoor_index_html_path
                frontdoor_quick_download_count = frontdoor_result.quick_download_count
                frontdoor_download_group_count = frontdoor_result.download_group_count

                previous_surface_alignment_check_count = surface_alignment_check_count
                previous_surface_alignment_drift_check_count = surface_alignment_drift_check_count

                try:
                    surface_alignment_result = build_single_base_delivery_surface_alignment_result(
                        project_root=PROJECT_ROOT,
                        frontdoor_manifest_json_path=frontdoor_manifest_path,
                        entrypoints_json_path=resolved_entrypoints_json_output_path,
                        entrypoints_markdown_path=resolved_entrypoints_markdown_output_path,
                        surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                        surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                        surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                        current_surface_health_json_path=resolved_surface_health_json_output_path,
                        current_surface_health_markdown_path=resolved_surface_health_markdown_output_path,
                        current_surface_health_console_path=resolved_surface_health_console_output_path,
                        require_surface_alignment_visibility=True,
                        require_surface_health_visibility=True,
                    )
                    surface_alignment_outputs = write_single_base_delivery_surface_alignment_outputs(
                        surface_alignment_result,
                        json_output_path=resolved_surface_alignment_json_output_path,
                        markdown_output_path=resolved_surface_alignment_markdown_output_path,
                        console_output_path=resolved_surface_alignment_console_output_path,
                    )
                except (SingleBaseDeliverySurfaceAlignmentError, OSError, ValueError) as exc:
                    raise SingleBaseDeliveryReleaseError(
                        f"surface alignment refresh after current surface health build failed for release {resolved_release_id!r}: {exc}"
                    ) from exc

                resolved_surface_alignment_json_output_path = surface_alignment_outputs.json_output_path
                resolved_surface_alignment_markdown_output_path = surface_alignment_outputs.markdown_output_path
                resolved_surface_alignment_console_output_path = surface_alignment_outputs.console_output_path
                surface_alignment_check_count = surface_alignment_result.checked_check_count
                surface_alignment_drift_check_count = surface_alignment_result.drift_check_count
                if not surface_alignment_result.is_clean:
                    raise SingleBaseDeliveryReleaseError(
                        f"surface alignment refresh after current surface health build failed for release {resolved_release_id!r}: drift_detected"
                    )

                try:
                    surface_health_result = build_single_base_delivery_surface_health(
                        project_root=PROJECT_ROOT,
                        surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                        surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                        surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                        output_json_path=resolved_surface_health_json_output_path,
                        output_markdown_path=resolved_surface_health_markdown_output_path,
                        output_console_path=resolved_surface_health_console_output_path,
                    )
                except SingleBaseDeliverySurfaceHealthError as exc:
                    raise SingleBaseDeliveryReleaseError(
                        f"current surface health refresh after visible-audit rebuild failed for release {resolved_release_id!r}: {exc}"
                    ) from exc

                resolved_surface_health_json_output_path = surface_health_result.output_json_path
                resolved_surface_health_markdown_output_path = surface_health_result.output_markdown_path
                resolved_surface_health_console_output_path = surface_health_result.output_console_path
                surface_health_check_count = surface_health_result.checked_check_count
                surface_health_drift_check_count = surface_health_result.drift_check_count
                surface_health_status = surface_health_result.status

                try:
                    entrypoints_result = build_single_base_delivery_entrypoints(
                        project_root=PROJECT_ROOT,
                        release_pointer_json_path=pointer_json_path,
                        viewer_pointer_json_path=resolved_viewer_pointer_json_path,
                        landing_manifest_json_path=landing_manifest_path,
                        frontdoor_manifest_json_path=frontdoor_manifest_path,
                        latest_bundle_pointer_json_path=(
                            resolved_frontdoor_output_dir / _LATEST_BUNDLE_POINTER_JSON_FILENAME
                            if resolved_frontdoor_output_dir is not None
                            else _DEFAULT_FRONTDOOR_OUTPUT_DIR / _LATEST_BUNDLE_POINTER_JSON_FILENAME
                        ),
                        surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                        surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                        surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                        require_surface_alignment=True,
                        surface_health_json_path=resolved_surface_health_json_output_path,
                        surface_health_markdown_path=resolved_surface_health_markdown_output_path,
                        surface_health_console_path=resolved_surface_health_console_output_path,
                        require_surface_health=True,
                        output_json_path=resolved_entrypoints_json_output_path,
                        output_markdown_path=resolved_entrypoints_markdown_output_path,
                    )
                except SingleBaseDeliveryEntrypointsError as exc:
                    raise SingleBaseDeliveryReleaseError(
                        f"active entrypoints closing refresh after current surface health build failed for release {resolved_release_id!r}: {exc}"
                    ) from exc

                resolved_entrypoints_json_output_path = entrypoints_result.output_json_path
                resolved_entrypoints_markdown_output_path = entrypoints_result.output_markdown_path
                entrypoints_action_count = entrypoints_result.action_count
                entrypoints_group_count = entrypoints_result.entrypoint_group_count

                try:
                    frontdoor_result = build_single_base_delivery_frontdoor(
                        project_root=PROJECT_ROOT,
                        landing_manifest_json_path=landing_manifest_path,
                        output_dir=(
                            resolved_frontdoor_output_dir
                            if resolved_frontdoor_output_dir is not None
                            else _DEFAULT_FRONTDOOR_OUTPUT_DIR
                        ),
                        entrypoints_json_path=resolved_entrypoints_json_output_path,
                        entrypoints_markdown_path=resolved_entrypoints_markdown_output_path,
                        require_entrypoints=True,
                        surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                        surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                        surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                        require_surface_alignment=True,
                        surface_health_json_path=resolved_surface_health_json_output_path,
                        surface_health_markdown_path=resolved_surface_health_markdown_output_path,
                        surface_health_console_path=resolved_surface_health_console_output_path,
                        require_surface_health=True,
                    )
                except SingleBaseDeliveryFrontdoorError as exc:
                    raise SingleBaseDeliveryReleaseError(
                        f"frontdoor closing refresh after current surface health build failed for release {resolved_release_id!r}: {exc}"
                    ) from exc

                frontdoor_manifest_path = frontdoor_result.frontdoor_manifest_path
                frontdoor_index_html_path = frontdoor_result.frontdoor_index_html_path
                frontdoor_quick_download_count = frontdoor_result.quick_download_count
                frontdoor_download_group_count = frontdoor_result.download_group_count

                final_surface_alignment_check_count = surface_alignment_check_count
                final_surface_alignment_drift_check_count = surface_alignment_drift_check_count

                try:
                    surface_alignment_result = build_single_base_delivery_surface_alignment_result(
                        project_root=PROJECT_ROOT,
                        frontdoor_manifest_json_path=frontdoor_manifest_path,
                        entrypoints_json_path=resolved_entrypoints_json_output_path,
                        entrypoints_markdown_path=resolved_entrypoints_markdown_output_path,
                        surface_alignment_json_path=resolved_surface_alignment_json_output_path,
                        surface_alignment_markdown_path=resolved_surface_alignment_markdown_output_path,
                        surface_alignment_console_path=resolved_surface_alignment_console_output_path,
                        current_surface_health_json_path=resolved_surface_health_json_output_path,
                        current_surface_health_markdown_path=resolved_surface_health_markdown_output_path,
                        current_surface_health_console_path=resolved_surface_health_console_output_path,
                        require_surface_alignment_visibility=True,
                        require_surface_health_visibility=True,
                    )
                    surface_alignment_outputs = write_single_base_delivery_surface_alignment_outputs(
                        surface_alignment_result,
                        json_output_path=resolved_surface_alignment_json_output_path,
                        markdown_output_path=resolved_surface_alignment_markdown_output_path,
                        console_output_path=resolved_surface_alignment_console_output_path,
                    )
                except (SingleBaseDeliverySurfaceAlignmentError, OSError, ValueError) as exc:
                    raise SingleBaseDeliveryReleaseError(
                        f"surface alignment closing audit after current surface health build failed for release {resolved_release_id!r}: {exc}"
                    ) from exc

                resolved_surface_alignment_json_output_path = surface_alignment_outputs.json_output_path
                resolved_surface_alignment_markdown_output_path = surface_alignment_outputs.markdown_output_path
                resolved_surface_alignment_console_output_path = surface_alignment_outputs.console_output_path
                surface_alignment_check_count = surface_alignment_result.checked_check_count
                surface_alignment_drift_check_count = surface_alignment_result.drift_check_count
                if not surface_alignment_result.is_clean:
                    raise SingleBaseDeliveryReleaseError(
                        f"surface alignment closing audit after current surface health build failed for release {resolved_release_id!r}: drift_detected"
                    )
                if (
                    previous_surface_alignment_check_count is not None
                    and previous_surface_alignment_drift_check_count is not None
                    and final_surface_alignment_check_count is not None
                    and final_surface_alignment_drift_check_count is not None
                    and (
                        surface_alignment_check_count != final_surface_alignment_check_count
                        or surface_alignment_drift_check_count != final_surface_alignment_drift_check_count
                    )
                ):
                    raise SingleBaseDeliveryReleaseError(
                        f"surface alignment closing audit after current surface health build failed for release {resolved_release_id!r}: audit metadata did not converge after the final current-surface-health refresh"
                    )
                surface_alignment_status = "clean"
                surface_health_status = surface_health_result.status

        result = SingleBaseDeliveryReleaseResult(
            release_id=resolved_release_id,
            base_id=base_id,
            source_run_dir=source_run_dir,
            release_dir=release_dir,
            release_manifest_json_path=release_manifest_json_path,
            release_manifest_markdown_path=release_manifest_markdown_path,
            sha256sums_path=sha256sums_path,
            pointer_json_path=pointer_json_path,
            pointer_markdown_path=pointer_markdown_path,
            index_json_path=resolved_index_json_path,
            index_markdown_path=resolved_index_markdown_path,
            delivery_status=str(summary.get("deliverable_status", "")),
            exact_full_scale_certified_status=str(
                ((summary.get("exact_full_scale_certified") or {}).get("status", ""))
                if isinstance(summary.get("exact_full_scale_certified"), Mapping)
                else ""
            ),
            payload_artifact_count=len(artifacts),
            required_payload_artifact_count=sum(1 for artifact in artifacts if artifact.required_for_delivery),
            viewer_bundle_status=viewer_bundle_status,
            viewer_output_dir=viewer_output_dir,
            viewer_manifest_path=viewer_manifest_path,
            viewer_pointer_json_path=resolved_viewer_pointer_json_path if build_viewer_bundle else None,
            viewer_pointer_markdown_path=(
                resolved_viewer_pointer_markdown_path if build_viewer_bundle else None
            ),
            viewer_index_json_path=resolved_viewer_index_json_path if build_viewer_bundle else None,
            viewer_index_markdown_path=resolved_viewer_index_markdown_path if build_viewer_bundle else None,
            viewer_selected_facility_type_count=viewer_selected_facility_type_count,
            viewer_selected_pose_count=viewer_selected_pose_count,
            viewer_payload_download_count=viewer_payload_download_count,
            viewer_metadata_download_count=viewer_metadata_download_count,
            viewer_quick_download_count=viewer_quick_download_count,
            landing_bundle_status=landing_bundle_status,
            landing_output_dir=resolved_landing_output_dir if resolved_build_landing_bundle else None,
            landing_manifest_path=landing_manifest_path,
            landing_index_html_path=landing_index_html_path,
            landing_quick_download_count=landing_quick_download_count,
            landing_download_group_count=landing_download_group_count,
            frontdoor_bundle_status=frontdoor_bundle_status,
            frontdoor_output_dir=resolved_frontdoor_output_dir if resolved_build_frontdoor else None,
            frontdoor_manifest_path=frontdoor_manifest_path,
            frontdoor_index_html_path=frontdoor_index_html_path,
            frontdoor_quick_download_count=frontdoor_quick_download_count,
            frontdoor_download_group_count=frontdoor_download_group_count,
            entrypoints_bundle_status=entrypoints_bundle_status,
            entrypoints_json_path=resolved_entrypoints_json_output_path if resolved_build_entrypoints else None,
            entrypoints_markdown_path=(
                resolved_entrypoints_markdown_output_path if resolved_build_entrypoints else None
            ),
            entrypoints_action_count=entrypoints_action_count,
            entrypoints_group_count=entrypoints_group_count,
            surface_alignment_status=surface_alignment_status,
            surface_alignment_json_path=(
                resolved_surface_alignment_json_output_path if resolved_audit_surface_alignment else None
            ),
            surface_alignment_markdown_path=(
                resolved_surface_alignment_markdown_output_path if resolved_audit_surface_alignment else None
            ),
            surface_alignment_console_path=(
                resolved_surface_alignment_console_output_path if resolved_audit_surface_alignment else None
            ),
            surface_alignment_check_count=surface_alignment_check_count,
            surface_alignment_drift_check_count=surface_alignment_drift_check_count,
            surface_health_status=surface_health_status,
            surface_health_json_path=(
                resolved_surface_health_json_output_path if resolved_build_surface_health else None
            ),
            surface_health_markdown_path=(
                resolved_surface_health_markdown_output_path if resolved_build_surface_health else None
            ),
            surface_health_console_path=(
                resolved_surface_health_console_output_path if resolved_build_surface_health else None
            ),
            surface_health_check_count=surface_health_check_count,
            surface_health_drift_check_count=surface_health_drift_check_count,
        )
        _discard_directory_backup(landing_output_dir_backup)
        return result
    except Exception as exc:
        if build_viewer_bundle:
            _remove_tree_if_exists(viewer_output_dir)
        if resolved_build_landing_bundle and resolved_landing_output_dir is not None:
            if landing_output_dir_backup is not None:
                _restore_directory_backup(path=resolved_landing_output_dir, backup_dir=landing_output_dir_backup)
                landing_output_dir_backup = None
            elif not landing_dir_existed_before:
                _remove_tree_if_exists(resolved_landing_output_dir)
        if release_dir_created and not overwrite:
            _remove_tree_if_exists(release_dir)
        for path, backup_text in file_backups.items():
            _restore_text_backup(path, backup_text)
        _discard_directory_backup(landing_output_dir_backup)
        if isinstance(exc, SingleBaseDeliveryReleaseError):
            raise
        raise SingleBaseDeliveryReleaseError(str(exc)) from exc



def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a versioned IndustrialPlanner single-base delivery release from a delivery-ready end-to-end run, "
            "refresh the active release pointer, and optionally materialize the checked-in current viewer bundle, "
            "viewer pointer, stable current landing/download page, repo-front entry page, and aggregate active-entrypoints "
            "manifest for the same active contract release."
        )
    )
    parser.add_argument(
        "--source-run-dir",
        default=str(_DEFAULT_SOURCE_RUN_DIR),
        help="Directory containing the source single-base e2e run summary and payload files.",
    )
    parser.add_argument(
        "--release-root",
        default=str(_DEFAULT_RELEASE_ROOT),
        help="Root directory where versioned release bundles should be written.",
    )
    parser.add_argument(
        "--release-id",
        default=None,
        help="Explicit release id. Defaults to a UTC timestamped id for the active single-base contract.",
    )
    parser.add_argument(
        "--pointer-json",
        default=str(_DEFAULT_POINTER_JSON_PATH),
        help="Machine-readable pointer that should track the current active single-base delivery release.",
    )
    parser.add_argument(
        "--pointer-markdown",
        default=str(_DEFAULT_POINTER_MARKDOWN_PATH),
        help="Human-readable pointer that should track the current active single-base delivery release.",
    )
    parser.add_argument(
        "--index-json",
        default=str(_DEFAULT_INDEX_JSON_PATH),
        help="Optional machine-readable release index path. Pass an empty string to skip writing it.",
    )
    parser.add_argument(
        "--index-markdown",
        default=str(_DEFAULT_INDEX_MARKDOWN_PATH),
        help="Optional human-readable release index path. Pass an empty string to skip writing it.",
    )
    parser.add_argument(
        "--viewer-root",
        default=str(_DEFAULT_VIEWER_ROOT),
        help=(
            "Root directory for versioned checked-in viewer bundles. Each promoted release writes one "
            "viewer bundle under <viewer-root>/<release-id>."
        ),
    )
    parser.add_argument(
        "--viewer-pointer-json",
        default=str(_DEFAULT_VIEWER_POINTER_JSON_PATH),
        help="Machine-readable pointer that should track the current active single-base delivery viewer bundle.",
    )
    parser.add_argument(
        "--viewer-pointer-markdown",
        default=str(_DEFAULT_VIEWER_POINTER_MARKDOWN_PATH),
        help="Human-readable pointer that should track the current active single-base delivery viewer bundle.",
    )
    parser.add_argument(
        "--viewer-index-json",
        default=str(_DEFAULT_VIEWER_INDEX_JSON_PATH),
        help="Optional machine-readable viewer index path. Pass an empty string to skip writing it.",
    )
    parser.add_argument(
        "--viewer-index-markdown",
        default=str(_DEFAULT_VIEWER_INDEX_MARKDOWN_PATH),
        help="Optional human-readable viewer index path. Pass an empty string to skip writing it.",
    )
    parser.add_argument(
        "--viewer-candidate-placements",
        default=str(_DEFAULT_VIEWER_CANDIDATE_PLACEMENTS_PATH),
        help="Candidate-placements JSON used when pruning the checked-in viewer bundle down to release-selected poses.",
    )
    parser.add_argument(
        "--viewer-rules-json",
        default=str(_DEFAULT_VIEWER_RULES_JSON_PATH),
        help="Rules JSON used when regenerating viewer-side report cards for the checked-in viewer bundle.",
    )
    parser.add_argument(
        "--viewer-html",
        default=str(_DEFAULT_VIEWER_HTML_PATH),
        help="Static viewer HTML template copied into the checked-in viewer bundle.",
    )
    parser.add_argument(
        "--landing-output-dir",
        default=str(_DEFAULT_LANDING_OUTPUT_DIR),
        help=(
            "Stable checked-in landing/download directory that should mirror the current-viewer pointer with a "
            "copied viewer bundle under current_delivery/viewer/."
        ),
    )
    parser.add_argument(
        "--frontdoor-output-dir",
        default=str(_DEFAULT_FRONTDOOR_OUTPUT_DIR),
        help=(
            "Repo-front directory that should receive the higher-level index.html/frontdoor_manifest.json "
            "entry point pointing forward to current_delivery/."
        ),
    )
    parser.add_argument(
        "--entrypoints-json",
        default="",
        help=(
            "Optional aggregate current-entrypoints JSON path. Defaults to <frontdoor-output-dir>/"
            f"{_ENTRYPOINTS_JSON_FILENAME} when repo-front refresh is enabled."
        ),
    )
    parser.add_argument(
        "--entrypoints-markdown",
        default="",
        help=(
            "Optional aggregate current-entrypoints Markdown path. Defaults to <frontdoor-output-dir>/"
            f"{_ENTRYPOINTS_MARKDOWN_FILENAME} when repo-front refresh is enabled."
        ),
    )
    parser.add_argument(
        "--surface-alignment-json",
        default=str(_DEFAULT_SURFACE_ALIGNMENT_JSON_PATH),
        help="Machine-readable output path for the repo-front/entrypoints no-drift audit summary.",
    )
    parser.add_argument(
        "--surface-alignment-markdown",
        default=str(_DEFAULT_SURFACE_ALIGNMENT_MARKDOWN_PATH),
        help="Human-readable output path for the repo-front/entrypoints no-drift audit summary.",
    )
    parser.add_argument(
        "--surface-alignment-console",
        default=str(_DEFAULT_SURFACE_ALIGNMENT_CONSOLE_PATH),
        help="Plain-text console output path for the repo-front/entrypoints no-drift audit summary.",
    )
    parser.add_argument(
        "--surface-health-json",
        default=str(_DEFAULT_SURFACE_HEALTH_JSON_PATH),
        help="Machine-readable compact current-surface health snapshot built from the converged surface-alignment audit.",
    )
    parser.add_argument(
        "--surface-health-markdown",
        default=str(_DEFAULT_SURFACE_HEALTH_MARKDOWN_PATH),
        help="Human-readable compact current-surface health snapshot built from the converged surface-alignment audit.",
    )
    parser.add_argument(
        "--surface-health-console",
        default=str(_DEFAULT_SURFACE_HEALTH_CONSOLE_PATH),
        help="Plain-text compact current-surface health snapshot built from the converged surface-alignment audit.",
    )
    parser.add_argument(
        "--base-id",
        default=DEFAULT_BASE_ID,
        help=(
            "Base id that the source run must target. Defaults to the active contract base "
            f"{DEFAULT_BASE_ID!r}."
        ),
    )
    parser.add_argument(
        "--refresh-run",
        action="store_true",
        help="Regenerate the source end-to-end run before packaging the release.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing release directory with the same release id.",
    )
    parser.add_argument(
        "--skip-viewer-bundle",
        action="store_true",
        help="Skip the checked-in viewer bundle/current-viewer-pointer refresh and build only the delivery release.",
    )
    parser.add_argument(
        "--skip-landing-bundle",
        action="store_true",
        help=(
            "Skip the stable current landing/download page refresh. This flag requires the viewer bundle refresh "
            "to remain enabled if you want the landing page to stay in sync with the promoted release."
        ),
    )
    parser.add_argument(
        "--skip-frontdoor",
        action="store_true",
        help=(
            "Skip the higher-level repo-front entry page refresh. This flag requires the stable landing refresh "
            "to remain enabled if you want the repo front door to stay in sync with the promoted release."
        ),
    )
    parser.add_argument(
        "--skip-entrypoints",
        action="store_true",
        help=(
            "Skip the aggregate current-entrypoints manifest refresh. This flag requires the repo-front refresh "
            "to remain enabled if you want the aggregated current-entrypoint summary to stay in sync with the promoted release."
        ),
    )
    parser.add_argument(
        "--skip-surface-alignment-audit",
        action="store_true",
        help=(
            "Skip the lightweight no-drift audit that cross-checks the checked-in repo-front helper links against "
            "the aggregate active-entrypoints manifest."
        ),
    )
    args = parser.parse_args()

    try:
        result = build_single_base_delivery_release(
            source_run_dir=Path(args.source_run_dir),
            release_root=Path(args.release_root),
            release_id=args.release_id,
            pointer_json_path=Path(args.pointer_json),
            pointer_markdown_path=Path(args.pointer_markdown),
            index_json_path=Path(args.index_json) if str(args.index_json).strip() else None,
            index_markdown_path=Path(args.index_markdown) if str(args.index_markdown).strip() else None,
            viewer_root=Path(args.viewer_root),
            viewer_pointer_json_path=Path(args.viewer_pointer_json),
            viewer_pointer_markdown_path=Path(args.viewer_pointer_markdown),
            viewer_index_json_path=(Path(args.viewer_index_json) if str(args.viewer_index_json).strip() else None),
            viewer_index_markdown_path=(
                Path(args.viewer_index_markdown) if str(args.viewer_index_markdown).strip() else None
            ),
            viewer_candidate_placements_path=Path(args.viewer_candidate_placements),
            viewer_rules_json_path=Path(args.viewer_rules_json),
            viewer_html_path=Path(args.viewer_html),
            landing_output_dir=(Path(args.landing_output_dir) if str(args.landing_output_dir).strip() else None),
            frontdoor_output_dir=(Path(args.frontdoor_output_dir) if str(args.frontdoor_output_dir).strip() else None),
            entrypoints_json_path=(Path(args.entrypoints_json) if str(args.entrypoints_json).strip() else None),
            entrypoints_markdown_path=(
                Path(args.entrypoints_markdown) if str(args.entrypoints_markdown).strip() else None
            ),
            surface_alignment_json_path=(
                Path(args.surface_alignment_json) if str(args.surface_alignment_json).strip() else None
            ),
            surface_alignment_markdown_path=(
                Path(args.surface_alignment_markdown) if str(args.surface_alignment_markdown).strip() else None
            ),
            surface_alignment_console_path=(
                Path(args.surface_alignment_console) if str(args.surface_alignment_console).strip() else None
            ),
            surface_health_json_path=(
                Path(args.surface_health_json) if str(args.surface_health_json).strip() else None
            ),
            surface_health_markdown_path=(
                Path(args.surface_health_markdown) if str(args.surface_health_markdown).strip() else None
            ),
            surface_health_console_path=(
                Path(args.surface_health_console) if str(args.surface_health_console).strip() else None
            ),
            base_id=str(args.base_id),
            refresh_run=bool(args.refresh_run),
            overwrite=bool(args.overwrite),
            build_viewer_bundle=not bool(args.skip_viewer_bundle),
            build_landing_bundle=not bool(args.skip_landing_bundle),
            build_frontdoor=not bool(args.skip_frontdoor),
            build_entrypoints=not bool(args.skip_entrypoints),
            audit_surface_alignment=not bool(args.skip_surface_alignment_audit),
        )
    except SingleBaseDeliveryReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(result.to_console_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
