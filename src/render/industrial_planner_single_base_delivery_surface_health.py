"""Compact current-surface health artifact for the active IndustrialPlanner single-base line.

This builder compresses the richer no-drift consumer-surface alignment audit down to one
small, stable artifact that CI, reviewer tooling, and script consumers can read without
needing to parse the full detailed audit summary first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from src.io.serializer import load_json_mapping
from src.render.industrial_planner_exact_status import normalize_non_authoritative_exact_status
from src.search.exact_campaign import atomic_write_json

_SURFACE_HEALTH_SOURCE = "industrial_planner_single_base_delivery_surface_health_v1"
_SURFACE_HEALTH_SCHEMA_VERSION = "1.0.0"

_DEFAULT_SURFACE_ALIGNMENT_JSON = Path(
    ".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.json"
)
_DEFAULT_SURFACE_ALIGNMENT_MARKDOWN = Path(
    ".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.md"
)
_DEFAULT_SURFACE_ALIGNMENT_CONSOLE = Path(
    ".artifacts/industrial_planner_single_base_delivery_surface_alignment/surface_alignment_summary.txt"
)
_DEFAULT_OUTPUT_JSON = Path("data/examples/industrial_planner/current_surface_health.json")
_DEFAULT_OUTPUT_MARKDOWN = Path("data/examples/industrial_planner/current_surface_health.md")
_DEFAULT_OUTPUT_CONSOLE = Path("data/examples/industrial_planner/current_surface_health.txt")


class SingleBaseDeliverySurfaceHealthError(RuntimeError):
    """Raised when the compact current-surface health artifact cannot be built safely."""


@dataclass(frozen=True)
class SingleBaseDeliverySurfaceHealthResult:
    project_root: Path
    source_surface_alignment_json_path: Path
    source_surface_alignment_markdown_path: Path
    source_surface_alignment_console_path: Path
    output_json_path: Path
    output_markdown_path: Path
    output_console_path: Path
    release_id: str
    base_id: str
    lot_size: int
    delivery_status: str
    exact_full_scale_certified_status: str
    status: str
    is_clean: bool
    checked_check_count: int
    clean_check_count: int
    drift_check_count: int
    helper_link_count: int
    helper_link_clean_count: int

    @property
    def badge_tone(self) -> str:
        return "healthy" if self.is_clean else "attention"

    @property
    def badge_label(self) -> str:
        return "current surface"

    @property
    def badge_text(self) -> str:
        return f"{self.status} · {self.checked_check_count} checks · {self.drift_check_count} drift"

    def to_payload(self, *, checked_paths: Mapping[str, Any] | None = None) -> dict[str, Any]:
        checked_paths = checked_paths if isinstance(checked_paths, Mapping) else {}
        frontdoor_manifest_json = str(checked_paths.get("frontdoor_manifest_json", "")).strip()
        frontdoor_index_html = str(checked_paths.get("frontdoor_index_html", "")).strip()
        entrypoints_json = str(checked_paths.get("entrypoints_json", "")).strip()
        entrypoints_markdown = str(checked_paths.get("entrypoints_markdown", "")).strip()
        return {
            "metadata": {
                "schema_version": _SURFACE_HEALTH_SCHEMA_VERSION,
                "generated_at": _now_iso(),
                "source": _SURFACE_HEALTH_SOURCE,
            },
            "surface_health": {
                "status": self.status,
                "is_clean": self.is_clean,
                "checked_check_count": self.checked_check_count,
                "clean_check_count": self.clean_check_count,
                "drift_check_count": self.drift_check_count,
                "helper_link_count": self.helper_link_count,
                "helper_link_clean_count": self.helper_link_clean_count,
                "summary_text": self.badge_text,
                "badge": {
                    "label": self.badge_label,
                    "text": self.badge_text,
                    "tone": self.badge_tone,
                },
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
            "source_summaries": {
                "surface_alignment_json": _display_repo_path(
                    self.project_root, self.source_surface_alignment_json_path
                ),
                "surface_alignment_markdown": _display_repo_path(
                    self.project_root, self.source_surface_alignment_markdown_path
                ),
                "surface_alignment_console": _display_repo_path(
                    self.project_root, self.source_surface_alignment_console_path
                ),
            },
            "checked_consumer_surfaces": {
                "frontdoor_manifest_json": frontdoor_manifest_json,
                "frontdoor_index_html": frontdoor_index_html,
                "entrypoints_json": entrypoints_json,
                "entrypoints_markdown": entrypoints_markdown,
            },
            "pointer_paths": {
                "json": _display_repo_path(self.project_root, self.output_json_path),
                "markdown": _display_repo_path(self.project_root, self.output_markdown_path),
                "console": _display_repo_path(self.project_root, self.output_console_path),
            },
            "notes": [
                "This is the smallest checked-in health snapshot for the current single-base consumer surface.",
                "Read this file when you only need the current clean/drift verdict and top-line counts; fall back to the linked surface-alignment summary when you need full per-check detail.",
            ],
        }

    def to_markdown(self, *, checked_paths: Mapping[str, Any] | None = None) -> str:
        payload = self.to_payload(checked_paths=checked_paths)
        surface_health = _mapping(payload.get("surface_health"))
        active_contract = _mapping(payload.get("active_contract"))
        exact_payload = _mapping(payload.get("exact_full_scale_certified"))
        source_summaries = _mapping(payload.get("source_summaries"))
        checked_consumer_surfaces = _mapping(payload.get("checked_consumer_surfaces"))
        notes = [str(note) for note in (payload.get("notes") or []) if str(note).strip()]
        lines = [
            "# IndustrialPlanner Current Surface Health",
            "",
            f"- Release id: `{active_contract.get('release_id', '')}`",
            f"- Base id: `{active_contract.get('base_id', '')}`",
            f"- Lot size: `{active_contract.get('lot_size', '')}`",
            f"- Delivery status: `{active_contract.get('delivery_status', '')}`",
            f"- Exact full-scale CERTIFIED status: `{exact_payload.get('status', '')}`",
            f"- Status: `{surface_health.get('status', '')}`",
            f"- Summary: `{surface_health.get('summary_text', '')}`",
            f"- Helper-link checks: `{surface_health.get('helper_link_count', '')}`",
            "",
            "## Source summaries",
            "",
            f"- Surface alignment JSON: `{source_summaries.get('surface_alignment_json', '')}`",
            f"- Surface alignment Markdown: `{source_summaries.get('surface_alignment_markdown', '')}`",
            f"- Surface alignment console: `{source_summaries.get('surface_alignment_console', '')}`",
            "",
            "## Checked consumer surfaces",
            "",
            f"- Frontdoor manifest JSON: `{checked_consumer_surfaces.get('frontdoor_manifest_json', '')}`",
            f"- Frontdoor index HTML: `{checked_consumer_surfaces.get('frontdoor_index_html', '')}`",
            f"- Entrypoints JSON: `{checked_consumer_surfaces.get('entrypoints_json', '')}`",
            f"- Entrypoints Markdown: `{checked_consumer_surfaces.get('entrypoints_markdown', '')}`",
        ]
        if notes:
            lines.extend(["", "## Notes", ""])
            lines.extend(f"- {note}" for note in notes)
        lines.append("")
        return "\n".join(lines)

    def to_console_text(self) -> str:
        return "\n".join(
            [
                "IndustrialPlanner current surface health ready.",
                f"- release id: {self.release_id}",
                f"- base id: {self.base_id}",
                f"- delivery status: {self.delivery_status}",
                f"- exact full-scale CERTIFIED status: {self.exact_full_scale_certified_status}",
                f"- status: {self.status}",
                f"- checks: {self.checked_check_count}",
                f"- drift checks: {self.drift_check_count}",
                f"- helper-link checks: {self.helper_link_count}",
                f"- badge: {self.badge_text}",
                f"- json: {_display_repo_path(self.project_root, self.output_json_path)}",
                f"- markdown: {_display_repo_path(self.project_root, self.output_markdown_path)}",
                f"- console: {_display_repo_path(self.project_root, self.output_console_path)}",
            ]
        )


def build_single_base_delivery_surface_health(
    *,
    project_root: Path,
    surface_alignment_json_path: Path = _DEFAULT_SURFACE_ALIGNMENT_JSON,
    surface_alignment_markdown_path: Path = _DEFAULT_SURFACE_ALIGNMENT_MARKDOWN,
    surface_alignment_console_path: Path = _DEFAULT_SURFACE_ALIGNMENT_CONSOLE,
    output_json_path: Path = _DEFAULT_OUTPUT_JSON,
    output_markdown_path: Path = _DEFAULT_OUTPUT_MARKDOWN,
    output_console_path: Path = _DEFAULT_OUTPUT_CONSOLE,
) -> SingleBaseDeliverySurfaceHealthResult:
    try:
        project_root = Path(project_root).resolve()
        surface_alignment_json_path = _resolve_repo_path(project_root, surface_alignment_json_path)
        surface_alignment_markdown_path = _resolve_repo_path(project_root, surface_alignment_markdown_path)
        surface_alignment_console_path = _resolve_repo_path(project_root, surface_alignment_console_path)
        output_json_path = _resolve_output_path(project_root, output_json_path)
        output_markdown_path = _resolve_output_path(project_root, output_markdown_path)
        output_console_path = _resolve_output_path(project_root, output_console_path)

        if not surface_alignment_json_path.is_file():
            raise SingleBaseDeliverySurfaceHealthError(
                f"surface-alignment JSON summary is missing: {surface_alignment_json_path}"
            )
        if not surface_alignment_markdown_path.is_file():
            raise SingleBaseDeliverySurfaceHealthError(
                f"surface-alignment Markdown summary is missing: {surface_alignment_markdown_path}"
            )
        if not surface_alignment_console_path.is_file():
            raise SingleBaseDeliverySurfaceHealthError(
                f"surface-alignment console summary is missing: {surface_alignment_console_path}"
            )

        source_payload = load_json_mapping(surface_alignment_json_path)
        summary = _require_mapping(source_payload, "summary", surface_alignment_json_path)
        active_contract = _require_mapping(source_payload, "active_contract", surface_alignment_json_path)
        exact_payload = _require_mapping(source_payload, "exact_full_scale_certified", surface_alignment_json_path)
        checked_paths = _require_mapping(source_payload, "checked_paths", surface_alignment_json_path)

        result = SingleBaseDeliverySurfaceHealthResult(
            project_root=project_root,
            source_surface_alignment_json_path=surface_alignment_json_path,
            source_surface_alignment_markdown_path=surface_alignment_markdown_path,
            source_surface_alignment_console_path=surface_alignment_console_path,
            output_json_path=output_json_path,
            output_markdown_path=output_markdown_path,
            output_console_path=output_console_path,
            release_id=_require_string(active_contract, "release_id", context="active_contract"),
            base_id=_require_string(active_contract, "base_id", context="active_contract"),
            lot_size=_require_int(active_contract, "lot_size", context="active_contract"),
            delivery_status=_require_string(active_contract, "delivery_status", context="active_contract"),
            exact_full_scale_certified_status=normalize_non_authoritative_exact_status(
                _require_string(exact_payload, "status", context="exact_full_scale_certified"),
                context="surface_alignment.exact_full_scale_certified",
            ),
            status=_require_string(summary, "status", context="summary"),
            is_clean=bool(summary.get("is_clean")),
            checked_check_count=_require_int(summary, "checked_check_count", context="summary"),
            clean_check_count=_require_int(summary, "clean_check_count", context="summary"),
            drift_check_count=_require_int(summary, "drift_check_count", context="summary"),
            helper_link_count=_require_int(summary, "helper_link_count", context="summary"),
            helper_link_clean_count=_require_int(summary, "helper_link_clean_count", context="summary"),
        )
        if result.delivery_status != "ready_for_single_base_delivery":
            raise SingleBaseDeliverySurfaceHealthError(
                "current surface health requires ready_for_single_base_delivery in the active contract"
            )

        payload = result.to_payload(checked_paths=checked_paths)
        markdown = result.to_markdown(checked_paths=checked_paths)
        console = result.to_console_text()

        atomic_write_json(output_json_path, payload)
        _atomic_write_text(output_markdown_path, markdown)
        _atomic_write_text(output_console_path, console)
        return result
    except Exception as exc:
        if isinstance(exc, SingleBaseDeliverySurfaceHealthError):
            raise
        raise SingleBaseDeliverySurfaceHealthError(str(exc)) from exc


@dataclass(frozen=True)
class SingleBaseDeliverySurfaceHealthOutputs:
    json_output_path: Path
    markdown_output_path: Path
    console_output_path: Path


def write_single_base_delivery_surface_health_outputs(
    result: SingleBaseDeliverySurfaceHealthResult,
    *,
    checked_paths: Mapping[str, Any] | None = None,
    json_output_path: Path,
    markdown_output_path: Path,
    console_output_path: Path,
) -> SingleBaseDeliverySurfaceHealthOutputs:
    payload = result.to_payload(checked_paths=checked_paths)
    markdown = result.to_markdown(checked_paths=checked_paths)
    console = result.to_console_text()
    atomic_write_json(json_output_path, payload)
    _atomic_write_text(markdown_output_path, markdown)
    _atomic_write_text(console_output_path, console)
    return SingleBaseDeliverySurfaceHealthOutputs(
        json_output_path=json_output_path,
        markdown_output_path=markdown_output_path,
        console_output_path=console_output_path,
    )


def _resolve_repo_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()



def _resolve_output_path(project_root: Path, path: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return project_root / candidate



def _display_repo_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve())).replace(os.sep, "/")
    except ValueError:
        return str(path.resolve())



def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(path)



def _require_mapping(payload: Mapping[str, Any], key: str, path: Path) -> Mapping[str, Any]:
    value = _mapping(payload.get(key))
    if value:
        return value
    raise SingleBaseDeliverySurfaceHealthError(f"{path} does not contain a {key} mapping")



def _require_string(mapping: Mapping[str, Any], key: str, *, context: str) -> str:
    value = str(mapping.get(key, "")).strip()
    if value:
        return value
    raise SingleBaseDeliverySurfaceHealthError(f"{context} is missing {key}")



def _require_int(mapping: Mapping[str, Any], key: str, *, context: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool):
        raise SingleBaseDeliverySurfaceHealthError(f"{context} has invalid integer field {key}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SingleBaseDeliverySurfaceHealthError(f"{context} has invalid integer field {key}") from exc



def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}



def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
