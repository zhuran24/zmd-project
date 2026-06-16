"""Audit full-demand fixture support across the active IndustrialPlanner contract scope.

The checked-in active scope is intentionally narrowed to the single 70×70
`valley4_protocol_core` base. Other known bases are preserved as `future_scope`
metadata for later reactivation, but they are not audited in the active CI /
checked-in report set unless callers explicitly request a subset run.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_industrial_planner_full_demand_fixture import (  # noqa: E402
    FullDemandFixturePlanReport,
    FullDemandFixturePlanningError,
    plan_full_demand_recipe_capacity_fixture,
)
from scripts.industrial_planner_scope import (  # noqa: E402
    build_scope_metadata,
    default_active_base_ids,
)
from src.search.exact_campaign import atomic_write_json  # noqa: E402


_CANONICAL_RELATION_SMALLER = "smaller_than_canonical_contract"
_CANONICAL_RELATION_EQUAL = "equal_to_canonical_contract"
_CANONICAL_RELATION_LARGER = "larger_than_canonical_contract"
_BLOCKER_MANUFACTURING_AREA = "manufacturing_area_shortfall"
_BLOCKER_CONTRACT_CEILING = "canonical_contract_ceiling"
_BLOCKER_ROW_PACKING = "manufacturing_row_packing_shortfall"
_BLOCKER_INPUT_SLOTS = "boundary_input_slot_shortfall"
_BLOCKER_OUTPUT_SLOTS = "boundary_output_slot_shortfall"
_BLOCKER_OTHER = "other_or_unknown"


@dataclass(frozen=True)
class FullDemandBaseSupportEntry:
    base_id: str
    planner_status: str
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
    throughput_status: str | None = None
    validator_import_compatible: bool | None = None
    validator_layout_healthy: bool | None = None
    selected_input_slots: tuple[int, ...] = ()
    selected_output_edge_counts: tuple[tuple[str, int], ...] = ()
    validation_probe_count: int = 0
    blocking_classification: str | None = None
    error_message: str | None = None
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_id": self.base_id,
            "planner_status": self.planner_status,
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
            "throughput_status": self.throughput_status,
            "validator_import_compatible": self.validator_import_compatible,
            "validator_layout_healthy": self.validator_layout_healthy,
            "selected_input_slots": list(self.selected_input_slots),
            "selected_output_edge_counts": {
                edge: count for edge, count in self.selected_output_edge_counts
            },
            "validation_probe_count": self.validation_probe_count,
            "blocking_classification": self.blocking_classification,
            "error_message": self.error_message,
            "notes": list(self.notes),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class FullDemandBaseSupportMatrixReport:
    entries: tuple[FullDemandBaseSupportEntry, ...]
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
            "# IndustrialPlanner Full-Demand Base Support Matrix",
            "",
            str(self.scope.get("scope_statement", "")).strip(),
            "",
            f"- Audited base count: {self.summary.get('total_base_count', 0)}",
            f"- Audited bases: {audited_bases_text}",
            f"- Preserved future-scope bases (not audited here): {self.summary.get('future_scope_base_count', 0)}",
            f"- Future-scope groups: {future_scope_group_text}",
            f"- Proven-equivalent bases under the current contract: {self.summary.get('proven_equivalent_base_count', 0)}",
            f"- Infeasible bases: {self.summary.get('infeasible_base_count', 0)}",
            f"- Unsupported-by-contract bases: {self.summary.get('unsupported_by_canonical_contract_base_count', 0)}",
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
                "| Base | Size | Relation | Planner status | Throughput | Import/Layout | Manufacturing headroom | Boundary slots (out/in) | Blocker |",
                "|---|---:|---|---|---|---|---:|---:|---|",
            ]
        )
        for entry in self.entries:
            throughput = entry.throughput_status or "-"
            validator = (
                "-"
                if entry.validator_import_compatible is None or entry.validator_layout_healthy is None
                else f"{entry.validator_import_compatible}/{entry.validator_layout_healthy}"
            )
            blocker = entry.blocking_classification or "-"
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{entry.base_id}`",
                        str(entry.selected_base_placeable_size),
                        entry.size_relation_to_canonical,
                        f"`{entry.planner_status}`",
                        f"`{throughput}`",
                        validator,
                        str(entry.manufacturing_area_headroom_cells),
                        f"{entry.required_boundary_output_slots}/{entry.required_boundary_input_slots}",
                        blocker,
                    ]
                )
                + " |"
            )

        lines.extend(["", "## Per-base details", ""])
        for entry in self.entries:
            lines.append(f"### `{entry.base_id}`")
            lines.append("")
            lines.append(f"- Planner status: `{entry.planner_status}`")
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
            if entry.selected_input_slots:
                lines.append(
                    "- Selected input slots: "
                    + ", ".join(str(value) for value in entry.selected_input_slots)
                )
            if entry.selected_output_edge_counts:
                lines.append(
                    "- Selected output edge counts: "
                    + ", ".join(f"{edge}={count}" for edge, count in entry.selected_output_edge_counts)
                )
            if entry.throughput_status is not None:
                lines.append(f"- Final throughput status: `{entry.throughput_status}`")
            if entry.validator_import_compatible is not None and entry.validator_layout_healthy is not None:
                lines.append(
                    f"- Final validator import/layout: {entry.validator_import_compatible}/{entry.validator_layout_healthy}"
                )
            if entry.blocking_classification:
                lines.append(f"- Blocking classification: `{entry.blocking_classification}`")
            if entry.error_message:
                lines.append(f"- Error: {entry.error_message}")
            if entry.notes:
                lines.append("- Notes:")
                for note in entry.notes:
                    lines.append(f"  - {note}")
            if entry.warnings:
                lines.append("- Warnings:")
                for warning in entry.warnings:
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


def _size_relation(*, placeable_size: int, canonical_grid_size: int) -> str:
    if placeable_size < canonical_grid_size:
        return _CANONICAL_RELATION_SMALLER
    if placeable_size > canonical_grid_size:
        return _CANONICAL_RELATION_LARGER
    return _CANONICAL_RELATION_EQUAL


def _blocking_classification(report: FullDemandFixturePlanReport) -> str | None:
    if report.status == "proven_equivalent":
        return None
    message = (report.error_message or "").lower()
    if report.status == "unsupported_by_canonical_contract":
        return _BLOCKER_CONTRACT_CEILING
    if "required manufacturing area" in message:
        return _BLOCKER_MANUFACTURING_AREA
    if "deterministic manufacturing row packing" in message:
        return _BLOCKER_ROW_PACKING
    if "top-edge input slots" in message:
        return _BLOCKER_INPUT_SLOTS
    if "explicit output slots" in message:
        return _BLOCKER_OUTPUT_SLOTS
    return _BLOCKER_OTHER


def _entry_from_plan_report(report: FullDemandFixturePlanReport) -> FullDemandBaseSupportEntry:
    size_relation = _size_relation(
        placeable_size=report.selected_base_placeable_size,
        canonical_grid_size=report.canonical_grid_size,
    )
    lot_area_cells = int(report.selected_base_placeable_size * report.selected_base_placeable_size)
    headroom = int(lot_area_cells - report.required_recipe_area_cells)
    selected_output_edge_counts = tuple(
        (edge, len(positions)) for edge, positions in report.selected_output_slots_by_edge
    )
    return FullDemandBaseSupportEntry(
        base_id=report.base_id,
        planner_status=report.status,
        size_relation_to_canonical=size_relation,
        selected_base_placeable_size=report.selected_base_placeable_size,
        lot_area_cells=lot_area_cells,
        canonical_grid_size=report.canonical_grid_size,
        foundation_bus_edges=tuple(report.foundation_bus_edges),
        required_recipe_facility_count=report.required_recipe_facility_count,
        required_recipe_area_cells=report.required_recipe_area_cells,
        manufacturing_area_headroom_cells=headroom,
        required_boundary_output_slots=report.required_boundary_output_slots,
        required_boundary_input_slots=report.required_boundary_input_slots,
        throughput_status=report.throughput_status,
        validator_import_compatible=report.validator_import_compatible,
        validator_layout_healthy=report.validator_layout_healthy,
        selected_input_slots=tuple(report.selected_input_slots),
        selected_output_edge_counts=selected_output_edge_counts,
        validation_probe_count=report.validation_probe_count,
        blocking_classification=_blocking_classification(report),
        error_message=report.error_message,
        notes=tuple(report.notes),
        warnings=tuple(report.warnings),
    )


def _decision_signals(entries: Sequence[FullDemandBaseSupportEntry], *, include_future_scope: bool) -> tuple[str, ...]:
    planner_status_counts = Counter(entry.planner_status for entry in entries)
    blocker_counts = Counter(
        entry.blocking_classification
        for entry in entries
        if entry.blocking_classification is not None
    )
    signals: list[str] = []
    proven_count = int(planner_status_counts.get("proven_equivalent", 0))
    if proven_count:
        signals.append(
            f"{proven_count} audited base{'s' if proven_count != 1 else ''} already reach `proven_equivalent` under the current 70×70 canonical contract."
        )
    area_blocked_count = int(blocker_counts.get(_BLOCKER_MANUFACTURING_AREA, 0))
    if area_blocked_count:
        signals.append(
            f"{area_blocked_count} audited base{'s' if area_blocked_count != 1 else ''} are blocked by manufacturing-area shortfall before boundary geometry is even considered."
        )
    contract_blocked_entries = [
        entry for entry in entries if entry.blocking_classification == _BLOCKER_CONTRACT_CEILING
    ]
    if contract_blocked_entries:
        if len(contract_blocked_entries) == 1:
            base_id = contract_blocked_entries[0].base_id
            signals.append(
                f"`{base_id}` is currently the only audited base blocked purely by the canonical 70×70 edge contract on this strict matrix."
            )
        else:
            signals.append(
                f"{len(contract_blocked_entries)} audited bases are blocked purely by the canonical 70×70 edge contract on this strict matrix."
            )
    if include_future_scope:
        signals.append(
            "The checked-in matrix is intentionally narrowed to the active 70×70 single-base contract; preserved future-scope bases are recorded separately below instead of expanding the active audit surface."
        )
    return tuple(signals)


def build_full_demand_base_support_matrix(
    *,
    base_ids: Sequence[str] | None = None,
) -> FullDemandBaseSupportMatrixReport:
    include_future_scope = base_ids is None
    selected_base_ids = tuple(base_ids) if base_ids is not None else default_active_base_ids()
    entries: list[FullDemandBaseSupportEntry] = []
    for base_id in selected_base_ids:
        try:
            _, report = plan_full_demand_recipe_capacity_fixture(base_id=str(base_id))
        except FullDemandFixturePlanningError as exc:
            report = exc.report
        entries.append(_entry_from_plan_report(report))

    planner_status_counts = Counter(entry.planner_status for entry in entries)
    size_relation_counts = Counter(entry.size_relation_to_canonical for entry in entries)
    blocker_counts = Counter(
        entry.blocking_classification
        for entry in entries
        if entry.blocking_classification is not None
    )
    scope = build_scope_metadata(
        audited_base_ids=selected_base_ids,
        include_future_scope=include_future_scope,
    )
    summary = {
        "total_base_count": len(entries),
        "audited_base_ids": [entry.base_id for entry in entries],
        "future_scope_base_count": int(scope.get("future_scope_base_count", 0)),
        "future_scope_base_ids": list(scope.get("future_scope_base_ids", [])),
        "proven_equivalent_base_count": int(planner_status_counts.get("proven_equivalent", 0)),
        "proven_equivalent_base_ids": [
            entry.base_id for entry in entries if entry.planner_status == "proven_equivalent"
        ],
        "infeasible_base_count": int(planner_status_counts.get("infeasible", 0)),
        "infeasible_base_ids": [entry.base_id for entry in entries if entry.planner_status == "infeasible"],
        "unsupported_by_canonical_contract_base_count": int(
            planner_status_counts.get("unsupported_by_canonical_contract", 0)
        ),
        "unsupported_by_canonical_contract_base_ids": [
            entry.base_id
            for entry in entries
            if entry.planner_status == "unsupported_by_canonical_contract"
        ],
        "smaller_than_canonical_contract_base_count": int(
            size_relation_counts.get(_CANONICAL_RELATION_SMALLER, 0)
        ),
        "equal_to_canonical_contract_base_count": int(
            size_relation_counts.get(_CANONICAL_RELATION_EQUAL, 0)
        ),
        "larger_than_canonical_contract_base_count": int(
            size_relation_counts.get(_CANONICAL_RELATION_LARGER, 0)
        ),
        "blocking_classification_counts": {
            str(key): int(value)
            for key, value in sorted(blocker_counts.items())
        },
    }
    return FullDemandBaseSupportMatrixReport(
        entries=tuple(entries),
        summary=summary,
        decision_signals=_decision_signals(entries, include_future_scope=include_future_scope),
        scope=scope,
    )


def _write_optional_outputs(
    *,
    report: FullDemandBaseSupportMatrixReport,
    json_output: str | None,
    markdown_output: str | None,
) -> None:
    if json_output:
        atomic_write_json(Path(json_output), report.to_dict())
    if markdown_output:
        path = Path(markdown_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.to_markdown(), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit which IndustrialPlanner bases can host the current 70×70 "
            "full-demand recipe-capacity fixture without widening the canonical contract. "
            "Defaults to the active single-base `valley4_protocol_core` contract scope."
        )
    )
    parser.add_argument(
        "--base-id",
        action="append",
        dest="base_ids",
        default=None,
        help=(
            "Optional base id to audit. Repeat the flag to run an explicit subset instead of the default "
            "active single-base contract scope."
        ),
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional path for the JSON support-matrix report.",
    )
    parser.add_argument(
        "--markdown-output",
        default=None,
        help="Optional path for the Markdown support-matrix report.",
    )
    args = parser.parse_args()

    report = build_full_demand_base_support_matrix(base_ids=tuple(args.base_ids) if args.base_ids else None)
    _write_optional_outputs(
        report=report,
        json_output=args.json_output,
        markdown_output=args.markdown_output,
    )
    print(report.to_markdown())


if __name__ == "__main__":
    main()
