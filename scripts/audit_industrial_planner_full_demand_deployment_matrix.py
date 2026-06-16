"""Audit best-available full-demand support across canonical and preserved future-scope paths.

The checked-in active contract is the single 70×70 `valley4_protocol_core`
base. The additive outer-deployment path remains preserved as `future_scope`, so
this report defaults to a canonical-only best-path view while keeping the outer
column present as an explicitly inactive companion surface.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_industrial_planner_full_demand_base_matrix import (  # noqa: E402
    FullDemandBaseSupportEntry,
    FullDemandBaseSupportMatrixReport,
    build_full_demand_base_support_matrix,
)
from scripts.industrial_planner_scope import build_scope_metadata  # noqa: E402
from src.search.exact_campaign import atomic_write_json  # noqa: E402

_DEFAULT_BLUEPRINT = (
    PROJECT_ROOT
    / "data"
    / "examples"
    / "industrial_planner"
    / "full_demand_recipe_capacity_canonical_blueprint.json"
)
_CANONICAL_PATH_ID = "canonical_contract"
_OUTER_PATH_ID = "outer_deployment"
_NOT_APPLICABLE_STATUS = "not_applicable"
_NOT_APPLICABLE_REASON_SMALLER = "base_smaller_than_canonical_contract"
_OUTER_THROUGHPUT_SHORTFALL = "outer_path_throughput_shortfall"
_FUTURE_SCOPE_OUTER_PATH_STATUS = "future_scope"
_FUTURE_SCOPE_OUTER_PATH_REASON = "outer_deployment_deactivated_from_active_contract"


@dataclass(frozen=True)
class OuterPathSupportResult:
    applicable: bool
    path_status: str
    applicability_reason: str | None = None
    planning_status: str | None = None
    probe_status: str | None = None
    throughput_status: str | None = None
    validator_import_compatible: bool | None = None
    validator_layout_healthy: bool | None = None
    blocking_classification: str | None = None
    error_message: str | None = None
    inner_island_origin: tuple[int, int] | None = None
    boundary_assignment_count: int = 0
    connector_reservation_count: int = 0
    witness_reservation_count: int = 0
    export_mapping_count: int = 0
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "applicable": self.applicable,
            "path_status": self.path_status,
            "applicability_reason": self.applicability_reason,
            "planning_status": self.planning_status,
            "probe_status": self.probe_status,
            "throughput_status": self.throughput_status,
            "validator_import_compatible": self.validator_import_compatible,
            "validator_layout_healthy": self.validator_layout_healthy,
            "blocking_classification": self.blocking_classification,
            "error_message": self.error_message,
            "inner_island_origin": (
                None
                if self.inner_island_origin is None
                else {"x": int(self.inner_island_origin[0]), "y": int(self.inner_island_origin[1])}
            ),
            "boundary_assignment_count": self.boundary_assignment_count,
            "connector_reservation_count": self.connector_reservation_count,
            "witness_reservation_count": self.witness_reservation_count,
            "export_mapping_count": self.export_mapping_count,
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class FullDemandDeploymentPathEntry:
    base_id: str
    size_relation_to_canonical: str
    selected_base_placeable_size: int
    lot_area_cells: int
    canonical_grid_size: int
    foundation_bus_edges: tuple[str, ...]
    required_recipe_facility_count: int
    required_recipe_area_cells: int
    manufacturing_area_headroom_cells: int
    required_boundary_output_slots: int
    required_boundary_input_slots: int
    canonical_path: FullDemandBaseSupportEntry
    outer_path: OuterPathSupportResult
    best_available_path_id: str
    best_available_status: str
    best_available_throughput_status: str | None
    best_available_validator_import_compatible: bool | None
    best_available_validator_layout_healthy: bool | None
    best_available_blocking_classification: str | None
    unlocked_by_outer_path: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_id": self.base_id,
            "size_relation_to_canonical": self.size_relation_to_canonical,
            "selected_base_placeable_size": self.selected_base_placeable_size,
            "lot_area_cells": self.lot_area_cells,
            "canonical_grid_size": self.canonical_grid_size,
            "foundation_bus_edges": list(self.foundation_bus_edges),
            "required_recipe_facility_count": self.required_recipe_facility_count,
            "required_recipe_area_cells": self.required_recipe_area_cells,
            "manufacturing_area_headroom_cells": self.manufacturing_area_headroom_cells,
            "required_boundary_output_slots": self.required_boundary_output_slots,
            "required_boundary_input_slots": self.required_boundary_input_slots,
            "canonical_path": self.canonical_path.to_dict(),
            "outer_path": self.outer_path.to_dict(),
            "best_available_path_id": self.best_available_path_id,
            "best_available_status": self.best_available_status,
            "best_available_throughput_status": self.best_available_throughput_status,
            "best_available_validator_import_compatible": self.best_available_validator_import_compatible,
            "best_available_validator_layout_healthy": self.best_available_validator_layout_healthy,
            "best_available_blocking_classification": self.best_available_blocking_classification,
            "unlocked_by_outer_path": self.unlocked_by_outer_path,
        }


@dataclass(frozen=True)
class FullDemandDeploymentPathMatrixReport:
    entries: tuple[FullDemandDeploymentPathEntry, ...]
    summary: dict[str, Any]
    decision_signals: tuple[str, ...]
    scope: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": dict(self.summary),
            "scope": dict(self.scope),
            "decision_signals": list(self.decision_signals),
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def to_markdown(self) -> str:
        audited_base_ids = tuple(str(base_id) for base_id in self.summary.get("audited_base_ids", []))
        audited_bases_text = ", ".join(f"`{base_id}`" for base_id in audited_base_ids) or "(none)"
        future_scope_groups = tuple(self.scope.get("future_scope_base_groups", []))
        future_scope_group_text = (
            ", ".join(
                f"{group.get('label')} ({group.get('count')})"
                for group in future_scope_groups
            )
            if future_scope_groups
            else "(none)"
        )
        lines = [
            "# IndustrialPlanner Full-Demand Deployment Path Matrix",
            "",
            str(self.scope.get("scope_statement", "")).strip(),
            "",
            f"- Audited base count: {self.summary.get('total_base_count', 0)}",
            f"- Audited bases: {audited_bases_text}",
            f"- Preserved future-scope bases (not audited here): {self.summary.get('future_scope_base_count', 0)}",
            f"- Future-scope groups: {future_scope_group_text}",
            f"- Proven-equivalent bases under the strict 70×70 canonical contract: {self.summary.get('canonical_path_proven_equivalent_base_count', 0)}",
            f"- Additional bases unlocked by the adapter-side outer deployment path: {self.summary.get('additional_bases_unlocked_by_outer_path_base_count', 0)}",
            f"- Outer-path rows preserved as future-scope (not evaluated): {self.summary.get('future_scope_outer_path_base_count', 0)}",
            f"- Proven-equivalent bases under any active checked-in path: {self.summary.get('best_available_proven_equivalent_base_count', 0)}",
            f"- Smaller / equal / larger than the canonical 70×70 contract: "
            f"{self.summary.get('smaller_than_canonical_contract_base_count', 0)} / "
            f"{self.summary.get('equal_to_canonical_contract_base_count', 0)} / "
            f"{self.summary.get('larger_than_canonical_contract_base_count', 0)}",
        ]
        if self.decision_signals:
            lines.extend(["", "## Decision signals", ""])
            for signal in self.decision_signals:
                lines.append(f"- {signal}")

        lines.extend(
            [
                "",
                "## Active base matrix",
                "",
                "| Base | Size | Relation | Canonical path | Outer path | Best path | Best throughput | Best import/layout | Best blocker |",
                "|---|---:|---|---|---|---|---|---|---|",
            ]
        )
        for entry in self.entries:
            best_validator = (
                "-"
                if entry.best_available_validator_import_compatible is None
                or entry.best_available_validator_layout_healthy is None
                else f"{entry.best_available_validator_import_compatible}/{entry.best_available_validator_layout_healthy}"
            )
            best_blocker = entry.best_available_blocking_classification or "-"
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{entry.base_id}`",
                        str(entry.selected_base_placeable_size),
                        entry.size_relation_to_canonical,
                        f"`{entry.canonical_path.planner_status}`",
                        f"`{entry.outer_path.path_status}`",
                        f"`{entry.best_available_path_id}`",
                        f"`{entry.best_available_throughput_status or '-'}`",
                        best_validator,
                        best_blocker,
                    ]
                )
                + " |"
            )

        lines.extend(["", "## Per-base details", ""])
        for entry in self.entries:
            lines.append(f"### `{entry.base_id}`")
            lines.append("")
            lines.append(f"- Placeable size: {entry.selected_base_placeable_size}")
            lines.append(f"- Size relation: {entry.size_relation_to_canonical}")
            lines.append(
                f"- Foundation bus edges: {', '.join(entry.foundation_bus_edges) if entry.foundation_bus_edges else '(none)'}"
            )
            lines.append(
                f"- Manufacturing headroom cells: {entry.manufacturing_area_headroom_cells} "
                f"(required {entry.required_recipe_area_cells}, lot {entry.lot_area_cells})"
            )
            lines.append(
                f"- Required boundary slots: outputs {entry.required_boundary_output_slots}, inputs {entry.required_boundary_input_slots}"
            )
            lines.append(f"- Best available path: `{entry.best_available_path_id}`")
            lines.append(f"- Best available status: `{entry.best_available_status}`")
            if entry.best_available_throughput_status is not None:
                lines.append(f"- Best available throughput: `{entry.best_available_throughput_status}`")
            if (
                entry.best_available_validator_import_compatible is not None
                and entry.best_available_validator_layout_healthy is not None
            ):
                lines.append(
                    f"- Best available validator import/layout: "
                    f"{entry.best_available_validator_import_compatible}/{entry.best_available_validator_layout_healthy}"
                )
            if entry.best_available_blocking_classification:
                lines.append(f"- Best available blocker: `{entry.best_available_blocking_classification}`")
            if entry.unlocked_by_outer_path:
                lines.append("- Outer path unlock: yes")

            lines.extend(["", "#### Canonical 70×70 contract path", ""])
            canonical = entry.canonical_path
            lines.append(f"- Planner status: `{canonical.planner_status}`")
            if canonical.throughput_status is not None:
                lines.append(f"- Throughput status: `{canonical.throughput_status}`")
            if canonical.validator_import_compatible is not None and canonical.validator_layout_healthy is not None:
                lines.append(
                    f"- Validator import/layout: {canonical.validator_import_compatible}/{canonical.validator_layout_healthy}"
                )
            if canonical.blocking_classification:
                lines.append(f"- Blocker: `{canonical.blocking_classification}`")
            if canonical.error_message:
                lines.append(f"- Error: {canonical.error_message}")
            if canonical.notes:
                lines.append("- Notes:")
                for note in canonical.notes:
                    lines.append(f"  - {note}")
            if canonical.warnings:
                lines.append("- Warnings:")
                for warning in canonical.warnings:
                    lines.append(f"  - {warning}")

            lines.extend(["", "#### Companion outer-path column", ""])
            outer = entry.outer_path
            lines.append(f"- Path status: `{outer.path_status}`")
            if not outer.applicable:
                lines.append(f"- Applicability reason: `{outer.applicability_reason or '-'}`")
            else:
                if outer.planning_status is not None:
                    lines.append(f"- Planning status: `{outer.planning_status}`")
                if outer.probe_status is not None:
                    lines.append(f"- Probe status: `{outer.probe_status}`")
                if outer.inner_island_origin is not None:
                    lines.append(
                        f"- Inner island origin: ({outer.inner_island_origin[0]}, {outer.inner_island_origin[1]})"
                    )
                lines.append(f"- Boundary assignments: {outer.boundary_assignment_count}")
                lines.append(f"- Connector reservations: {outer.connector_reservation_count}")
                lines.append(f"- Witness reservations: {outer.witness_reservation_count}")
                lines.append(f"- Export mappings: {outer.export_mapping_count}")
                if outer.throughput_status is not None:
                    lines.append(f"- Throughput status: `{outer.throughput_status}`")
                if outer.validator_import_compatible is not None and outer.validator_layout_healthy is not None:
                    lines.append(
                        f"- Validator import/layout: {outer.validator_import_compatible}/{outer.validator_layout_healthy}"
                    )
                if outer.blocking_classification:
                    lines.append(f"- Blocker: `{outer.blocking_classification}`")
            if outer.error_message:
                lines.append(f"- Error: {outer.error_message}")
            if outer.notes:
                lines.append("- Notes:")
                for note in outer.notes:
                    lines.append(f"  - {note}")
            if outer.warnings:
                lines.append("- Warnings:")
                for warning in outer.warnings:
                    lines.append(f"  - {warning}")
            lines.append("")

        future_scope_bases = tuple(self.scope.get("future_scope_bases", []))
        if future_scope_bases:
            lines.extend(["## Preserved future-scope inventory", ""])
            if future_scope_groups:
                lines.extend(
                    [
                        "| Group | Bases | Size(s) | Note |",
                        "|---|---|---|---|",
                    ]
                )
                for group in future_scope_groups:
                    size_text = ", ".join(str(value) for value in group.get("placeable_sizes", [])) or "-"
                    base_ids = ", ".join(f"`{base_id}`" for base_id in group.get("base_ids", []))
                    lines.append(
                        "| "
                        + " | ".join(
                            [
                                str(group.get("label", "future_scope")),
                                base_ids,
                                size_text,
                                str(group.get("summary_note", "")),
                            ]
                        )
                        + " |"
                    )
                lines.append("")
            lines.append(
                "The detailed future-scope base inventory remains available in the JSON sidecar so dormant bases stay preserved without re-expanding the active Markdown decision surface."
            )
            lines.append("")
        return "\n".join(lines)


def _load_blueprint_payload(blueprint_path: Path) -> dict[str, Any]:
    return json.loads(blueprint_path.read_text(encoding="utf-8"))


def _outer_path_support_result(
    *,
    blueprint_payload: Mapping[str, Any],
    canonical_entry: FullDemandBaseSupportEntry,
    evaluate_future_scope_outer_path: bool,
) -> OuterPathSupportResult:
    if not evaluate_future_scope_outer_path:
        return OuterPathSupportResult(
            applicable=False,
            path_status=_FUTURE_SCOPE_OUTER_PATH_STATUS,
            applicability_reason=_FUTURE_SCOPE_OUTER_PATH_REASON,
            notes=(
                "outer deployment is preserved as future_scope and excluded from the active single-base contract / CI gate",
            ),
        )

    if canonical_entry.size_relation_to_canonical == "smaller_than_canonical_contract":
        return OuterPathSupportResult(
            applicable=False,
            path_status=_NOT_APPLICABLE_STATUS,
            applicability_reason=_NOT_APPLICABLE_REASON_SMALLER,
            notes=(
                "outer deployment is only meaningful for bases that can host the canonical 70×70 inner island; smaller bases remain blocked upstream on manufacturing area shortfall",
            ),
        )

    from src.adapters.base_planner.outer_deployment_plan import (  # noqa: WPS433,E402
        build_outer_base_deployment_plan,
    )
    from src.adapters.industrial_planner.export_blueprint import (  # noqa: WPS433,E402
        build_industrial_planner_export_bundle,
    )
    from src.adapters.industrial_planner.outer_export_probe import (  # noqa: WPS433,E402
        probe_outer_deployment_plan,
    )

    try:
        deployment_plan = build_outer_base_deployment_plan(
            blueprint_payload=blueprint_payload,
            base_id=canonical_entry.base_id,
            canonical_contract_size=canonical_entry.canonical_grid_size,
        )
        probe_bundle = probe_outer_deployment_plan(
            blueprint_payload=blueprint_payload,
            deployment_plan=deployment_plan,
        )
        export_bundle = build_industrial_planner_export_bundle(
            blueprint_payload=blueprint_payload,
            deployment_plan=deployment_plan,
        )
    except Exception as exc:  # pragma: no cover - fail-closed wrapper
        return OuterPathSupportResult(
            applicable=True,
            path_status="outer_path_error",
            blocking_classification="outer_path_error",
            error_message=str(exc),
        )

    validation_report = export_bundle["validation_report"]
    throughput_report = export_bundle["throughput_report"]
    throughput_status = str(throughput_report.get("status")) if throughput_report.get("status") is not None else None
    validator_import_compatible = bool(validation_report.get("is_import_compatible"))
    validator_layout_healthy = bool(validation_report.get("is_layout_healthy"))
    validator_clean = validator_import_compatible and validator_layout_healthy
    if validator_clean and throughput_status == "proven_equivalent":
        path_status = "proven_equivalent"
        blocker_classification = None
    elif validator_clean:
        path_status = throughput_status or str(probe_bundle.status)
        blocker_classification = _OUTER_THROUGHPUT_SHORTFALL
    else:
        path_status = str(probe_bundle.status)
        blocker_classification = probe_bundle.blocker_classification

    combined_warnings = tuple(
        sorted(
            {
                *deployment_plan.warnings,
                *probe_bundle.warnings,
                *(str(entry) for entry in export_bundle.get("warnings", ()) if str(entry).strip()),
            }
        )
    )
    return OuterPathSupportResult(
        applicable=True,
        path_status=path_status,
        planning_status=deployment_plan.planning_status,
        probe_status=str(probe_bundle.status),
        throughput_status=throughput_status,
        validator_import_compatible=validator_import_compatible,
        validator_layout_healthy=validator_layout_healthy,
        blocking_classification=blocker_classification,
        error_message=probe_bundle.error_message,
        inner_island_origin=(deployment_plan.inner_island_origin.x, deployment_plan.inner_island_origin.y),
        boundary_assignment_count=len(deployment_plan.boundary_assignments),
        connector_reservation_count=len(deployment_plan.connector_reservations),
        witness_reservation_count=len(deployment_plan.witness_reservations),
        export_mapping_count=len(deployment_plan.export_mappings),
        notes=deployment_plan.notes,
        warnings=combined_warnings,
    )


def _select_best_available_path(
    *,
    canonical_entry: FullDemandBaseSupportEntry,
    outer_path: OuterPathSupportResult,
) -> tuple[str, str, str | None, bool | None, bool | None, str | None]:
    if canonical_entry.planner_status == "proven_equivalent":
        return (
            _CANONICAL_PATH_ID,
            canonical_entry.planner_status,
            canonical_entry.throughput_status,
            canonical_entry.validator_import_compatible,
            canonical_entry.validator_layout_healthy,
            canonical_entry.blocking_classification,
        )
    if outer_path.applicable and outer_path.path_status == "proven_equivalent":
        return (
            _OUTER_PATH_ID,
            outer_path.path_status,
            outer_path.throughput_status,
            outer_path.validator_import_compatible,
            outer_path.validator_layout_healthy,
            outer_path.blocking_classification,
        )
    if outer_path.applicable and canonical_entry.planner_status == "unsupported_by_canonical_contract":
        return (
            _OUTER_PATH_ID,
            outer_path.path_status,
            outer_path.throughput_status,
            outer_path.validator_import_compatible,
            outer_path.validator_layout_healthy,
            outer_path.blocking_classification,
        )
    return (
        _CANONICAL_PATH_ID,
        canonical_entry.planner_status,
        canonical_entry.throughput_status,
        canonical_entry.validator_import_compatible,
        canonical_entry.validator_layout_healthy,
        canonical_entry.blocking_classification,
    )


def _decision_signals(entries: Sequence[FullDemandDeploymentPathEntry], summary: Mapping[str, Any]) -> tuple[str, ...]:
    unlocked_entries = [entry for entry in entries if entry.unlocked_by_outer_path]
    total_proven = int(summary.get("best_available_proven_equivalent_base_count", 0))
    canonical_proven = int(summary.get("canonical_path_proven_equivalent_base_count", 0))
    unlocked_count = int(summary.get("additional_bases_unlocked_by_outer_path_base_count", 0))
    future_scope_outer_count = int(summary.get("future_scope_outer_path_base_count", 0))
    shortfall_count = int(summary.get("manufacturing_area_shortfall_base_count", 0))
    base_word_total = "base" if total_proven == 1 else "bases"
    base_word_unlocked = "base" if unlocked_count == 1 else "bases"
    base_word_shortfall = "base" if shortfall_count == 1 else "bases"
    signals: list[str] = [
        (
            f"{total_proven} audited {base_word_total} now reach `proven_equivalent` under active checked-in paths: "
            f"{canonical_proven} on the strict 70×70 canonical contract and "
            f"{unlocked_count} additional {base_word_unlocked} via evaluated outer deployment."
        ),
        (
            f"{shortfall_count} audited {base_word_shortfall} remain blocked by manufacturing-area shortfall before "
            "boundary representation is even considered."
        ),
        (
            "This deployment-path report stays postprocess-only: it preserves the companion outer-path column without widening canonical truth, campaign schema, or certified evidence."
        ),
    ]
    if future_scope_outer_count:
        signals.insert(
            1,
            f"The companion outer-path column is currently preserved as `future_scope` for {future_scope_outer_count} audited base{'s' if future_scope_outer_count != 1 else ''}; active checked-in status therefore stays canonical-only.",
        )
    if unlocked_entries:
        base_ids = ", ".join(f"`{entry.base_id}`" for entry in unlocked_entries)
        plural = "is" if len(unlocked_entries) == 1 else "are"
        signals.insert(
            1,
            f"{base_ids} {plural} unsupported on the canonical-only matrix, but the best available checked-in path is `outer_deployment` with validator-clean translated `proven_equivalent`.",
        )
    return tuple(signals)


def build_full_demand_deployment_path_matrix(
    *,
    base_ids: Sequence[str] | None = None,
    blueprint_path: Path = _DEFAULT_BLUEPRINT,
    canonical_report: FullDemandBaseSupportMatrixReport | None = None,
    evaluate_future_scope_outer_path: bool = False,
) -> FullDemandDeploymentPathMatrixReport:
    if canonical_report is None:
        canonical_report = build_full_demand_base_support_matrix(base_ids=base_ids)
    elif base_ids is not None:
        expected_base_ids = tuple(str(base_id) for base_id in base_ids)
        actual_base_ids = tuple(entry.base_id for entry in canonical_report.entries)
        if actual_base_ids != expected_base_ids:
            raise ValueError(
                "provided canonical_report does not match the requested base_ids order for the deployment-path audit"
            )
    blueprint_payload = _load_blueprint_payload(blueprint_path)

    entries: list[FullDemandDeploymentPathEntry] = []
    best_available_path_counts: Counter[str] = Counter()
    best_available_blocking_counts: Counter[str] = Counter()
    manufacturing_area_shortfall_count = 0
    additional_unlocked_count = 0
    future_scope_outer_path_count = 0

    for canonical_entry in canonical_report.entries:
        outer_path = _outer_path_support_result(
            blueprint_payload=blueprint_payload,
            canonical_entry=canonical_entry,
            evaluate_future_scope_outer_path=evaluate_future_scope_outer_path,
        )
        (
            best_available_path_id,
            best_available_status,
            best_available_throughput_status,
            best_available_validator_import_compatible,
            best_available_validator_layout_healthy,
            best_available_blocking_classification,
        ) = _select_best_available_path(
            canonical_entry=canonical_entry,
            outer_path=outer_path,
        )
        unlocked_by_outer_path = (
            canonical_entry.planner_status != "proven_equivalent"
            and outer_path.path_status == "proven_equivalent"
            and best_available_path_id == _OUTER_PATH_ID
        )
        if unlocked_by_outer_path:
            additional_unlocked_count += 1
        if outer_path.path_status == _FUTURE_SCOPE_OUTER_PATH_STATUS:
            future_scope_outer_path_count += 1
        if best_available_blocking_classification == "manufacturing_area_shortfall":
            manufacturing_area_shortfall_count += 1
        if best_available_blocking_classification is not None:
            best_available_blocking_counts[best_available_blocking_classification] += 1
        best_available_path_counts[best_available_path_id] += 1
        entries.append(
            FullDemandDeploymentPathEntry(
                base_id=canonical_entry.base_id,
                size_relation_to_canonical=canonical_entry.size_relation_to_canonical,
                selected_base_placeable_size=canonical_entry.selected_base_placeable_size,
                lot_area_cells=canonical_entry.lot_area_cells,
                canonical_grid_size=canonical_entry.canonical_grid_size,
                foundation_bus_edges=canonical_entry.foundation_bus_edges,
                required_recipe_facility_count=canonical_entry.required_recipe_facility_count,
                required_recipe_area_cells=canonical_entry.required_recipe_area_cells,
                manufacturing_area_headroom_cells=canonical_entry.manufacturing_area_headroom_cells,
                required_boundary_output_slots=canonical_entry.required_boundary_output_slots,
                required_boundary_input_slots=canonical_entry.required_boundary_input_slots,
                canonical_path=canonical_entry,
                outer_path=outer_path,
                best_available_path_id=best_available_path_id,
                best_available_status=best_available_status,
                best_available_throughput_status=best_available_throughput_status,
                best_available_validator_import_compatible=best_available_validator_import_compatible,
                best_available_validator_layout_healthy=best_available_validator_layout_healthy,
                best_available_blocking_classification=best_available_blocking_classification,
                unlocked_by_outer_path=unlocked_by_outer_path,
            )
        )

    scope = build_scope_metadata(
        audited_base_ids=canonical_report.summary.get("audited_base_ids", []),
        include_future_scope=bool(canonical_report.scope.get("future_scope_base_ids", [])),
    )
    summary = {
        "total_base_count": len(entries),
        "audited_base_ids": [entry.base_id for entry in entries],
        "future_scope_base_count": int(scope.get("future_scope_base_count", 0)),
        "future_scope_base_ids": list(scope.get("future_scope_base_ids", [])),
        "canonical_path_proven_equivalent_base_count": sum(
            1 for entry in entries if entry.canonical_path.planner_status == "proven_equivalent"
        ),
        "canonical_path_proven_equivalent_base_ids": [
            entry.base_id for entry in entries if entry.canonical_path.planner_status == "proven_equivalent"
        ],
        "best_available_proven_equivalent_base_count": sum(
            1 for entry in entries if entry.best_available_status == "proven_equivalent"
        ),
        "best_available_proven_equivalent_base_ids": [
            entry.base_id for entry in entries if entry.best_available_status == "proven_equivalent"
        ],
        "additional_bases_unlocked_by_outer_path_base_count": additional_unlocked_count,
        "additional_bases_unlocked_by_outer_path_base_ids": [
            entry.base_id for entry in entries if entry.unlocked_by_outer_path
        ],
        "best_available_canonical_contract_ceiling_base_count": sum(
            1 for entry in entries if entry.best_available_blocking_classification == "canonical_contract_ceiling"
        ),
        "best_available_canonical_contract_ceiling_base_ids": [
            entry.base_id
            for entry in entries
            if entry.best_available_blocking_classification == "canonical_contract_ceiling"
        ],
        "outer_path_attempted_base_count": sum(1 for entry in entries if entry.outer_path.applicable),
        "outer_path_not_applicable_base_count": sum(1 for entry in entries if not entry.outer_path.applicable),
        "future_scope_outer_path_base_count": future_scope_outer_path_count,
        "smaller_than_canonical_contract_base_count": canonical_report.summary.get(
            "smaller_than_canonical_contract_base_count", 0
        ),
        "equal_to_canonical_contract_base_count": canonical_report.summary.get(
            "equal_to_canonical_contract_base_count", 0
        ),
        "larger_than_canonical_contract_base_count": canonical_report.summary.get(
            "larger_than_canonical_contract_base_count", 0
        ),
        "manufacturing_area_shortfall_base_count": manufacturing_area_shortfall_count,
        "best_available_path_counts": dict(sorted(best_available_path_counts.items())),
        "best_available_blocking_classification_counts": dict(sorted(best_available_blocking_counts.items())),
    }
    return FullDemandDeploymentPathMatrixReport(
        entries=tuple(entries),
        summary=summary,
        decision_signals=_decision_signals(entries, summary),
        scope=scope,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the checked-in full-demand IndustrialPlanner fixture across the strict canonical path "
            "and the preserved companion outer-path column. Defaults to the active single-base contract scope, "
            "with future-scope outer deployment left inactive."
        )
    )
    parser.add_argument(
        "--base-id",
        dest="base_ids",
        action="append",
        default=None,
        help="Optional base id to audit. Repeat the flag to restrict the matrix to an explicit subset.",
    )
    parser.add_argument(
        "--blueprint",
        default=str(_DEFAULT_BLUEPRINT),
        help="Canonical full-demand blueprint used for the companion deployment-path audit.",
    )
    parser.add_argument(
        "--evaluate-future-scope-outer-path",
        action="store_true",
        help="Future-scope/debug option: actually evaluate the preserved outer-deployment path instead of leaving it inactive.",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional path for the JSON deployment-path report.",
    )
    parser.add_argument(
        "--markdown-output",
        default=None,
        help="Optional path for the Markdown deployment-path report.",
    )
    args = parser.parse_args()

    report = build_full_demand_deployment_path_matrix(
        base_ids=tuple(args.base_ids) if args.base_ids else None,
        blueprint_path=Path(args.blueprint),
        evaluate_future_scope_outer_path=bool(args.evaluate_future_scope_outer_path),
    )
    if args.json_output:
        atomic_write_json(Path(args.json_output), report.to_dict())
    if args.markdown_output:
        output_path = Path(args.markdown_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report.to_markdown(), encoding="utf-8")
    if not args.json_output and not args.markdown_output:
        print(report.to_markdown())


if __name__ == "__main__":
    main()
