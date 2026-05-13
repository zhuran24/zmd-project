"""No-drift audit for the checked-in IndustrialPlanner single-base consumer surface.

This audit is intentionally narrower than the broader release/viewer/landing/frontdoor
builders. It assumes those surfaces already exist and verifies that the checked-in
repo-front frontdoor and the aggregate active-entrypoints manifest still point at the
same current single-base consumer surface.

The main goal is to fail closed when human-facing helper links and script-facing
aggregate entrypoints drift apart after the initial build/promotion path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from src.io.serializer import load_json_mapping
from src.search.exact_campaign import atomic_write_json

_SURFACE_ALIGNMENT_SOURCE = "industrial_planner_single_base_delivery_surface_alignment_v3"
_SURFACE_ALIGNMENT_SCHEMA_VERSION = "1.2.0"

_DEFAULT_FRONTDOOR_MANIFEST_JSON = Path("data/examples/industrial_planner/frontdoor_manifest.json")
_DEFAULT_ENTRYPOINTS_JSON = Path("data/examples/industrial_planner/active_single_base_delivery_entrypoints.json")
_DEFAULT_ENTRYPOINTS_MARKDOWN = Path("data/examples/industrial_planner/active_single_base_delivery_entrypoints.md")
_DEFAULT_SURFACE_HEALTH_JSON = Path("data/examples/industrial_planner/current_surface_health.json")
_DEFAULT_SURFACE_HEALTH_MARKDOWN = Path("data/examples/industrial_planner/current_surface_health.md")
_DEFAULT_SURFACE_HEALTH_CONSOLE = Path("data/examples/industrial_planner/current_surface_health.txt")
_DEFAULT_OUTPUT_JSON = Path(
    ".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json"
)
_DEFAULT_OUTPUT_MARKDOWN = Path(
    ".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.md"
)
_DEFAULT_OUTPUT_CONSOLE = Path(
    ".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.txt"
)


class SingleBaseDeliverySurfaceAlignmentError(RuntimeError):
    """Raised when the checked-in single-base consumer surface cannot be audited safely."""


@dataclass(frozen=True)
class SingleBaseDeliverySurfaceAlignmentCheck:
    group_id: str
    check_id: str
    label: str
    expected: str
    actual: str
    is_clean: bool
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "check_id": self.check_id,
            "label": self.label,
            "expected": self.expected,
            "actual": self.actual,
            "status": "clean" if self.is_clean else "drift_detected",
            "is_clean": self.is_clean,
            "note": self.note,
        }


@dataclass(frozen=True)
class SingleBaseDeliverySurfaceAlignmentResult:
    project_root: Path
    frontdoor_manifest_json_path: Path
    frontdoor_index_html_path: Path
    entrypoints_json_path: Path
    entrypoints_markdown_path: Path
    surface_alignment_json_path: Path | None
    surface_alignment_markdown_path: Path | None
    surface_alignment_console_path: Path | None
    surface_health_json_path: Path | None
    surface_health_markdown_path: Path | None
    surface_health_console_path: Path | None
    release_id: str
    base_id: str
    lot_size: int
    delivery_status: str
    exact_full_scale_certified_status: str
    checks: tuple[SingleBaseDeliverySurfaceAlignmentCheck, ...]

    @property
    def checked_check_count(self) -> int:
        return len(self.checks)

    @property
    def clean_check_count(self) -> int:
        return sum(1 for check in self.checks if check.is_clean)

    @property
    def drift_check_count(self) -> int:
        return self.checked_check_count - self.clean_check_count

    @property
    def helper_link_count(self) -> int:
        return sum(1 for check in self.checks if check.group_id == "frontdoor_helper_links")

    @property
    def helper_link_clean_count(self) -> int:
        return sum(
            1
            for check in self.checks
            if check.group_id == "frontdoor_helper_links" and check.is_clean
        )

    @property
    def is_clean(self) -> bool:
        return self.drift_check_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": {
                "schema_version": _SURFACE_ALIGNMENT_SCHEMA_VERSION,
                "generated_at": _now_iso(),
                "source": _SURFACE_ALIGNMENT_SOURCE,
            },
            "summary": {
                "checked_check_count": self.checked_check_count,
                "clean_check_count": self.clean_check_count,
                "drift_check_count": self.drift_check_count,
                "helper_link_count": self.helper_link_count,
                "helper_link_clean_count": self.helper_link_clean_count,
                "is_clean": self.is_clean,
                "status": "clean" if self.is_clean else "drift_detected",
            },
            "active_contract": {
                "release_id": self.release_id,
                "base_id": self.base_id,
                "lot_size": self.lot_size,
                "delivery_status": self.delivery_status,
            },
            "exact_full_scale_certified": {
                "status": self.exact_full_scale_certified_status,
            },
            "checked_paths": {
                "frontdoor_manifest_json": _display_repo_path(self.project_root, self.frontdoor_manifest_json_path),
                "frontdoor_index_html": _display_repo_path(self.project_root, self.frontdoor_index_html_path),
                "entrypoints_json": _display_repo_path(self.project_root, self.entrypoints_json_path),
                "entrypoints_markdown": _display_repo_path(self.project_root, self.entrypoints_markdown_path),
                "surface_alignment_json": (
                    _display_repo_path(self.project_root, self.surface_alignment_json_path)
                    if self.surface_alignment_json_path is not None
                    else None
                ),
                "surface_alignment_markdown": (
                    _display_repo_path(self.project_root, self.surface_alignment_markdown_path)
                    if self.surface_alignment_markdown_path is not None
                    else None
                ),
                "surface_alignment_console": (
                    _display_repo_path(self.project_root, self.surface_alignment_console_path)
                    if self.surface_alignment_console_path is not None
                    else None
                ),
                "surface_health_json": (
                    _display_repo_path(self.project_root, self.surface_health_json_path)
                    if self.surface_health_json_path is not None
                    else None
                ),
                "surface_health_markdown": (
                    _display_repo_path(self.project_root, self.surface_health_markdown_path)
                    if self.surface_health_markdown_path is not None
                    else None
                ),
                "surface_health_console": (
                    _display_repo_path(self.project_root, self.surface_health_console_path)
                    if self.surface_health_console_path is not None
                    else None
                ),
            },
            "checks": [check.to_dict() for check in self.checks],
        }

    def to_markdown(self) -> str:
        lines = [
            "# IndustrialPlanner single-base delivery surface alignment audit",
            "",
            "This is a lightweight no-drift audit for the checked-in current consumer surface. It verifies that the repo-front single-base frontdoor and the aggregate active-entrypoints manifest still describe the same current single-base release/viewer/landing/latest-bundle surface, and that the human-facing helper links remain aligned with the script-facing entrypoint file.",
            "",
            f"- Frontdoor manifest: `{_display_repo_path(self.project_root, self.frontdoor_manifest_json_path)}`",
            f"- Frontdoor HTML: `{_display_repo_path(self.project_root, self.frontdoor_index_html_path)}`",
            f"- Entrypoints JSON: `{_display_repo_path(self.project_root, self.entrypoints_json_path)}`",
            f"- Entrypoints Markdown: `{_display_repo_path(self.project_root, self.entrypoints_markdown_path)}`",
            (
                f"- Surface-alignment JSON: `{_display_repo_path(self.project_root, self.surface_alignment_json_path)}`"
                if self.surface_alignment_json_path is not None
                else "- Surface-alignment JSON: `<not_checked>`"
            ),
            (
                f"- Surface-alignment Markdown: `{_display_repo_path(self.project_root, self.surface_alignment_markdown_path)}`"
                if self.surface_alignment_markdown_path is not None
                else "- Surface-alignment Markdown: `<not_checked>`"
            ),
            (
                f"- Surface-alignment console: `{_display_repo_path(self.project_root, self.surface_alignment_console_path)}`"
                if self.surface_alignment_console_path is not None
                else "- Surface-alignment console: `<not_checked>`"
            ),
            (
                f"- Surface-health JSON: `{_display_repo_path(self.project_root, self.surface_health_json_path)}`"
                if self.surface_health_json_path is not None
                else "- Surface-health JSON: `<not_checked>`"
            ),
            (
                f"- Surface-health Markdown: `{_display_repo_path(self.project_root, self.surface_health_markdown_path)}`"
                if self.surface_health_markdown_path is not None
                else "- Surface-health Markdown: `<not_checked>`"
            ),
            (
                f"- Surface-health console: `{_display_repo_path(self.project_root, self.surface_health_console_path)}`"
                if self.surface_health_console_path is not None
                else "- Surface-health console: `<not_checked>`"
            ),
            f"- Release id: `{self.release_id}`",
            f"- Base id: `{self.base_id}`",
            f"- Lot size: `{self.lot_size}`",
            f"- Delivery status: `{self.delivery_status}`",
            f"- Exact full-scale CERTIFIED status: `{self.exact_full_scale_certified_status}`",
            f"- Checks: {self.checked_check_count}",
            f"- Helper-link checks: {self.helper_link_count}",
            f"- Drift checks: {self.drift_check_count}",
            f"- Overall status: `{'clean' if self.is_clean else 'drift_detected'}`",
            "",
            "## Check summary",
            "",
            "| Group | Check | Status | Expected | Actual | Note |",
            "|---|---|---|---|---|---|",
        ]
        for check in self.checks:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{check.group_id}`",
                        f"`{check.check_id}`",
                        f"`{'clean' if check.is_clean else 'drift_detected'}`",
                        _md_escape_inline(check.expected),
                        _md_escape_inline(check.actual),
                        _md_escape_inline(check.note),
                    ]
                )
                + " |"
            )
        lines.append("")
        return "\n".join(lines)

    def to_console_text(self) -> str:
        lines = [
            "IndustrialPlanner single-base delivery surface alignment audit completed.",
            f"- release id: {self.release_id}",
            f"- base id: {self.base_id}",
            f"- delivery status: {self.delivery_status}",
            f"- exact full-scale CERTIFIED status: {self.exact_full_scale_certified_status}",
            f"- checks: {self.checked_check_count}",
            f"- helper-link checks: {self.helper_link_count}",
            f"- drift checks: {self.drift_check_count}",
            f"- overall status: {'clean' if self.is_clean else 'drift_detected'}",
        ]
        if not self.is_clean:
            lines.append("- drifted checks:")
            for check in self.checks:
                if not check.is_clean:
                    lines.append(
                        f"  - [{check.group_id}] {check.check_id}: expected {check.expected!r}, got {check.actual!r}"
                    )
        return "\n".join(lines)


def build_single_base_delivery_surface_alignment_result(
    *,
    project_root: Path,
    frontdoor_manifest_json_path: Path = _DEFAULT_FRONTDOOR_MANIFEST_JSON,
    entrypoints_json_path: Path = _DEFAULT_ENTRYPOINTS_JSON,
    entrypoints_markdown_path: Path = _DEFAULT_ENTRYPOINTS_MARKDOWN,
    surface_alignment_json_path: Path | None = _DEFAULT_OUTPUT_JSON,
    surface_alignment_markdown_path: Path | None = _DEFAULT_OUTPUT_MARKDOWN,
    surface_alignment_console_path: Path | None = _DEFAULT_OUTPUT_CONSOLE,
    current_surface_health_json_path: Path | None = _DEFAULT_SURFACE_HEALTH_JSON,
    current_surface_health_markdown_path: Path | None = _DEFAULT_SURFACE_HEALTH_MARKDOWN,
    current_surface_health_console_path: Path | None = _DEFAULT_SURFACE_HEALTH_CONSOLE,
    require_surface_alignment_visibility: bool = True,
    require_surface_health_visibility: bool = True,
) -> SingleBaseDeliverySurfaceAlignmentResult:
    project_root = Path(project_root).resolve()
    frontdoor_manifest_json_path = _resolve_repo_path(project_root, frontdoor_manifest_json_path)
    entrypoints_json_path = _resolve_repo_path(project_root, entrypoints_json_path)
    entrypoints_markdown_path = _resolve_repo_path(project_root, entrypoints_markdown_path)
    surface_alignment_json_path = _resolve_expected_repo_path(project_root, surface_alignment_json_path)
    surface_alignment_markdown_path = _resolve_expected_repo_path(project_root, surface_alignment_markdown_path)
    surface_alignment_console_path = _resolve_expected_repo_path(project_root, surface_alignment_console_path)
    current_surface_health_json_path = _resolve_expected_repo_path(project_root, current_surface_health_json_path)
    current_surface_health_markdown_path = _resolve_expected_repo_path(project_root, current_surface_health_markdown_path)
    current_surface_health_console_path = _resolve_expected_repo_path(project_root, current_surface_health_console_path)

    if require_surface_alignment_visibility:
        missing_surface_alignment_outputs = [
            label
            for label, path in (
                ("surface-alignment JSON", surface_alignment_json_path),
                ("surface-alignment Markdown", surface_alignment_markdown_path),
                ("surface-alignment console", surface_alignment_console_path),
            )
            if path is None or not path.is_file()
        ]
        if missing_surface_alignment_outputs:
            raise SingleBaseDeliverySurfaceAlignmentError(
                "surface-alignment visibility checks require checked-in outputs for: "
                + ", ".join(missing_surface_alignment_outputs)
            )
    if require_surface_health_visibility:
        missing_surface_health_outputs = [
            label
            for label, path in (
                ("surface-health JSON", current_surface_health_json_path),
                ("surface-health Markdown", current_surface_health_markdown_path),
                ("surface-health console", current_surface_health_console_path),
            )
            if path is None or not path.is_file()
        ]
        if missing_surface_health_outputs:
            raise SingleBaseDeliverySurfaceAlignmentError(
                "surface-health visibility checks require checked-in outputs for: "
                + ", ".join(missing_surface_health_outputs)
            )

    frontdoor_index_html_path = frontdoor_manifest_json_path.parent / "index.html"
    if not frontdoor_index_html_path.is_file():
        raise SingleBaseDeliverySurfaceAlignmentError(
            f"frontdoor index HTML is missing next to {frontdoor_manifest_json_path}: {frontdoor_index_html_path}"
        )

    frontdoor_payload = load_json_mapping(frontdoor_manifest_json_path)
    entrypoints_payload = load_json_mapping(entrypoints_json_path)
    surface_alignment_payload = (
        load_json_mapping(surface_alignment_json_path)
        if surface_alignment_json_path is not None and surface_alignment_json_path.is_file()
        else {}
    )
    surface_health_payload = (
        load_json_mapping(current_surface_health_json_path)
        if current_surface_health_json_path is not None and current_surface_health_json_path.is_file()
        else {}
    )

    current_frontdoor = _require_mapping(frontdoor_payload, "current_frontdoor", frontdoor_manifest_json_path)
    frontdoor_actions = _mapping(frontdoor_payload.get("actions"))
    script_entrypoints = _mapping(frontdoor_payload.get("script_entrypoints"))
    frontdoor_surface_alignment = _mapping(frontdoor_payload.get("surface_alignment"))
    frontdoor_surface_health = _mapping(frontdoor_payload.get("surface_health"))
    linked_assets = _mapping(frontdoor_payload.get("linked_assets"))
    frontdoor_exact = _require_mapping(
        frontdoor_payload, "exact_full_scale_certified", frontdoor_manifest_json_path
    )

    active_contract = _require_mapping(entrypoints_payload, "active_contract", entrypoints_json_path)
    entrypoints_actions = _mapping(entrypoints_payload.get("actions"))
    current_entrypoints = _mapping(entrypoints_payload.get("current_entrypoints"))
    entrypoints_surface_alignment = _mapping(entrypoints_payload.get("surface_alignment"))
    entrypoints_current_surface_alignment = _mapping(current_entrypoints.get("surface_alignment"))
    entrypoints_surface_health = _mapping(entrypoints_payload.get("surface_health"))
    entrypoints_current_surface_health = _mapping(current_entrypoints.get("surface_health"))
    repo_frontdoor = _require_mapping(entrypoints_payload, "repo_frontdoor", entrypoints_json_path)
    entrypoints_exact = _require_mapping(entrypoints_payload, "exact_full_scale_certified", entrypoints_json_path)
    surface_summary = _mapping(entrypoints_payload.get("surface_summary"))

    summary_payload = _require_mapping(surface_alignment_payload, "summary", surface_alignment_json_path) if surface_alignment_payload else {}
    summary_active_contract = (
        _require_mapping(surface_alignment_payload, "active_contract", surface_alignment_json_path)
        if surface_alignment_payload
        else {}
    )
    summary_exact = (
        _require_mapping(surface_alignment_payload, "exact_full_scale_certified", surface_alignment_json_path)
        if surface_alignment_payload
        else {}
    )
    checked_paths = _mapping(surface_alignment_payload.get("checked_paths")) if surface_alignment_payload else {}
    health_summary_payload = (
        _require_mapping(surface_health_payload, "surface_health", current_surface_health_json_path)
        if surface_health_payload
        else {}
    )
    health_active_contract = (
        _require_mapping(surface_health_payload, "active_contract", current_surface_health_json_path)
        if surface_health_payload
        else {}
    )
    health_exact = (
        _require_mapping(surface_health_payload, "exact_full_scale_certified", current_surface_health_json_path)
        if surface_health_payload
        else {}
    )
    health_source_summaries = _mapping(surface_health_payload.get("source_summaries")) if surface_health_payload else {}
    health_checked_surfaces = _mapping(surface_health_payload.get("checked_consumer_surfaces")) if surface_health_payload else {}

    release_id = _require_string(active_contract, "release_id", context="active_contract")
    base_id = _require_string(active_contract, "base_id", context="active_contract")
    lot_size = _require_int(active_contract, "lot_size", context="active_contract")
    delivery_status = _require_string(active_contract, "delivery_status", context="active_contract")
    exact_status = _require_string(entrypoints_exact, "status", context="exact_full_scale_certified")

    frontdoor_dir = frontdoor_manifest_json_path.parent.resolve()
    entrypoints_json_relative = _relative_from(frontdoor_dir, entrypoints_json_path)
    entrypoints_markdown_relative = _relative_from(frontdoor_dir, entrypoints_markdown_path)
    frontdoor_manifest_relative = _relative_from(frontdoor_dir, frontdoor_manifest_json_path)
    frontdoor_index_repo = _display_repo_path(project_root, frontdoor_index_html_path)
    frontdoor_manifest_repo = _display_repo_path(project_root, frontdoor_manifest_json_path)
    entrypoints_json_repo = _display_repo_path(project_root, entrypoints_json_path)
    entrypoints_markdown_repo = _display_repo_path(project_root, entrypoints_markdown_path)
    surface_alignment_json_relative = (
        _relative_from(frontdoor_dir, surface_alignment_json_path)
        if surface_alignment_json_path is not None
        else "<not_checked>"
    )
    surface_alignment_markdown_relative = (
        _relative_from(frontdoor_dir, surface_alignment_markdown_path)
        if surface_alignment_markdown_path is not None
        else "<not_checked>"
    )
    surface_alignment_console_relative = (
        _relative_from(frontdoor_dir, surface_alignment_console_path)
        if surface_alignment_console_path is not None
        else "<not_checked>"
    )
    surface_alignment_json_repo = (
        _display_repo_path(project_root, surface_alignment_json_path)
        if surface_alignment_json_path is not None
        else "<not_checked>"
    )
    surface_alignment_markdown_repo = (
        _display_repo_path(project_root, surface_alignment_markdown_path)
        if surface_alignment_markdown_path is not None
        else "<not_checked>"
    )
    surface_alignment_console_repo = (
        _display_repo_path(project_root, surface_alignment_console_path)
        if surface_alignment_console_path is not None
        else "<not_checked>"
    )
    surface_health_json_relative = (
        _relative_from(frontdoor_dir, current_surface_health_json_path)
        if current_surface_health_json_path is not None
        else "<not_checked>"
    )
    surface_health_markdown_relative = (
        _relative_from(frontdoor_dir, current_surface_health_markdown_path)
        if current_surface_health_markdown_path is not None
        else "<not_checked>"
    )
    surface_health_console_relative = (
        _relative_from(frontdoor_dir, current_surface_health_console_path)
        if current_surface_health_console_path is not None
        else "<not_checked>"
    )
    surface_health_json_repo = (
        _display_repo_path(project_root, current_surface_health_json_path)
        if current_surface_health_json_path is not None
        else "<not_checked>"
    )
    surface_health_markdown_repo = (
        _display_repo_path(project_root, current_surface_health_markdown_path)
        if current_surface_health_markdown_path is not None
        else "<not_checked>"
    )
    surface_health_console_repo = (
        _display_repo_path(project_root, current_surface_health_console_path)
        if current_surface_health_console_path is not None
        else "<not_checked>"
    )

    helper_links = _extract_helper_links(frontdoor_index_html_path)
    helper_href_set = {link["href"] for link in helper_links}
    helper_label_set = {link["label"] for link in helper_links if link["label"]}
    frontdoor_html_text = frontdoor_index_html_path.read_text(encoding="utf-8")

    checks: list[SingleBaseDeliverySurfaceAlignmentCheck] = []

    checks.extend(
        [
            _equality_check(
                group_id="contract",
                check_id="release_id",
                label="frontdoor release id matches active entrypoints release id",
                expected=release_id,
                actual=str(current_frontdoor.get("release_id", "")).strip(),
            ),
            _equality_check(
                group_id="contract",
                check_id="base_id",
                label="frontdoor base id matches active entrypoints base id",
                expected=base_id,
                actual=str(current_frontdoor.get("base_id", "")).strip(),
            ),
            _equality_check(
                group_id="contract",
                check_id="lot_size",
                label="frontdoor lot size matches active entrypoints lot size",
                expected=str(lot_size),
                actual=str(current_frontdoor.get("lot_size", "")).strip(),
            ),
            _equality_check(
                group_id="contract",
                check_id="delivery_status",
                label="frontdoor delivery status matches active entrypoints delivery status",
                expected=delivery_status,
                actual=str(current_frontdoor.get("delivery_status", "")).strip(),
            ),
            _equality_check(
                group_id="exact_status",
                check_id="exact_full_scale_certified_status",
                label="frontdoor exact status matches active entrypoints exact status",
                expected=exact_status,
                actual=str(frontdoor_exact.get("status", "")).strip(),
            ),
        ]
    )

    if require_surface_alignment_visibility:
        checks.extend(
            [
                _equality_check(
                    group_id="surface_alignment_contract",
                    check_id="surface_alignment_release_id",
                    label="surface-alignment summary release id matches the active contract",
                    expected=release_id,
                    actual=str(summary_active_contract.get("release_id", "")).strip(),
                ),
                _equality_check(
                    group_id="surface_alignment_contract",
                    check_id="surface_alignment_base_id",
                    label="surface-alignment summary base id matches the active contract",
                    expected=base_id,
                    actual=str(summary_active_contract.get("base_id", "")).strip(),
                ),
                _equality_check(
                    group_id="surface_alignment_contract",
                    check_id="surface_alignment_lot_size",
                    label="surface-alignment summary lot size matches the active contract",
                    expected=str(lot_size),
                    actual=str(summary_active_contract.get("lot_size", "")).strip(),
                ),
                _equality_check(
                    group_id="surface_alignment_contract",
                    check_id="surface_alignment_delivery_status",
                    label="surface-alignment summary delivery status matches the active contract",
                    expected=delivery_status,
                    actual=str(summary_active_contract.get("delivery_status", "")).strip(),
                ),
                _equality_check(
                    group_id="surface_alignment_contract",
                    check_id="surface_alignment_exact_status",
                    label="surface-alignment summary exact status matches the active contract exact status",
                    expected=exact_status,
                    actual=str(summary_exact.get("status", "")).strip(),
                ),
            ]
        )

    checks.extend(
        [
            _equality_check(
                group_id="frontdoor_entrypoints_refs",
                check_id="current_frontdoor_active_entrypoints_json",
                label="current_frontdoor active_entrypoints_json points at the checked-in aggregate JSON",
                expected=entrypoints_json_relative,
                actual=str(current_frontdoor.get("active_entrypoints_json", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_entrypoints_refs",
                check_id="current_frontdoor_active_entrypoints_markdown",
                label="current_frontdoor active_entrypoints_markdown points at the checked-in aggregate Markdown",
                expected=entrypoints_markdown_relative,
                actual=str(current_frontdoor.get("active_entrypoints_markdown", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_entrypoints_refs",
                check_id="actions_active_entrypoints_json",
                label="frontdoor actions.active_entrypoints_json points at the checked-in aggregate JSON",
                expected=entrypoints_json_relative,
                actual=str(frontdoor_actions.get("active_entrypoints_json", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_entrypoints_refs",
                check_id="actions_active_entrypoints_markdown",
                label="frontdoor actions.active_entrypoints_markdown points at the checked-in aggregate Markdown",
                expected=entrypoints_markdown_relative,
                actual=str(frontdoor_actions.get("active_entrypoints_markdown", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_entrypoints_refs",
                check_id="script_entrypoints_json",
                label="frontdoor script_entrypoints.json points at the checked-in aggregate JSON",
                expected=entrypoints_json_relative,
                actual=str(script_entrypoints.get("json", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_entrypoints_refs",
                check_id="script_entrypoints_markdown",
                label="frontdoor script_entrypoints.markdown points at the checked-in aggregate Markdown",
                expected=entrypoints_markdown_relative,
                actual=str(script_entrypoints.get("markdown", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_entrypoints_refs",
                check_id="script_entrypoints_json_repo_path",
                label="frontdoor script_entrypoints.json_repo_path matches the checked-in aggregate JSON repo path",
                expected=entrypoints_json_repo,
                actual=str(script_entrypoints.get("json_repo_path", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_entrypoints_refs",
                check_id="script_entrypoints_markdown_repo_path",
                label="frontdoor script_entrypoints.markdown_repo_path matches the checked-in aggregate Markdown repo path",
                expected=entrypoints_markdown_repo,
                actual=str(script_entrypoints.get("markdown_repo_path", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_entrypoints_refs",
                check_id="linked_assets_active_entrypoints_json",
                label="frontdoor linked_assets.active_entrypoints_json points at the checked-in aggregate JSON",
                expected=entrypoints_json_relative,
                actual=str(linked_assets.get("active_entrypoints_json", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_entrypoints_refs",
                check_id="linked_assets_active_entrypoints_markdown",
                label="frontdoor linked_assets.active_entrypoints_markdown points at the checked-in aggregate Markdown",
                expected=entrypoints_markdown_relative,
                actual=str(linked_assets.get("active_entrypoints_markdown", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_entrypoints_refs",
                check_id="recommended_for_automation",
                label="frontdoor still marks the aggregate manifest as the recommended automation entry",
                expected="True",
                actual=str(bool(script_entrypoints.get("recommended_for_automation"))),
            ),
        ]
    )

    if require_surface_alignment_visibility:
        checks.extend(
            [
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="current_frontdoor_surface_alignment_summary_json",
                    label="current_frontdoor surface_alignment_summary_json points at the checked-in surface-alignment JSON",
                    expected=surface_alignment_json_relative,
                    actual=str(current_frontdoor.get("surface_alignment_summary_json", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="current_frontdoor_surface_alignment_summary_markdown",
                    label="current_frontdoor surface_alignment_summary_markdown points at the checked-in surface-alignment Markdown",
                    expected=surface_alignment_markdown_relative,
                    actual=str(current_frontdoor.get("surface_alignment_summary_markdown", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="current_frontdoor_surface_alignment_summary_console",
                    label="current_frontdoor surface_alignment_summary_console points at the checked-in surface-alignment console summary",
                    expected=surface_alignment_console_relative,
                    actual=str(current_frontdoor.get("surface_alignment_summary_console", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="actions_surface_alignment_summary_json",
                    label="frontdoor actions.surface_alignment_summary_json points at the checked-in surface-alignment JSON",
                    expected=surface_alignment_json_relative,
                    actual=str(frontdoor_actions.get("surface_alignment_summary_json", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="actions_surface_alignment_summary_markdown",
                    label="frontdoor actions.surface_alignment_summary_markdown points at the checked-in surface-alignment Markdown",
                    expected=surface_alignment_markdown_relative,
                    actual=str(frontdoor_actions.get("surface_alignment_summary_markdown", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="actions_surface_alignment_summary_console",
                    label="frontdoor actions.surface_alignment_summary_console points at the checked-in surface-alignment console summary",
                    expected=surface_alignment_console_relative,
                    actual=str(frontdoor_actions.get("surface_alignment_summary_console", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="surface_alignment_json",
                    label="frontdoor surface_alignment.json points at the checked-in surface-alignment JSON",
                    expected=surface_alignment_json_relative,
                    actual=str(frontdoor_surface_alignment.get("json", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="surface_alignment_markdown",
                    label="frontdoor surface_alignment.markdown points at the checked-in surface-alignment Markdown",
                    expected=surface_alignment_markdown_relative,
                    actual=str(frontdoor_surface_alignment.get("markdown", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="surface_alignment_console",
                    label="frontdoor surface_alignment.console points at the checked-in surface-alignment console summary",
                    expected=surface_alignment_console_relative,
                    actual=str(frontdoor_surface_alignment.get("console", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="surface_alignment_json_repo_path",
                    label="frontdoor surface_alignment.json_repo_path matches the checked-in surface-alignment JSON repo path",
                    expected=surface_alignment_json_repo,
                    actual=str(frontdoor_surface_alignment.get("json_repo_path", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="surface_alignment_markdown_repo_path",
                    label="frontdoor surface_alignment.markdown_repo_path matches the checked-in surface-alignment Markdown repo path",
                    expected=surface_alignment_markdown_repo,
                    actual=str(frontdoor_surface_alignment.get("markdown_repo_path", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="surface_alignment_console_repo_path",
                    label="frontdoor surface_alignment.console_repo_path matches the checked-in surface-alignment console repo path",
                    expected=surface_alignment_console_repo,
                    actual=str(frontdoor_surface_alignment.get("console_repo_path", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="linked_assets_surface_alignment_summary_json",
                    label="frontdoor linked_assets.surface_alignment_summary_json points at the checked-in surface-alignment JSON",
                    expected=surface_alignment_json_relative,
                    actual=str(linked_assets.get("surface_alignment_summary_json", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="linked_assets_surface_alignment_summary_markdown",
                    label="frontdoor linked_assets.surface_alignment_summary_markdown points at the checked-in surface-alignment Markdown",
                    expected=surface_alignment_markdown_relative,
                    actual=str(linked_assets.get("surface_alignment_summary_markdown", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_alignment_refs",
                    check_id="linked_assets_surface_alignment_summary_console",
                    label="frontdoor linked_assets.surface_alignment_summary_console points at the checked-in surface-alignment console summary",
                    expected=surface_alignment_console_relative,
                    actual=str(linked_assets.get("surface_alignment_summary_console", "")).strip(),
                ),
            ]
        )

    checks.extend(
        [
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_active_entrypoints_json_href",
                label="frontdoor helper links still include Active entrypoints JSON",
                expected=entrypoints_json_relative,
                present=entrypoints_json_relative in helper_href_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_active_entrypoints_markdown_href",
                label="frontdoor helper links still include Active entrypoints Markdown",
                expected=entrypoints_markdown_relative,
                present=entrypoints_markdown_relative in helper_href_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_frontdoor_manifest_href",
                label="frontdoor helper links still include the frontdoor manifest JSON",
                expected=frontdoor_manifest_relative,
                present=frontdoor_manifest_relative in helper_href_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_latest_bundle_pointer_json_href",
                label="frontdoor helper links still include the latest-bundle pointer JSON",
                expected=str(current_frontdoor.get("latest_bundle_pointer_json", "")).strip(),
                present=str(current_frontdoor.get("latest_bundle_pointer_json", "")).strip() in helper_href_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_current_delivery_manifest_href",
                label="frontdoor helper links still include the current-delivery landing manifest",
                expected=str(current_frontdoor.get("current_delivery_landing_manifest_json", "")).strip(),
                present=str(current_frontdoor.get("current_delivery_landing_manifest_json", "")).strip() in helper_href_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_viewer_manifest_href",
                label="frontdoor helper links still include the viewer manifest JSON",
                expected=str(current_frontdoor.get("viewer_manifest_json", "")).strip(),
                present=str(current_frontdoor.get("viewer_manifest_json", "")).strip() in helper_href_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_label_active_entrypoints_json",
                label="frontdoor helper-link label still advertises Active entrypoints JSON",
                expected="Active entrypoints JSON",
                present="Active entrypoints JSON" in helper_label_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_label_active_entrypoints_markdown",
                label="frontdoor helper-link label still advertises Active entrypoints Markdown",
                expected="Active entrypoints Markdown",
                present="Active entrypoints Markdown" in helper_label_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="automation_tip_mentions_entrypoints_json",
                label="frontdoor automation tip still points readers at the aggregate JSON",
                expected=f"<code>{entrypoints_json_relative}</code>",
                present=f"<code>{entrypoints_json_relative}</code>" in frontdoor_html_text,
            ),
        ]
    )

    if require_surface_alignment_visibility:
        checks.extend(
            [
                _presence_check(
                    group_id="frontdoor_helper_links",
                    check_id="helper_surface_alignment_json_href",
                    label="frontdoor helper links still include the surface-alignment JSON summary",
                    expected=surface_alignment_json_relative,
                    present=surface_alignment_json_relative in helper_href_set,
                ),
                _presence_check(
                    group_id="frontdoor_helper_links",
                    check_id="helper_surface_alignment_markdown_href",
                    label="frontdoor helper links still include the surface-alignment Markdown summary",
                    expected=surface_alignment_markdown_relative,
                    present=surface_alignment_markdown_relative in helper_href_set,
                ),
                _presence_check(
                    group_id="frontdoor_helper_links",
                    check_id="helper_surface_alignment_console_href",
                    label="frontdoor helper links still include the surface-alignment console summary",
                    expected=surface_alignment_console_relative,
                    present=surface_alignment_console_relative in helper_href_set,
                ),
                _presence_check(
                    group_id="frontdoor_helper_links",
                    check_id="helper_label_surface_alignment_json",
                    label="frontdoor helper-link label still advertises Surface alignment JSON",
                    expected="Surface alignment JSON",
                    present="Surface alignment JSON" in helper_label_set,
                ),
                _presence_check(
                    group_id="frontdoor_helper_links",
                    check_id="helper_label_surface_alignment_markdown",
                    label="frontdoor helper-link label still advertises Surface alignment Markdown",
                    expected="Surface alignment Markdown",
                    present="Surface alignment Markdown" in helper_label_set,
                ),
                _presence_check(
                    group_id="frontdoor_helper_links",
                    check_id="helper_label_surface_alignment_console",
                    label="frontdoor helper-link label still advertises Surface alignment console",
                    expected="Surface alignment console",
                    present="Surface alignment console" in helper_label_set,
                ),
            ]
        )

        if summary_payload:
            surface_alignment_summary_text = (
                f"{summary_payload.get('checked_check_count', 0)} checks / {summary_payload.get('drift_check_count', 0)} drift"
            )
            checks.extend(
                [
                    _presence_check(
                        group_id="frontdoor_surface_alignment_html",
                        check_id="surface_alignment_panel_heading",
                        label="frontdoor HTML still renders the current consumer-surface audit panel heading",
                        expected="Current consumer-surface audit",
                        present="Current consumer-surface audit" in frontdoor_html_text,
                    ),
                    _presence_check(
                        group_id="frontdoor_surface_alignment_html",
                        check_id="surface_alignment_status_text",
                        label="frontdoor HTML still renders the surface-alignment status text",
                        expected=str(summary_payload.get("status", "")).strip(),
                        present=str(summary_payload.get("status", "")).strip() in frontdoor_html_text,
                    ),
                    _presence_check(
                        group_id="frontdoor_surface_alignment_html",
                        check_id="surface_alignment_summary_text",
                        label="frontdoor HTML still renders the surface-alignment summary counts",
                        expected=surface_alignment_summary_text,
                        present=surface_alignment_summary_text in frontdoor_html_text,
                    ),
                ]
            )

    current_delivery_manifest_repo, current_delivery_manifest_exists = _repo_path_from_frontdoor_relative(
        project_root, frontdoor_dir, str(current_frontdoor.get("current_delivery_landing_manifest_json", "")).strip()
    )
    current_bundle_zip_repo, current_bundle_zip_exists = _repo_path_from_frontdoor_relative(
        project_root, frontdoor_dir, str(current_frontdoor.get("current_bundle_zip", "")).strip()
    )
    latest_bundle_zip_repo, latest_bundle_zip_exists = _repo_path_from_frontdoor_relative(
        project_root, frontdoor_dir, str(current_frontdoor.get("latest_bundle_zip", "")).strip()
    )
    latest_bundle_pointer_json_repo, latest_bundle_pointer_json_exists = _repo_path_from_frontdoor_relative(
        project_root, frontdoor_dir, str(current_frontdoor.get("latest_bundle_pointer_json", "")).strip()
    )
    viewer_manifest_repo, viewer_manifest_exists = _repo_path_from_frontdoor_relative(
        project_root, frontdoor_dir, str(current_frontdoor.get("viewer_manifest_json", "")).strip()
    )
    browse_primary_repo, browse_primary_exists = _repo_path_from_frontdoor_relative(
        project_root, frontdoor_dir, str(frontdoor_actions.get("open_viewer", "")).strip()
    )
    download_primary_repo, download_primary_exists = _repo_path_from_frontdoor_relative(
        project_root, frontdoor_dir, str(frontdoor_actions.get("download_latest_bundle_zip", "")).strip()
    )
    open_current_delivery_repo, open_current_delivery_exists = _repo_path_from_frontdoor_relative(
        project_root, frontdoor_dir, str(frontdoor_actions.get("open_current_delivery", "")).strip()
    )

    checks.extend(
        [
            _equality_check(
                group_id="entrypoints_actions",
                check_id="frontdoor_index_html",
                label="entrypoints.actions.frontdoor_index_html still points at the checked-in frontdoor HTML",
                expected=frontdoor_index_repo,
                actual=str(entrypoints_actions.get("frontdoor_index_html", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_actions",
                check_id="frontdoor_manifest_json",
                label="entrypoints.actions.frontdoor_manifest_json still points at the checked-in frontdoor manifest",
                expected=frontdoor_manifest_repo,
                actual=str(entrypoints_actions.get("frontdoor_manifest_json", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_actions",
                check_id="active_entrypoints_json",
                label="entrypoints.actions.active_entrypoints_json still points at this aggregate JSON",
                expected=entrypoints_json_repo,
                actual=str(entrypoints_actions.get("active_entrypoints_json", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_actions",
                check_id="active_entrypoints_markdown",
                label="entrypoints.actions.active_entrypoints_markdown still points at this aggregate Markdown",
                expected=entrypoints_markdown_repo,
                actual=str(entrypoints_actions.get("active_entrypoints_markdown", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_actions",
                check_id="open_current_delivery",
                label="entrypoints.actions.open_current_delivery still matches the repo-front current-delivery link",
                expected=open_current_delivery_repo,
                actual=str(entrypoints_actions.get("open_current_delivery", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_actions",
                check_id="download_latest_bundle_zip",
                label="entrypoints.actions.download_latest_bundle_zip still matches the repo-front download-first ZIP alias",
                expected=download_primary_repo,
                actual=str(entrypoints_actions.get("download_latest_bundle_zip", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_actions",
                check_id="latest_bundle_pointer_json",
                label="entrypoints.actions.latest_bundle_pointer_json still matches the repo-front latest-bundle pointer JSON",
                expected=latest_bundle_pointer_json_repo,
                actual=str(entrypoints_actions.get("latest_bundle_pointer_json", "")).strip(),
            ),
        ]
    )

    if require_surface_alignment_visibility:
        checks.extend(
            [
                _equality_check(
                    group_id="entrypoints_surface_alignment_refs",
                    check_id="actions_surface_alignment_summary_json",
                    label="entrypoints.actions.surface_alignment_summary_json still points at the checked-in surface-alignment JSON",
                    expected=surface_alignment_json_repo,
                    actual=str(entrypoints_actions.get("surface_alignment_summary_json", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_alignment_refs",
                    check_id="actions_surface_alignment_summary_markdown",
                    label="entrypoints.actions.surface_alignment_summary_markdown still points at the checked-in surface-alignment Markdown",
                    expected=surface_alignment_markdown_repo,
                    actual=str(entrypoints_actions.get("surface_alignment_summary_markdown", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_alignment_refs",
                    check_id="actions_surface_alignment_summary_console",
                    label="entrypoints.actions.surface_alignment_summary_console still points at the checked-in surface-alignment console summary",
                    expected=surface_alignment_console_repo,
                    actual=str(entrypoints_actions.get("surface_alignment_summary_console", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_alignment_refs",
                    check_id="surface_alignment_json",
                    label="entrypoints.surface_alignment.json still points at the checked-in surface-alignment JSON",
                    expected=surface_alignment_json_repo,
                    actual=str(entrypoints_surface_alignment.get("json", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_alignment_refs",
                    check_id="surface_alignment_markdown",
                    label="entrypoints.surface_alignment.markdown still points at the checked-in surface-alignment Markdown",
                    expected=surface_alignment_markdown_repo,
                    actual=str(entrypoints_surface_alignment.get("markdown", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_alignment_refs",
                    check_id="surface_alignment_console",
                    label="entrypoints.surface_alignment.console still points at the checked-in surface-alignment console summary",
                    expected=surface_alignment_console_repo,
                    actual=str(entrypoints_surface_alignment.get("console", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_alignment_refs",
                    check_id="current_entrypoints_surface_alignment_json",
                    label="entrypoints.current_entrypoints.surface_alignment.json still points at the checked-in surface-alignment JSON",
                    expected=surface_alignment_json_repo,
                    actual=str(entrypoints_current_surface_alignment.get("json", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_alignment_refs",
                    check_id="current_entrypoints_surface_alignment_markdown",
                    label="entrypoints.current_entrypoints.surface_alignment.markdown still points at the checked-in surface-alignment Markdown",
                    expected=surface_alignment_markdown_repo,
                    actual=str(entrypoints_current_surface_alignment.get("markdown", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_alignment_refs",
                    check_id="current_entrypoints_surface_alignment_console",
                    label="entrypoints.current_entrypoints.surface_alignment.console still points at the checked-in surface-alignment console summary",
                    expected=surface_alignment_console_repo,
                    actual=str(entrypoints_current_surface_alignment.get("console", "")).strip(),
                ),
            ]
        )

        checks.extend(
            [
                _presence_check(
                    group_id="linked_target_presence",
                    check_id="surface_alignment_json_exists",
                    label="checked-in surface-alignment JSON summary still exists",
                    expected=surface_alignment_json_repo,
                    present=surface_alignment_json_path is not None and surface_alignment_json_path.is_file(),
                ),
                _presence_check(
                    group_id="linked_target_presence",
                    check_id="surface_alignment_markdown_exists",
                    label="checked-in surface-alignment Markdown summary still exists",
                    expected=surface_alignment_markdown_repo,
                    present=surface_alignment_markdown_path is not None and surface_alignment_markdown_path.is_file(),
                ),
                _presence_check(
                    group_id="linked_target_presence",
                    check_id="surface_alignment_console_exists",
                    label="checked-in surface-alignment console summary still exists",
                    expected=surface_alignment_console_repo,
                    present=surface_alignment_console_path is not None and surface_alignment_console_path.is_file(),
                ),
            ]
        )

        if summary_payload:
            summary_status = str(summary_payload.get("status", "")).strip()
            summary_checked_count = str(summary_payload.get("checked_check_count", "")).strip()
            summary_clean_count = str(summary_payload.get("clean_check_count", "")).strip()
            summary_drift_count = str(summary_payload.get("drift_check_count", "")).strip()
            summary_helper_count = str(summary_payload.get("helper_link_count", "")).strip()
            summary_helper_clean_count = str(summary_payload.get("helper_link_clean_count", "")).strip()
            checks.extend(
                [
                    _equality_check(
                        group_id="frontdoor_surface_alignment_metadata",
                        check_id="current_frontdoor_surface_alignment_status",
                        label="current_frontdoor surface_alignment_status matches the checked-in surface-alignment summary",
                        expected=summary_status,
                        actual=str(current_frontdoor.get("surface_alignment_status", "")).strip(),
                    ),
                    _equality_check(
                        group_id="frontdoor_surface_alignment_metadata",
                        check_id="current_frontdoor_surface_alignment_check_count",
                        label="current_frontdoor surface_alignment_check_count matches the checked-in surface-alignment summary",
                        expected=summary_checked_count,
                        actual=str(current_frontdoor.get("surface_alignment_check_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="frontdoor_surface_alignment_metadata",
                        check_id="current_frontdoor_surface_alignment_drift_check_count",
                        label="current_frontdoor surface_alignment_drift_check_count matches the checked-in surface-alignment summary",
                        expected=summary_drift_count,
                        actual=str(current_frontdoor.get("surface_alignment_drift_check_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="frontdoor_surface_alignment_metadata",
                        check_id="surface_alignment_status",
                        label="frontdoor surface_alignment.status matches the checked-in surface-alignment summary",
                        expected=summary_status,
                        actual=str(frontdoor_surface_alignment.get("status", "")).strip(),
                    ),
                    _equality_check(
                        group_id="frontdoor_surface_alignment_metadata",
                        check_id="surface_alignment_checked_check_count",
                        label="frontdoor surface_alignment.checked_check_count matches the checked-in surface-alignment summary",
                        expected=summary_checked_count,
                        actual=str(frontdoor_surface_alignment.get("checked_check_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="frontdoor_surface_alignment_metadata",
                        check_id="surface_alignment_clean_check_count",
                        label="frontdoor surface_alignment.clean_check_count matches the checked-in surface-alignment summary",
                        expected=summary_clean_count,
                        actual=str(frontdoor_surface_alignment.get("clean_check_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="frontdoor_surface_alignment_metadata",
                        check_id="surface_alignment_drift_check_count",
                        label="frontdoor surface_alignment.drift_check_count matches the checked-in surface-alignment summary",
                        expected=summary_drift_count,
                        actual=str(frontdoor_surface_alignment.get("drift_check_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="frontdoor_surface_alignment_metadata",
                        check_id="surface_alignment_helper_link_count",
                        label="frontdoor surface_alignment.helper_link_count matches the checked-in surface-alignment summary",
                        expected=summary_helper_count,
                        actual=str(frontdoor_surface_alignment.get("helper_link_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="frontdoor_surface_alignment_metadata",
                        check_id="surface_alignment_helper_link_clean_count",
                        label="frontdoor surface_alignment.helper_link_clean_count matches the checked-in surface-alignment summary",
                        expected=summary_helper_clean_count,
                        actual=str(frontdoor_surface_alignment.get("helper_link_clean_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="frontdoor_surface_alignment_metadata",
                        check_id="surface_alignment_release_id",
                        label="frontdoor surface_alignment.release_id matches the checked-in surface-alignment summary",
                        expected=release_id,
                        actual=str(frontdoor_surface_alignment.get("release_id", "")).strip(),
                    ),
                    _equality_check(
                        group_id="frontdoor_surface_alignment_metadata",
                        check_id="surface_alignment_delivery_status",
                        label="frontdoor surface_alignment.delivery_status matches the checked-in surface-alignment summary",
                        expected=delivery_status,
                        actual=str(frontdoor_surface_alignment.get("delivery_status", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_alignment_metadata",
                        check_id="surface_summary_status",
                        label="entrypoints.surface_summary.surface_alignment_status matches the checked-in surface-alignment summary",
                        expected=summary_status,
                        actual=str(surface_summary.get("surface_alignment_status", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_alignment_metadata",
                        check_id="surface_summary_check_count",
                        label="entrypoints.surface_summary.surface_alignment_check_count matches the checked-in surface-alignment summary",
                        expected=summary_checked_count,
                        actual=str(surface_summary.get("surface_alignment_check_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_alignment_metadata",
                        check_id="surface_summary_drift_check_count",
                        label="entrypoints.surface_summary.surface_alignment_drift_check_count matches the checked-in surface-alignment summary",
                        expected=summary_drift_count,
                        actual=str(surface_summary.get("surface_alignment_drift_check_count", "")).strip(),
                    ),
                ]
            )

            for prefix, payload_mapping in (
                ("surface_alignment", entrypoints_surface_alignment),
                ("current_entrypoints_surface_alignment", entrypoints_current_surface_alignment),
            ):
                checks.extend(
                    [
                        _equality_check(
                            group_id="entrypoints_surface_alignment_metadata",
                            check_id=f"{prefix}_status",
                            label=f"entrypoints {prefix}.status matches the checked-in surface-alignment summary",
                            expected=summary_status,
                            actual=str(payload_mapping.get("status", "")).strip(),
                        ),
                        _equality_check(
                            group_id="entrypoints_surface_alignment_metadata",
                            check_id=f"{prefix}_is_clean",
                            label=f"entrypoints {prefix}.is_clean matches the checked-in surface-alignment summary",
                            expected=str(bool(summary_payload.get("is_clean"))),
                            actual=str(bool(payload_mapping.get("is_clean"))),
                        ),
                        _equality_check(
                            group_id="entrypoints_surface_alignment_metadata",
                            check_id=f"{prefix}_checked_check_count",
                            label=f"entrypoints {prefix}.checked_check_count matches the checked-in surface-alignment summary",
                            expected=summary_checked_count,
                            actual=str(payload_mapping.get("checked_check_count", "")).strip(),
                        ),
                        _equality_check(
                            group_id="entrypoints_surface_alignment_metadata",
                            check_id=f"{prefix}_clean_check_count",
                            label=f"entrypoints {prefix}.clean_check_count matches the checked-in surface-alignment summary",
                            expected=summary_clean_count,
                            actual=str(payload_mapping.get("clean_check_count", "")).strip(),
                        ),
                        _equality_check(
                            group_id="entrypoints_surface_alignment_metadata",
                            check_id=f"{prefix}_drift_check_count",
                            label=f"entrypoints {prefix}.drift_check_count matches the checked-in surface-alignment summary",
                            expected=summary_drift_count,
                            actual=str(payload_mapping.get("drift_check_count", "")).strip(),
                        ),
                        _equality_check(
                            group_id="entrypoints_surface_alignment_metadata",
                            check_id=f"{prefix}_helper_link_count",
                            label=f"entrypoints {prefix}.helper_link_count matches the checked-in surface-alignment summary",
                            expected=summary_helper_count,
                            actual=str(payload_mapping.get("helper_link_count", "")).strip(),
                        ),
                        _equality_check(
                            group_id="entrypoints_surface_alignment_metadata",
                            check_id=f"{prefix}_helper_link_clean_count",
                            label=f"entrypoints {prefix}.helper_link_clean_count matches the checked-in surface-alignment summary",
                            expected=summary_helper_clean_count,
                            actual=str(payload_mapping.get("helper_link_clean_count", "")).strip(),
                        ),
                        _equality_check(
                            group_id="entrypoints_surface_alignment_metadata",
                            check_id=f"{prefix}_checked_frontdoor_manifest_json",
                            label=f"entrypoints {prefix}.checked_frontdoor_manifest_json matches the checked-in surface-alignment summary",
                            expected=frontdoor_manifest_repo,
                            actual=str(payload_mapping.get("checked_frontdoor_manifest_json", "")).strip(),
                        ),
                        _equality_check(
                            group_id="entrypoints_surface_alignment_metadata",
                            check_id=f"{prefix}_checked_frontdoor_index_html",
                            label=f"entrypoints {prefix}.checked_frontdoor_index_html matches the checked-in surface-alignment summary",
                            expected=frontdoor_index_repo,
                            actual=str(payload_mapping.get("checked_frontdoor_index_html", "")).strip(),
                        ),
                        _equality_check(
                            group_id="entrypoints_surface_alignment_metadata",
                            check_id=f"{prefix}_checked_entrypoints_json",
                            label=f"entrypoints {prefix}.checked_entrypoints_json matches the checked-in surface-alignment summary",
                            expected=entrypoints_json_repo,
                            actual=str(payload_mapping.get("checked_entrypoints_json", "")).strip(),
                        ),
                        _equality_check(
                            group_id="entrypoints_surface_alignment_metadata",
                            check_id=f"{prefix}_checked_entrypoints_markdown",
                            label=f"entrypoints {prefix}.checked_entrypoints_markdown matches the checked-in surface-alignment summary",
                            expected=entrypoints_markdown_repo,
                            actual=str(payload_mapping.get("checked_entrypoints_markdown", "")).strip(),
                        ),
                    ]
                )

            checks.extend(
                [
                    _equality_check(
                        group_id="surface_alignment_checked_paths",
                        check_id="checked_paths_frontdoor_manifest_json",
                        label="surface-alignment checked_paths.frontdoor_manifest_json matches the checked-in frontdoor manifest",
                        expected=frontdoor_manifest_repo,
                        actual=str(checked_paths.get("frontdoor_manifest_json", "")).strip(),
                    ),
                    _equality_check(
                        group_id="surface_alignment_checked_paths",
                        check_id="checked_paths_frontdoor_index_html",
                        label="surface-alignment checked_paths.frontdoor_index_html matches the checked-in frontdoor HTML",
                        expected=frontdoor_index_repo,
                        actual=str(checked_paths.get("frontdoor_index_html", "")).strip(),
                    ),
                    _equality_check(
                        group_id="surface_alignment_checked_paths",
                        check_id="checked_paths_entrypoints_json",
                        label="surface-alignment checked_paths.entrypoints_json matches the checked-in entrypoints JSON",
                        expected=entrypoints_json_repo,
                        actual=str(checked_paths.get("entrypoints_json", "")).strip(),
                    ),
                    _equality_check(
                        group_id="surface_alignment_checked_paths",
                        check_id="checked_paths_entrypoints_markdown",
                        label="surface-alignment checked_paths.entrypoints_markdown matches the checked-in entrypoints Markdown",
                        expected=entrypoints_markdown_repo,
                        actual=str(checked_paths.get("entrypoints_markdown", "")).strip(),
                    ),
                    _equality_check(
                        group_id="surface_alignment_checked_paths",
                        check_id="checked_paths_surface_alignment_json",
                        label="surface-alignment checked_paths.surface_alignment_json matches the checked-in surface-alignment JSON",
                        expected=surface_alignment_json_repo,
                        actual=str(checked_paths.get("surface_alignment_json", "")).strip(),
                    ),
                    _equality_check(
                        group_id="surface_alignment_checked_paths",
                        check_id="checked_paths_surface_alignment_markdown",
                        label="surface-alignment checked_paths.surface_alignment_markdown matches the checked-in surface-alignment Markdown",
                        expected=surface_alignment_markdown_repo,
                        actual=str(checked_paths.get("surface_alignment_markdown", "")).strip(),
                    ),
                    _equality_check(
                        group_id="surface_alignment_checked_paths",
                        check_id="checked_paths_surface_alignment_console",
                        label="surface-alignment checked_paths.surface_alignment_console matches the checked-in surface-alignment console summary",
                        expected=surface_alignment_console_repo,
                        actual=str(checked_paths.get("surface_alignment_console", "")).strip(),
                    ),
                ]
            )

    checks.extend(
        [
            _equality_check(
                group_id="repo_frontdoor_refs",
                check_id="index_html",
                label="entrypoints.repo_frontdoor.index_html still points at the checked-in frontdoor HTML",
                expected=frontdoor_index_repo,
                actual=str(repo_frontdoor.get("index_html", "")).strip(),
            ),
            _equality_check(
                group_id="repo_frontdoor_refs",
                check_id="manifest_json",
                label="entrypoints.repo_frontdoor.manifest_json still points at the checked-in frontdoor manifest",
                expected=frontdoor_manifest_repo,
                actual=str(repo_frontdoor.get("manifest_json", "")).strip(),
            ),
            _equality_check(
                group_id="repo_frontdoor_refs",
                check_id="current_delivery_manifest_json",
                label="entrypoints.repo_frontdoor.current_delivery_manifest_json still matches the frontdoor landing-manifest path",
                expected=current_delivery_manifest_repo,
                actual=str(repo_frontdoor.get("current_delivery_manifest_json", "")).strip(),
            ),
            _equality_check(
                group_id="repo_frontdoor_refs",
                check_id="current_bundle_zip",
                label="entrypoints.repo_frontdoor.current_bundle_zip still matches the frontdoor current-bundle ZIP",
                expected=current_bundle_zip_repo,
                actual=str(repo_frontdoor.get("current_bundle_zip", "")).strip(),
            ),
            _equality_check(
                group_id="repo_frontdoor_refs",
                check_id="latest_bundle_zip",
                label="entrypoints.repo_frontdoor.latest_bundle_zip still matches the frontdoor latest-bundle ZIP alias",
                expected=latest_bundle_zip_repo,
                actual=str(repo_frontdoor.get("latest_bundle_zip", "")).strip(),
            ),
            _equality_check(
                group_id="repo_frontdoor_refs",
                check_id="latest_bundle_pointer_json",
                label="entrypoints.repo_frontdoor.latest_bundle_pointer_json still matches the frontdoor latest-bundle pointer JSON",
                expected=latest_bundle_pointer_json_repo,
                actual=str(repo_frontdoor.get("latest_bundle_pointer_json", "")).strip(),
            ),
            _equality_check(
                group_id="repo_frontdoor_refs",
                check_id="browse_primary_href",
                label="entrypoints.repo_frontdoor.browse_primary_href still matches the frontdoor browse-first primary action",
                expected=browse_primary_repo,
                actual=str(repo_frontdoor.get("browse_primary_href", "")).strip(),
            ),
            _equality_check(
                group_id="repo_frontdoor_refs",
                check_id="download_primary_href",
                label="entrypoints.repo_frontdoor.download_primary_href still matches the frontdoor download-first primary action",
                expected=download_primary_repo,
                actual=str(repo_frontdoor.get("download_primary_href", "")).strip(),
            ),
        ]
    )

    checks.extend(
        [
            _presence_check(
                group_id="linked_target_presence",
                check_id="current_delivery_manifest_exists",
                label="frontdoor current-delivery landing manifest still exists",
                expected=current_delivery_manifest_repo,
                present=current_delivery_manifest_exists,
            ),
            _presence_check(
                group_id="linked_target_presence",
                check_id="current_bundle_zip_exists",
                label="frontdoor current-bundle ZIP still exists",
                expected=current_bundle_zip_repo,
                present=current_bundle_zip_exists,
            ),
            _presence_check(
                group_id="linked_target_presence",
                check_id="latest_bundle_zip_exists",
                label="frontdoor latest-bundle ZIP alias still exists",
                expected=latest_bundle_zip_repo,
                present=latest_bundle_zip_exists,
            ),
            _presence_check(
                group_id="linked_target_presence",
                check_id="latest_bundle_pointer_json_exists",
                label="frontdoor latest-bundle pointer JSON still exists",
                expected=latest_bundle_pointer_json_repo,
                present=latest_bundle_pointer_json_exists,
            ),
            _presence_check(
                group_id="linked_target_presence",
                check_id="viewer_manifest_exists",
                label="frontdoor viewer manifest JSON still exists",
                expected=viewer_manifest_repo,
                present=viewer_manifest_exists,
            ),
            _presence_check(
                group_id="linked_target_presence",
                check_id="browse_primary_target_exists",
                label="frontdoor browse-first primary target still exists",
                expected=browse_primary_repo,
                present=browse_primary_exists,
            ),
            _presence_check(
                group_id="linked_target_presence",
                check_id="download_primary_target_exists",
                label="frontdoor download-first primary target still exists",
                expected=download_primary_repo,
                present=download_primary_exists,
            ),
            _presence_check(
                group_id="linked_target_presence",
                check_id="open_current_delivery_target_exists",
                label="frontdoor current-delivery page still exists",
                expected=open_current_delivery_repo,
                present=open_current_delivery_exists,
            ),
        ]
    )

    if require_surface_health_visibility:
        checks.extend(
            _build_surface_health_visibility_checks(
                project_root=project_root,
                frontdoor_html_text=frontdoor_html_text,
                helper_href_set=helper_href_set,
                helper_label_set=helper_label_set,
                release_id=release_id,
                base_id=base_id,
                lot_size=lot_size,
                delivery_status=delivery_status,
                exact_status=exact_status,
                current_frontdoor=current_frontdoor,
                frontdoor_actions=frontdoor_actions,
                frontdoor_surface_health=frontdoor_surface_health,
                linked_assets=linked_assets,
                entrypoints_actions=entrypoints_actions,
                entrypoints_surface_health=entrypoints_surface_health,
                entrypoints_current_surface_health=entrypoints_current_surface_health,
                surface_summary=surface_summary,
                surface_health_json_path=current_surface_health_json_path,
                surface_health_markdown_path=current_surface_health_markdown_path,
                surface_health_console_path=current_surface_health_console_path,
                surface_health_json_relative=surface_health_json_relative,
                surface_health_markdown_relative=surface_health_markdown_relative,
                surface_health_console_relative=surface_health_console_relative,
                surface_health_json_repo=surface_health_json_repo,
                surface_health_markdown_repo=surface_health_markdown_repo,
                surface_health_console_repo=surface_health_console_repo,
                health_summary_payload=health_summary_payload,
                health_active_contract=health_active_contract,
                health_exact=health_exact,
                health_source_summaries=health_source_summaries,
                health_checked_surfaces=health_checked_surfaces,
                frontdoor_manifest_repo=frontdoor_manifest_repo,
                frontdoor_index_repo=frontdoor_index_repo,
                entrypoints_json_repo=entrypoints_json_repo,
                entrypoints_markdown_repo=entrypoints_markdown_repo,
                surface_alignment_json_repo=surface_alignment_json_repo,
                surface_alignment_markdown_repo=surface_alignment_markdown_repo,
                surface_alignment_console_repo=surface_alignment_console_repo,
            )
        )

    return SingleBaseDeliverySurfaceAlignmentResult(
        project_root=project_root,
        frontdoor_manifest_json_path=frontdoor_manifest_json_path,
        frontdoor_index_html_path=frontdoor_index_html_path,
        entrypoints_json_path=entrypoints_json_path,
        entrypoints_markdown_path=entrypoints_markdown_path,
        surface_alignment_json_path=surface_alignment_json_path,
        surface_alignment_markdown_path=surface_alignment_markdown_path,
        surface_alignment_console_path=surface_alignment_console_path,
        surface_health_json_path=current_surface_health_json_path,
        surface_health_markdown_path=current_surface_health_markdown_path,
        surface_health_console_path=current_surface_health_console_path,
        release_id=release_id,
        base_id=base_id,
        lot_size=lot_size,
        delivery_status=delivery_status,
        exact_full_scale_certified_status=exact_status,
        checks=tuple(checks),
    )


def _build_surface_health_visibility_checks(
    *,
    project_root: Path,
    frontdoor_html_text: str,
    helper_href_set: set[str],
    helper_label_set: set[str],
    release_id: str,
    base_id: str,
    lot_size: int,
    delivery_status: str,
    exact_status: str,
    current_frontdoor: Mapping[str, Any],
    frontdoor_actions: Mapping[str, Any],
    frontdoor_surface_health: Mapping[str, Any],
    linked_assets: Mapping[str, Any],
    entrypoints_actions: Mapping[str, Any],
    entrypoints_surface_health: Mapping[str, Any],
    entrypoints_current_surface_health: Mapping[str, Any],
    surface_summary: Mapping[str, Any],
    surface_health_json_path: Path | None,
    surface_health_markdown_path: Path | None,
    surface_health_console_path: Path | None,
    surface_health_json_relative: str,
    surface_health_markdown_relative: str,
    surface_health_console_relative: str,
    surface_health_json_repo: str,
    surface_health_markdown_repo: str,
    surface_health_console_repo: str,
    health_summary_payload: Mapping[str, Any],
    health_active_contract: Mapping[str, Any],
    health_exact: Mapping[str, Any],
    health_source_summaries: Mapping[str, Any],
    health_checked_surfaces: Mapping[str, Any],
    frontdoor_manifest_repo: str,
    frontdoor_index_repo: str,
    entrypoints_json_repo: str,
    entrypoints_markdown_repo: str,
    surface_alignment_json_repo: str,
    surface_alignment_markdown_repo: str,
    surface_alignment_console_repo: str,
) -> list[SingleBaseDeliverySurfaceAlignmentCheck]:
    checks: list[SingleBaseDeliverySurfaceAlignmentCheck] = []

    checks.extend(
        [
            _equality_check(
                group_id="surface_health_contract",
                check_id="surface_health_release_id",
                label="current-surface-health release id matches the active contract",
                expected=release_id,
                actual=str(health_active_contract.get("release_id", "")).strip(),
            ),
            _equality_check(
                group_id="surface_health_contract",
                check_id="surface_health_base_id",
                label="current-surface-health base id matches the active contract",
                expected=base_id,
                actual=str(health_active_contract.get("base_id", "")).strip(),
            ),
            _equality_check(
                group_id="surface_health_contract",
                check_id="surface_health_lot_size",
                label="current-surface-health lot size matches the active contract",
                expected=str(lot_size),
                actual=str(health_active_contract.get("lot_size", "")).strip(),
            ),
            _equality_check(
                group_id="surface_health_contract",
                check_id="surface_health_delivery_status",
                label="current-surface-health delivery status matches the active contract",
                expected=delivery_status,
                actual=str(health_active_contract.get("delivery_status", "")).strip(),
            ),
            _equality_check(
                group_id="surface_health_contract",
                check_id="surface_health_exact_status",
                label="current-surface-health exact status matches the active exact status",
                expected=exact_status,
                actual=str(health_exact.get("status", "")).strip(),
            ),
        ]
    )

    checks.extend(
        [
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="current_frontdoor_surface_health_json",
                label="current_frontdoor current_surface_health_json points at the checked-in surface-health JSON",
                expected=surface_health_json_relative,
                actual=str(current_frontdoor.get("current_surface_health_json", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="current_frontdoor_surface_health_markdown",
                label="current_frontdoor current_surface_health_markdown points at the checked-in surface-health Markdown",
                expected=surface_health_markdown_relative,
                actual=str(current_frontdoor.get("current_surface_health_markdown", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="current_frontdoor_surface_health_console",
                label="current_frontdoor current_surface_health_console points at the checked-in surface-health console snapshot",
                expected=surface_health_console_relative,
                actual=str(current_frontdoor.get("current_surface_health_console", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="actions_current_surface_health_json",
                label="frontdoor actions.current_surface_health_json points at the checked-in surface-health JSON",
                expected=surface_health_json_relative,
                actual=str(frontdoor_actions.get("current_surface_health_json", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="actions_current_surface_health_markdown",
                label="frontdoor actions.current_surface_health_markdown points at the checked-in surface-health Markdown",
                expected=surface_health_markdown_relative,
                actual=str(frontdoor_actions.get("current_surface_health_markdown", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="actions_current_surface_health_console",
                label="frontdoor actions.current_surface_health_console points at the checked-in surface-health console snapshot",
                expected=surface_health_console_relative,
                actual=str(frontdoor_actions.get("current_surface_health_console", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="surface_health_json",
                label="frontdoor surface_health.json points at the checked-in surface-health JSON",
                expected=surface_health_json_relative,
                actual=str(frontdoor_surface_health.get("json", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="surface_health_markdown",
                label="frontdoor surface_health.markdown points at the checked-in surface-health Markdown",
                expected=surface_health_markdown_relative,
                actual=str(frontdoor_surface_health.get("markdown", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="surface_health_console",
                label="frontdoor surface_health.console points at the checked-in surface-health console snapshot",
                expected=surface_health_console_relative,
                actual=str(frontdoor_surface_health.get("console", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="surface_health_json_repo_path",
                label="frontdoor surface_health.json_repo_path matches the checked-in surface-health JSON repo path",
                expected=surface_health_json_repo,
                actual=str(frontdoor_surface_health.get("json_repo_path", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="surface_health_markdown_repo_path",
                label="frontdoor surface_health.markdown_repo_path matches the checked-in surface-health Markdown repo path",
                expected=surface_health_markdown_repo,
                actual=str(frontdoor_surface_health.get("markdown_repo_path", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="surface_health_console_repo_path",
                label="frontdoor surface_health.console_repo_path matches the checked-in surface-health console repo path",
                expected=surface_health_console_repo,
                actual=str(frontdoor_surface_health.get("console_repo_path", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="linked_assets_current_surface_health_json",
                label="frontdoor linked_assets.current_surface_health_json points at the checked-in surface-health JSON",
                expected=surface_health_json_relative,
                actual=str(linked_assets.get("current_surface_health_json", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="linked_assets_current_surface_health_markdown",
                label="frontdoor linked_assets.current_surface_health_markdown points at the checked-in surface-health Markdown",
                expected=surface_health_markdown_relative,
                actual=str(linked_assets.get("current_surface_health_markdown", "")).strip(),
            ),
            _equality_check(
                group_id="frontdoor_surface_health_refs",
                check_id="linked_assets_current_surface_health_console",
                label="frontdoor linked_assets.current_surface_health_console points at the checked-in surface-health console snapshot",
                expected=surface_health_console_relative,
                actual=str(linked_assets.get("current_surface_health_console", "")).strip(),
            ),
        ]
    )

    checks.extend(
        [
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_surface_health_json_href",
                label="frontdoor helper links still include the current surface-health JSON",
                expected=surface_health_json_relative,
                present=surface_health_json_relative in helper_href_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_surface_health_markdown_href",
                label="frontdoor helper links still include the current surface-health Markdown",
                expected=surface_health_markdown_relative,
                present=surface_health_markdown_relative in helper_href_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_surface_health_console_href",
                label="frontdoor helper links still include the current surface-health console snapshot",
                expected=surface_health_console_relative,
                present=surface_health_console_relative in helper_href_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_label_surface_health_json",
                label="frontdoor helper-link label still advertises Current surface health JSON",
                expected="Current surface health JSON",
                present="Current surface health JSON" in helper_label_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_label_surface_health_markdown",
                label="frontdoor helper-link label still advertises Current surface health Markdown",
                expected="Current surface health Markdown",
                present="Current surface health Markdown" in helper_label_set,
            ),
            _presence_check(
                group_id="frontdoor_helper_links",
                check_id="helper_label_surface_health_console",
                label="frontdoor helper-link label still advertises Current surface health console",
                expected="Current surface health console",
                present="Current surface health console" in helper_label_set,
            ),
            _presence_check(
                group_id="frontdoor_surface_health_html",
                check_id="surface_health_panel_heading",
                label="frontdoor HTML still renders the current surface-health panel heading",
                expected="Current surface health snapshot",
                present="Current surface health snapshot" in frontdoor_html_text,
            ),
            _presence_check(
                group_id="frontdoor_surface_health_html",
                check_id="surface_health_card_heading",
                label="frontdoor HTML still renders the surface-health card heading",
                expected="Surface health",
                present="Surface health" in frontdoor_html_text,
            ),
        ]
    )

    checks.extend(
        [
            _presence_check(
                group_id="linked_target_presence",
                check_id="surface_health_json_exists",
                label="checked-in surface-health JSON snapshot still exists",
                expected=surface_health_json_repo,
                present=surface_health_json_path is not None and surface_health_json_path.is_file(),
            ),
            _presence_check(
                group_id="linked_target_presence",
                check_id="surface_health_markdown_exists",
                label="checked-in surface-health Markdown snapshot still exists",
                expected=surface_health_markdown_repo,
                present=surface_health_markdown_path is not None and surface_health_markdown_path.is_file(),
            ),
            _presence_check(
                group_id="linked_target_presence",
                check_id="surface_health_console_exists",
                label="checked-in surface-health console snapshot still exists",
                expected=surface_health_console_repo,
                present=surface_health_console_path is not None and surface_health_console_path.is_file(),
            ),
        ]
    )

    checks.extend(
        [
            _equality_check(
                group_id="entrypoints_surface_health_refs",
                check_id="actions_current_surface_health_json",
                label="entrypoints.actions.current_surface_health_json still points at the checked-in surface-health JSON",
                expected=surface_health_json_repo,
                actual=str(entrypoints_actions.get("current_surface_health_json", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_surface_health_refs",
                check_id="actions_current_surface_health_markdown",
                label="entrypoints.actions.current_surface_health_markdown still points at the checked-in surface-health Markdown",
                expected=surface_health_markdown_repo,
                actual=str(entrypoints_actions.get("current_surface_health_markdown", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_surface_health_refs",
                check_id="actions_current_surface_health_console",
                label="entrypoints.actions.current_surface_health_console still points at the checked-in surface-health console snapshot",
                expected=surface_health_console_repo,
                actual=str(entrypoints_actions.get("current_surface_health_console", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_surface_health_refs",
                check_id="surface_health_json",
                label="entrypoints.surface_health.json still points at the checked-in surface-health JSON",
                expected=surface_health_json_repo,
                actual=str(entrypoints_surface_health.get("json", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_surface_health_refs",
                check_id="surface_health_markdown",
                label="entrypoints.surface_health.markdown still points at the checked-in surface-health Markdown",
                expected=surface_health_markdown_repo,
                actual=str(entrypoints_surface_health.get("markdown", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_surface_health_refs",
                check_id="surface_health_console",
                label="entrypoints.surface_health.console still points at the checked-in surface-health console snapshot",
                expected=surface_health_console_repo,
                actual=str(entrypoints_surface_health.get("console", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_surface_health_refs",
                check_id="current_entrypoints_surface_health_json",
                label="entrypoints.current_entrypoints.surface_health.json still points at the checked-in surface-health JSON",
                expected=surface_health_json_repo,
                actual=str(entrypoints_current_surface_health.get("json", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_surface_health_refs",
                check_id="current_entrypoints_surface_health_markdown",
                label="entrypoints.current_entrypoints.surface_health.markdown still points at the checked-in surface-health Markdown",
                expected=surface_health_markdown_repo,
                actual=str(entrypoints_current_surface_health.get("markdown", "")).strip(),
            ),
            _equality_check(
                group_id="entrypoints_surface_health_refs",
                check_id="current_entrypoints_surface_health_console",
                label="entrypoints.current_entrypoints.surface_health.console still points at the checked-in surface-health console snapshot",
                expected=surface_health_console_repo,
                actual=str(entrypoints_current_surface_health.get("console", "")).strip(),
            ),
        ]
    )

    summary_status = str(health_summary_payload.get("status", "")).strip()
    summary_checked_count = str(health_summary_payload.get("checked_check_count", "")).strip()
    summary_clean_count = str(health_summary_payload.get("clean_check_count", "")).strip()
    summary_drift_count = str(health_summary_payload.get("drift_check_count", "")).strip()
    summary_helper_count = str(health_summary_payload.get("helper_link_count", "")).strip()
    summary_helper_clean_count = str(health_summary_payload.get("helper_link_clean_count", "")).strip()
    summary_text = str(health_summary_payload.get("summary_text", "")).strip()
    summary_is_clean = str(bool(health_summary_payload.get("is_clean")))

    if summary_status:
        checks.extend(
            [
                _presence_check(
                    group_id="frontdoor_surface_health_html",
                    check_id="surface_health_status_text",
                    label="frontdoor HTML still renders the surface-health status text",
                    expected=summary_status,
                    present=summary_status in frontdoor_html_text,
                ),
                _presence_check(
                    group_id="frontdoor_surface_health_html",
                    check_id="surface_health_summary_text",
                    label="frontdoor HTML still renders the surface-health summary text",
                    expected=summary_text,
                    present=summary_text in frontdoor_html_text,
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="current_frontdoor_surface_health_status",
                    label="current_frontdoor surface_health_status matches the checked-in surface-health snapshot",
                    expected=summary_status,
                    actual=str(current_frontdoor.get("surface_health_status", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="current_frontdoor_surface_health_summary_text",
                    label="current_frontdoor surface_health_summary_text matches the checked-in surface-health snapshot",
                    expected=summary_text,
                    actual=str(current_frontdoor.get("surface_health_summary_text", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="current_frontdoor_surface_health_check_count",
                    label="current_frontdoor surface_health_check_count matches the checked-in surface-health snapshot",
                    expected=summary_checked_count,
                    actual=str(current_frontdoor.get("surface_health_check_count", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="current_frontdoor_surface_health_drift_check_count",
                    label="current_frontdoor surface_health_drift_check_count matches the checked-in surface-health snapshot",
                    expected=summary_drift_count,
                    actual=str(current_frontdoor.get("surface_health_drift_check_count", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="surface_health_status",
                    label="frontdoor surface_health.status matches the checked-in surface-health snapshot",
                    expected=summary_status,
                    actual=str(frontdoor_surface_health.get("status", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="surface_health_summary_text",
                    label="frontdoor surface_health.summary_text matches the checked-in surface-health snapshot",
                    expected=summary_text,
                    actual=str(frontdoor_surface_health.get("summary_text", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="surface_health_checked_check_count",
                    label="frontdoor surface_health.checked_check_count matches the checked-in surface-health snapshot",
                    expected=summary_checked_count,
                    actual=str(frontdoor_surface_health.get("checked_check_count", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="surface_health_clean_check_count",
                    label="frontdoor surface_health.clean_check_count matches the checked-in surface-health snapshot",
                    expected=summary_clean_count,
                    actual=str(frontdoor_surface_health.get("clean_check_count", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="surface_health_drift_check_count",
                    label="frontdoor surface_health.drift_check_count matches the checked-in surface-health snapshot",
                    expected=summary_drift_count,
                    actual=str(frontdoor_surface_health.get("drift_check_count", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="surface_health_helper_link_count",
                    label="frontdoor surface_health.helper_link_count matches the checked-in surface-health snapshot",
                    expected=summary_helper_count,
                    actual=str(frontdoor_surface_health.get("helper_link_count", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="surface_health_helper_link_clean_count",
                    label="frontdoor surface_health.helper_link_clean_count matches the checked-in surface-health snapshot",
                    expected=summary_helper_clean_count,
                    actual=str(frontdoor_surface_health.get("helper_link_clean_count", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="surface_health_release_id",
                    label="frontdoor surface_health.release_id matches the active release id",
                    expected=release_id,
                    actual=str(frontdoor_surface_health.get("release_id", "")).strip(),
                ),
                _equality_check(
                    group_id="frontdoor_surface_health_metadata",
                    check_id="surface_health_delivery_status",
                    label="frontdoor surface_health.delivery_status matches the active delivery status",
                    expected=delivery_status,
                    actual=str(frontdoor_surface_health.get("delivery_status", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_health_metadata",
                    check_id="surface_summary_status",
                    label="entrypoints.surface_summary.surface_health_status matches the checked-in surface-health snapshot",
                    expected=summary_status,
                    actual=str(surface_summary.get("surface_health_status", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_health_metadata",
                    check_id="surface_summary_check_count",
                    label="entrypoints.surface_summary.surface_health_check_count matches the checked-in surface-health snapshot",
                    expected=summary_checked_count,
                    actual=str(surface_summary.get("surface_health_check_count", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_health_metadata",
                    check_id="surface_summary_drift_check_count",
                    label="entrypoints.surface_summary.surface_health_drift_check_count matches the checked-in surface-health snapshot",
                    expected=summary_drift_count,
                    actual=str(surface_summary.get("surface_health_drift_check_count", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_health_metadata",
                    check_id="surface_summary_helper_link_count",
                    label="entrypoints.surface_summary.surface_health_helper_link_count matches the checked-in surface-health snapshot",
                    expected=summary_helper_count,
                    actual=str(surface_summary.get("surface_health_helper_link_count", "")).strip(),
                ),
                _equality_check(
                    group_id="entrypoints_surface_health_metadata",
                    check_id="surface_summary_helper_link_clean_count",
                    label="entrypoints.surface_summary.surface_health_helper_link_clean_count matches the checked-in surface-health snapshot",
                    expected=summary_helper_clean_count,
                    actual=str(surface_summary.get("surface_health_helper_link_clean_count", "")).strip(),
                ),
            ]
        )

        for prefix, payload_mapping in (
            ("surface_health", entrypoints_surface_health),
            ("current_entrypoints_surface_health", entrypoints_current_surface_health),
        ):
            checks.extend(
                [
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_status",
                        label=f"entrypoints {prefix}.status matches the checked-in surface-health snapshot",
                        expected=summary_status,
                        actual=str(payload_mapping.get("status", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_summary_text",
                        label=f"entrypoints {prefix}.summary_text matches the checked-in surface-health snapshot",
                        expected=summary_text,
                        actual=str(payload_mapping.get("summary_text", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_is_clean",
                        label=f"entrypoints {prefix}.is_clean matches the checked-in surface-health snapshot",
                        expected=summary_is_clean,
                        actual=str(bool(payload_mapping.get("is_clean"))),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_checked_check_count",
                        label=f"entrypoints {prefix}.checked_check_count matches the checked-in surface-health snapshot",
                        expected=summary_checked_count,
                        actual=str(payload_mapping.get("checked_check_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_clean_check_count",
                        label=f"entrypoints {prefix}.clean_check_count matches the checked-in surface-health snapshot",
                        expected=summary_clean_count,
                        actual=str(payload_mapping.get("clean_check_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_drift_check_count",
                        label=f"entrypoints {prefix}.drift_check_count matches the checked-in surface-health snapshot",
                        expected=summary_drift_count,
                        actual=str(payload_mapping.get("drift_check_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_helper_link_count",
                        label=f"entrypoints {prefix}.helper_link_count matches the checked-in surface-health snapshot",
                        expected=summary_helper_count,
                        actual=str(payload_mapping.get("helper_link_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_helper_link_clean_count",
                        label=f"entrypoints {prefix}.helper_link_clean_count matches the checked-in surface-health snapshot",
                        expected=summary_helper_clean_count,
                        actual=str(payload_mapping.get("helper_link_clean_count", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_checked_frontdoor_manifest_json",
                        label=f"entrypoints {prefix}.checked_frontdoor_manifest_json matches the checked-in surface-health snapshot",
                        expected=frontdoor_manifest_repo,
                        actual=str(payload_mapping.get("checked_frontdoor_manifest_json", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_checked_frontdoor_index_html",
                        label=f"entrypoints {prefix}.checked_frontdoor_index_html matches the checked-in surface-health snapshot",
                        expected=frontdoor_index_repo,
                        actual=str(payload_mapping.get("checked_frontdoor_index_html", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_checked_entrypoints_json",
                        label=f"entrypoints {prefix}.checked_entrypoints_json matches the checked-in surface-health snapshot",
                        expected=entrypoints_json_repo,
                        actual=str(payload_mapping.get("checked_entrypoints_json", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_checked_entrypoints_markdown",
                        label=f"entrypoints {prefix}.checked_entrypoints_markdown matches the checked-in surface-health snapshot",
                        expected=entrypoints_markdown_repo,
                        actual=str(payload_mapping.get("checked_entrypoints_markdown", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_source_surface_alignment_json",
                        label=f"entrypoints {prefix}.source_surface_alignment_json matches the checked-in surface-alignment JSON",
                        expected=surface_alignment_json_repo,
                        actual=str(payload_mapping.get("source_surface_alignment_json", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_source_surface_alignment_markdown",
                        label=f"entrypoints {prefix}.source_surface_alignment_markdown matches the checked-in surface-alignment Markdown",
                        expected=surface_alignment_markdown_repo,
                        actual=str(payload_mapping.get("source_surface_alignment_markdown", "")).strip(),
                    ),
                    _equality_check(
                        group_id="entrypoints_surface_health_metadata",
                        check_id=f"{prefix}_source_surface_alignment_console",
                        label=f"entrypoints {prefix}.source_surface_alignment_console matches the checked-in surface-alignment console snapshot",
                        expected=surface_alignment_console_repo,
                        actual=str(payload_mapping.get("source_surface_alignment_console", "")).strip(),
                    ),
                ]
            )

        checks.extend(
            [
                _equality_check(
                    group_id="surface_health_checked_paths",
                    check_id="checked_frontdoor_manifest_json",
                    label="current-surface-health checked_consumer_surfaces.frontdoor_manifest_json matches the checked-in frontdoor manifest",
                    expected=frontdoor_manifest_repo,
                    actual=str(health_checked_surfaces.get("frontdoor_manifest_json", "")).strip(),
                ),
                _equality_check(
                    group_id="surface_health_checked_paths",
                    check_id="checked_frontdoor_index_html",
                    label="current-surface-health checked_consumer_surfaces.frontdoor_index_html matches the checked-in frontdoor HTML",
                    expected=frontdoor_index_repo,
                    actual=str(health_checked_surfaces.get("frontdoor_index_html", "")).strip(),
                ),
                _equality_check(
                    group_id="surface_health_checked_paths",
                    check_id="checked_entrypoints_json",
                    label="current-surface-health checked_consumer_surfaces.entrypoints_json matches the checked-in entrypoints JSON",
                    expected=entrypoints_json_repo,
                    actual=str(health_checked_surfaces.get("entrypoints_json", "")).strip(),
                ),
                _equality_check(
                    group_id="surface_health_checked_paths",
                    check_id="checked_entrypoints_markdown",
                    label="current-surface-health checked_consumer_surfaces.entrypoints_markdown matches the checked-in entrypoints Markdown",
                    expected=entrypoints_markdown_repo,
                    actual=str(health_checked_surfaces.get("entrypoints_markdown", "")).strip(),
                ),
                _equality_check(
                    group_id="surface_health_checked_paths",
                    check_id="source_surface_alignment_json",
                    label="current-surface-health source_summaries.surface_alignment_json matches the checked-in surface-alignment JSON",
                    expected=surface_alignment_json_repo,
                    actual=str(health_source_summaries.get("surface_alignment_json", "")).strip(),
                ),
                _equality_check(
                    group_id="surface_health_checked_paths",
                    check_id="source_surface_alignment_markdown",
                    label="current-surface-health source_summaries.surface_alignment_markdown matches the checked-in surface-alignment Markdown",
                    expected=surface_alignment_markdown_repo,
                    actual=str(health_source_summaries.get("surface_alignment_markdown", "")).strip(),
                ),
                _equality_check(
                    group_id="surface_health_checked_paths",
                    check_id="source_surface_alignment_console",
                    label="current-surface-health source_summaries.surface_alignment_console matches the checked-in surface-alignment console snapshot",
                    expected=surface_alignment_console_repo,
                    actual=str(health_source_summaries.get("surface_alignment_console", "")).strip(),
                ),
            ]
        )

    return checks




@dataclass(frozen=True)
class SingleBaseDeliverySurfaceAlignmentOutputs:
    result: SingleBaseDeliverySurfaceAlignmentResult
    json_output_path: Path
    markdown_output_path: Path
    console_output_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.to_dict(),
            "json_output_path": str(self.json_output_path),
            "markdown_output_path": str(self.markdown_output_path),
            "console_output_path": str(self.console_output_path),
        }


def write_single_base_delivery_surface_alignment_outputs(
    result: SingleBaseDeliverySurfaceAlignmentResult,
    *,
    json_output_path: Path = _DEFAULT_OUTPUT_JSON,
    markdown_output_path: Path = _DEFAULT_OUTPUT_MARKDOWN,
    console_output_path: Path = _DEFAULT_OUTPUT_CONSOLE,
) -> SingleBaseDeliverySurfaceAlignmentOutputs:
    json_output_path = Path(json_output_path)
    markdown_output_path = Path(markdown_output_path)
    console_output_path = Path(console_output_path)
    atomic_write_json(json_output_path, result.to_dict())
    _atomic_write_text(markdown_output_path, result.to_markdown())
    _atomic_write_text(console_output_path, result.to_console_text() + "\n")
    return SingleBaseDeliverySurfaceAlignmentOutputs(
        result=result,
        json_output_path=json_output_path,
        markdown_output_path=markdown_output_path,
        console_output_path=console_output_path,
    )



def _extract_helper_links(index_html_path: Path) -> tuple[dict[str, str], ...]:
    text = index_html_path.read_text(encoding="utf-8")
    match = re.search(r'<div class="helper-links">(.*?)</div>', text, flags=re.DOTALL)
    if match is None:
        raise SingleBaseDeliverySurfaceAlignmentError(
            f"frontdoor HTML does not contain a helper-links block: {index_html_path}"
        )
    block = match.group(1)
    links: list[dict[str, str]] = []
    for anchor in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.DOTALL):
        href = anchor.group(1).strip()
        label = re.sub(r"<[^>]+>", "", anchor.group(2)).strip()
        links.append({"href": href, "label": label})
    if not links:
        raise SingleBaseDeliverySurfaceAlignmentError(
            f"frontdoor helper-links block does not contain any anchors: {index_html_path}"
        )
    return tuple(links)



def _repo_path_from_frontdoor_relative(
    project_root: Path,
    frontdoor_dir: Path,
    relative_path: str,
) -> tuple[str, bool]:
    candidate_text = relative_path.strip()
    if not candidate_text:
        return "<missing>", False
    candidate = (frontdoor_dir / candidate_text).resolve()
    return _display_repo_path(project_root, candidate), candidate.exists()



def _equality_check(
    *,
    group_id: str,
    check_id: str,
    label: str,
    expected: str,
    actual: str,
    note: str = "",
) -> SingleBaseDeliverySurfaceAlignmentCheck:
    normalized_expected = expected.strip()
    normalized_actual = actual.strip() if actual.strip() else "<missing>"
    return SingleBaseDeliverySurfaceAlignmentCheck(
        group_id=group_id,
        check_id=check_id,
        label=label,
        expected=normalized_expected,
        actual=normalized_actual,
        is_clean=normalized_actual == normalized_expected,
        note=note,
    )



def _presence_check(
    *,
    group_id: str,
    check_id: str,
    label: str,
    expected: str,
    present: bool,
    note: str = "",
) -> SingleBaseDeliverySurfaceAlignmentCheck:
    return SingleBaseDeliverySurfaceAlignmentCheck(
        group_id=group_id,
        check_id=check_id,
        label=label,
        expected=expected.strip(),
        actual=expected.strip() if present else "<missing>",
        is_clean=present,
        note=note,
    )



def _require_mapping(payload: Mapping[str, Any], key: str, path: Path) -> Mapping[str, Any]:
    mapping = _mapping(payload.get(key))
    if mapping:
        return mapping
    raise SingleBaseDeliverySurfaceAlignmentError(f"{path} does not contain a {key} mapping")



def _require_string(mapping: Mapping[str, Any], key: str, *, context: str) -> str:
    value = str(mapping.get(key, "")).strip()
    if value:
        return value
    raise SingleBaseDeliverySurfaceAlignmentError(f"{context} is missing {key}")



def _require_int(mapping: Mapping[str, Any], key: str, *, context: str) -> int:
    value = mapping.get(key)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SingleBaseDeliverySurfaceAlignmentError(f"{context} is missing integer {key}") from exc



def _resolve_repo_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    resolved = candidate if candidate.is_absolute() else project_root / candidate
    resolved = resolved.resolve()
    if not resolved.exists():
        raise SingleBaseDeliverySurfaceAlignmentError(f"required path does not exist: {resolved}")
    return resolved



def _resolve_expected_repo_path(project_root: Path, path: Path | None) -> Path | None:
    if path is None:
        return None
    candidate = Path(path)
    resolved = candidate if candidate.is_absolute() else project_root / candidate
    return resolved.resolve()



def _display_repo_path(project_root: Path, path: Path) -> str:
    resolved = Path(path).resolve()
    project_root = Path(project_root).resolve()
    try:
        return resolved.relative_to(project_root).as_posix()
    except ValueError:
        return str(resolved)



def _relative_from(base_dir: Path, target_path: Path) -> str:
    return Path(os.path.relpath(str(target_path), start=str(base_dir))).as_posix()



def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}



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



def _md_escape_inline(value: Any) -> str:
    text = str(value)
    if not text:
        return ""
    text = text.replace("|", "\\|")
    if "`" in text:
        return text
    return f"`{text}`"



def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
