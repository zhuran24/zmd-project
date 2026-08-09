"""Run the active full-demand IndustrialPlanner support audits in one deterministic pass.

The checked-in support suite is intentionally narrowed to the single 70×70
`valley4_protocol_core` contract. The companion deployment-path view is still
regenerated so the preserved future-scope metadata stays coherent, but the outer
path remains inactive unless a caller explicitly opts into future-scope
inspection.
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
    FullDemandBaseSupportMatrixReport,
    build_full_demand_base_support_matrix,
)
from scripts.audit_industrial_planner_full_demand_deployment_matrix import (  # noqa: E402
    FullDemandDeploymentPathMatrixReport,
    build_full_demand_deployment_path_matrix,
)
from src.search.exact_campaign import atomic_write_json  # noqa: E402

_DEFAULT_BLUEPRINT = (
    PROJECT_ROOT
    / "data"
    / "examples"
    / "industrial_planner"
    / "full_demand_recipe_capacity_canonical_blueprint.json"
)
_DEFAULT_OUTPUT_DIR = _DEFAULT_BLUEPRINT.parent

_BASE_MATRIX_JSON_NAME = "full_demand_base_support_matrix.json"
_BASE_MATRIX_MARKDOWN_NAME = "full_demand_base_support_matrix.md"
_DEPLOYMENT_MATRIX_JSON_NAME = "full_demand_deployment_path_matrix.json"
_DEPLOYMENT_MATRIX_MARKDOWN_NAME = "full_demand_deployment_path_matrix.md"
_OVERVIEW_JSON_NAME = "full_demand_support_overview.json"
_OVERVIEW_MARKDOWN_NAME = "full_demand_support_overview.md"
_UNCHANGED_TRANSITION = "unchanged"


@dataclass(frozen=True)
class FullDemandSupportOverviewEntry:
    base_id: str
    selected_base_placeable_size: int
    size_relation_to_canonical: str
    canonical_status: str
    canonical_blocking_classification: str | None
    outer_path_applicable: bool
    outer_path_status: str
    best_available_path_id: str
    best_available_status: str
    best_available_blocking_classification: str | None
    unlocked_by_outer_path: bool
    status_transition: str
    canonical_validator_import_compatible: bool | None = None
    canonical_validator_layout_healthy: bool | None = None
    best_available_validator_import_compatible: bool | None = None
    best_available_validator_layout_healthy: bool | None = None
    canonical_throughput_status: str | None = None
    best_available_throughput_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_id": self.base_id,
            "selected_base_placeable_size": self.selected_base_placeable_size,
            "size_relation_to_canonical": self.size_relation_to_canonical,
            "canonical_status": self.canonical_status,
            "canonical_blocking_classification": self.canonical_blocking_classification,
            "outer_path_applicable": self.outer_path_applicable,
            "outer_path_status": self.outer_path_status,
            "best_available_path_id": self.best_available_path_id,
            "best_available_status": self.best_available_status,
            "best_available_blocking_classification": self.best_available_blocking_classification,
            "unlocked_by_outer_path": self.unlocked_by_outer_path,
            "status_transition": self.status_transition,
            "canonical_validator_import_compatible": self.canonical_validator_import_compatible,
            "canonical_validator_layout_healthy": self.canonical_validator_layout_healthy,
            "best_available_validator_import_compatible": self.best_available_validator_import_compatible,
            "best_available_validator_layout_healthy": self.best_available_validator_layout_healthy,
            "canonical_throughput_status": self.canonical_throughput_status,
            "best_available_throughput_status": self.best_available_throughput_status,
        }


@dataclass(frozen=True)
class FullDemandSupportOverviewReport:
    canonical_report: FullDemandBaseSupportMatrixReport
    deployment_report: FullDemandDeploymentPathMatrixReport
    entries: tuple[FullDemandSupportOverviewEntry, ...]
    summary: dict[str, Any]
    decision_signals: tuple[str, ...]
    scope: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": dict(self.summary),
            "scope": dict(self.scope),
            "decision_signals": list(self.decision_signals),
            "component_report_filenames": {
                "canonical_matrix_json": _BASE_MATRIX_JSON_NAME,
                "canonical_matrix_markdown": _BASE_MATRIX_MARKDOWN_NAME,
                "deployment_path_matrix_json": _DEPLOYMENT_MATRIX_JSON_NAME,
                "deployment_path_matrix_markdown": _DEPLOYMENT_MATRIX_MARKDOWN_NAME,
            },
            "canonical_matrix_summary": dict(self.canonical_report.summary),
            "deployment_path_matrix_summary": dict(self.deployment_report.summary),
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
            "# IndustrialPlanner Full-Demand Support Overview",
            "",
            str(self.scope.get("scope_statement", "")).strip(),
            "",
            "This overview regenerates the strict canonical base matrix and the companion deployment-path matrix together while keeping the active checked-in decision surface aligned to the single 70×70 `valley4_protocol_core` contract.",
            "",
            f"- Total bases audited: {self.summary.get('total_base_count', 0)}",
            f"- Audited bases: {audited_bases_text}",
            f"- Preserved future-scope bases (not audited here): {self.summary.get('future_scope_base_count', 0)}",
            f"- Future-scope groups: {future_scope_group_text}",
            f"- Proven-equivalent bases on the strict canonical path: {self.summary.get('canonical_path_proven_equivalent_base_count', 0)}",
            f"- Proven-equivalent bases on the best available active checked-in path: {self.summary.get('best_available_proven_equivalent_base_count', 0)}",
            f"- Additional bases unlocked by the active checked-in path: {self.summary.get('additional_bases_unlocked_by_outer_path_base_count', 0)}",
            f"- Bases whose active checked-in status changes across the two reports: {self.summary.get('status_transition_base_count', 0)}",
            f"- Outer-path rows preserved as future-scope (not evaluated): {self.summary.get('future_scope_outer_path_base_count', 0)}",
            f"- Canonical-contract ceiling count, strict vs best available active path: {self.summary.get('canonical_contract_ceiling_base_count', 0)} -> {self.summary.get('best_available_canonical_contract_ceiling_base_count', 0)}",
            f"- Manufacturing-area shortfall bases (unchanged upstream blocker): {self.summary.get('manufacturing_area_shortfall_base_count', 0)}",
            "",
            "## Companion reports",
            "",
            f"- `{_BASE_MATRIX_JSON_NAME}` / `{_BASE_MATRIX_MARKDOWN_NAME}` — strict 70×70 canonical-only matrix for the active contract.",
            f"- `{_DEPLOYMENT_MATRIX_JSON_NAME}` / `{_DEPLOYMENT_MATRIX_MARKDOWN_NAME}` — companion deployment matrix that preserves future-scope outer-path metadata without activating it by default.",
        ]
        if self.decision_signals:
            lines.extend(["", "## Decision signals", ""])
            for signal in self.decision_signals:
                lines.append(f"- {signal}")

        lines.extend(
            [
                "",
                "## Active cross-view status table",
                "",
                "| Base | Size | Relation | Canonical status | Outer path | Best path | Best status | Transition | Best blocker |",
                "|---|---:|---|---|---|---|---|---|---|",
            ]
        )
        for entry in self.entries:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{entry.base_id}`",
                        str(entry.selected_base_placeable_size),
                        entry.size_relation_to_canonical,
                        f"`{entry.canonical_status}`",
                        f"`{entry.outer_path_status}`",
                        f"`{entry.best_available_path_id}`",
                        f"`{entry.best_available_status}`",
                        f"`{entry.status_transition}`",
                        entry.best_available_blocking_classification or "-",
                    ]
                )
                + " |"
            )

        changed_entries = [entry for entry in self.entries if entry.status_transition != _UNCHANGED_TRANSITION]
        if changed_entries:
            lines.extend(["", "## Status transitions", ""])
            for entry in changed_entries:
                lines.append(f"### `{entry.base_id}`")
                lines.append("")
                lines.append(f"- Canonical status: `{entry.canonical_status}`")
                lines.append(f"- Outer path status: `{entry.outer_path_status}`")
                lines.append(f"- Best available path: `{entry.best_available_path_id}`")
                lines.append(f"- Transition: `{entry.status_transition}`")
                if entry.best_available_throughput_status is not None:
                    lines.append(f"- Best available throughput: `{entry.best_available_throughput_status}`")
                if (
                    entry.best_available_validator_import_compatible is not None
                    and entry.best_available_validator_layout_healthy is not None
                ):
                    lines.append(
                        "- Best available validator import/layout: "
                        f"{entry.best_available_validator_import_compatible}/{entry.best_available_validator_layout_healthy}"
                    )
                if entry.best_available_blocking_classification:
                    lines.append(f"- Best available blocker: `{entry.best_available_blocking_classification}`")
                if entry.unlocked_by_outer_path:
                    lines.append("- Outer-path unlock: yes")
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


@dataclass(frozen=True)
class FullDemandSupportSuiteDriftEntry:
    filename: str
    drift_kind: str


@dataclass(frozen=True)
class FullDemandSupportSuiteCheckResult:
    output_dir: Path
    checked_file_count: int
    drift_entries: tuple[FullDemandSupportSuiteDriftEntry, ...] = ()

    @property
    def is_clean(self) -> bool:
        return not self.drift_entries

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": str(self.output_dir),
            "checked_file_count": self.checked_file_count,
            "is_clean": self.is_clean,
            "drift_entries": [
                {"filename": entry.filename, "drift_kind": entry.drift_kind}
                for entry in self.drift_entries
            ],
        }

    def to_markdown(self) -> str:
        lines = [
            "# IndustrialPlanner Full-Demand Support Suite Check",
            "",
            f"- Output directory: `{self.output_dir}`",
            f"- Files checked: {self.checked_file_count}",
            f"- Check status: `{'clean' if self.is_clean else 'drift_detected'}`",
        ]
        if self.drift_entries:
            lines.extend(["", "## Drift entries", ""])
            for entry in self.drift_entries:
                lines.append(f"- `{entry.drift_kind}`: `{entry.filename}`")
        return "\n".join(lines)

    def to_console_text(self) -> str:
        if self.is_clean:
            return (
                f"full-demand support suite is in sync under {self.output_dir} "
                f"({self.checked_file_count} files checked)"
            )

        lines = [
            (
                f"full-demand support suite drift detected under {self.output_dir}: "
                f"{len(self.drift_entries)} of {self.checked_file_count} files need refresh"
            )
        ]
        for drift_entry in self.drift_entries:
            lines.append(f"- {drift_entry.drift_kind}: {drift_entry.filename}")
        lines.append(
            "regenerate with: "
            f"python scripts/audit_industrial_planner_full_demand_support_suite.py --output-dir {self.output_dir}"
        )
        return "\n".join(lines)


def _status_transition(*, canonical_status: str, best_available_status: str) -> str:
    if canonical_status == best_available_status:
        return _UNCHANGED_TRANSITION
    return f"{canonical_status} -> {best_available_status}"


def _decision_signals(
    *,
    entries: Sequence[FullDemandSupportOverviewEntry],
    summary: Mapping[str, Any],
    scope: Mapping[str, Any],
) -> tuple[str, ...]:
    canonical_proven = int(summary.get("canonical_path_proven_equivalent_base_count", 0))
    best_available_proven = int(summary.get("best_available_proven_equivalent_base_count", 0))
    unlocked_count = int(summary.get("additional_bases_unlocked_by_outer_path_base_count", 0))
    changed_entries = [entry for entry in entries if entry.status_transition != _UNCHANGED_TRANSITION]
    shortfall_count = int(summary.get("manufacturing_area_shortfall_base_count", 0))
    future_scope_outer_count = int(summary.get("future_scope_outer_path_base_count", 0))
    future_scope_base_count = int(scope.get("future_scope_base_count", 0))
    signals: list[str] = [
        (
            f"The active checked-in support suite is intentionally narrowed to {len(summary.get('audited_base_ids', []))} audited base"
            f"{'s' if int(summary.get('total_base_count', 0)) != 1 else ''} under the single 70×70 contract, while {future_scope_base_count} preserved base"
            f"{'s' if future_scope_base_count != 1 else ''} remain outside the active audit / CI surface."
        ),
        (
            f"The strict canonical matrix records {canonical_proven} active `proven_equivalent` base"
            f"{'s' if canonical_proven != 1 else ''}, and the best available active checked-in path records {best_available_proven}."
        ),
        (
            f"{shortfall_count} active audited base{'s' if shortfall_count != 1 else ''} remain blocked by manufacturing-area shortfall before boundary representation is even considered."
        ),
        (
            "This umbrella workflow stays postprocess-only: it writes companion strict/deployment summaries together without widening canonical truth, campaign schema, or certified evidence."
        ),
    ]
    if future_scope_outer_count:
        signals.insert(
            2,
            f"The companion deployment column is currently preserved as `future_scope` for {future_scope_outer_count} audited base{'s' if future_scope_outer_count != 1 else ''}, so the active checked-in best-path view stays canonical-only.",
        )
    if changed_entries:
        changed_descriptions = ", ".join(
            f"`{entry.base_id}` ({entry.status_transition} via `{entry.best_available_path_id}`)"
            for entry in changed_entries
        )
        signals.insert(2, f"Current active checked-in status transitions: {changed_descriptions}.")
    elif unlocked_count == 0:
        signals.insert(
            2,
            "No active checked-in status transitions remain after the out-of-scope outer deployment path is frozen as future_scope.",
        )
    return tuple(signals)


def build_full_demand_support_overview(
    *,
    base_ids: Sequence[str] | None = None,
    blueprint_path: Path = _DEFAULT_BLUEPRINT,
    evaluate_future_scope_outer_path: bool = False,
) -> FullDemandSupportOverviewReport:
    canonical_report = build_full_demand_base_support_matrix(base_ids=base_ids)
    deployment_report = build_full_demand_deployment_path_matrix(
        base_ids=base_ids,
        blueprint_path=blueprint_path,
        canonical_report=canonical_report,
        evaluate_future_scope_outer_path=evaluate_future_scope_outer_path,
    )

    deployment_entries_by_base = {entry.base_id: entry for entry in deployment_report.entries}
    entries: list[FullDemandSupportOverviewEntry] = []
    transition_counts: Counter[str] = Counter()

    for canonical_entry in canonical_report.entries:
        deployment_entry = deployment_entries_by_base[canonical_entry.base_id]
        transition = _status_transition(
            canonical_status=canonical_entry.planner_status,
            best_available_status=deployment_entry.best_available_status,
        )
        if transition != _UNCHANGED_TRANSITION:
            transition_counts[transition] += 1
        entries.append(
            FullDemandSupportOverviewEntry(
                base_id=canonical_entry.base_id,
                selected_base_placeable_size=canonical_entry.selected_base_placeable_size,
                size_relation_to_canonical=canonical_entry.size_relation_to_canonical,
                canonical_status=canonical_entry.planner_status,
                canonical_blocking_classification=canonical_entry.blocking_classification,
                outer_path_applicable=deployment_entry.outer_path.applicable,
                outer_path_status=deployment_entry.outer_path.path_status,
                best_available_path_id=deployment_entry.best_available_path_id,
                best_available_status=deployment_entry.best_available_status,
                best_available_blocking_classification=deployment_entry.best_available_blocking_classification,
                unlocked_by_outer_path=deployment_entry.unlocked_by_outer_path,
                status_transition=transition,
                canonical_validator_import_compatible=canonical_entry.validator_import_compatible,
                canonical_validator_layout_healthy=canonical_entry.validator_layout_healthy,
                best_available_validator_import_compatible=deployment_entry.best_available_validator_import_compatible,
                best_available_validator_layout_healthy=deployment_entry.best_available_validator_layout_healthy,
                canonical_throughput_status=canonical_entry.throughput_status,
                best_available_throughput_status=deployment_entry.best_available_throughput_status,
            )
        )

    scope = dict(canonical_report.scope)
    summary = {
        "total_base_count": len(entries),
        "scope_mode": scope.get("scope_mode"),
        "audited_base_ids": [entry.base_id for entry in entries],
        "future_scope_base_count": int(scope.get("future_scope_base_count", 0)),
        "future_scope_base_ids": list(scope.get("future_scope_base_ids", [])),
        "canonical_path_proven_equivalent_base_count": canonical_report.summary.get(
            "proven_equivalent_base_count", 0
        ),
        "canonical_path_proven_equivalent_base_ids": [
            entry.base_id for entry in entries if entry.canonical_status == "proven_equivalent"
        ],
        "best_available_proven_equivalent_base_count": deployment_report.summary.get(
            "best_available_proven_equivalent_base_count", 0
        ),
        "best_available_proven_equivalent_base_ids": [
            entry.base_id for entry in entries if entry.best_available_status == "proven_equivalent"
        ],
        "additional_bases_unlocked_by_outer_path_base_count": deployment_report.summary.get(
            "additional_bases_unlocked_by_outer_path_base_count", 0
        ),
        "additional_bases_unlocked_by_outer_path_base_ids": [
            entry.base_id for entry in entries if entry.unlocked_by_outer_path
        ],
        "status_transition_base_count": sum(transition_counts.values()),
        "status_transition_base_ids": [
            entry.base_id for entry in entries if entry.status_transition != _UNCHANGED_TRANSITION
        ],
        "canonical_contract_ceiling_base_count": canonical_report.summary.get(
            "unsupported_by_canonical_contract_base_count", 0
        ),
        "best_available_canonical_contract_ceiling_base_count": deployment_report.summary.get(
            "best_available_canonical_contract_ceiling_base_count", 0
        ),
        "manufacturing_area_shortfall_base_count": deployment_report.summary.get(
            "manufacturing_area_shortfall_base_count", 0
        ),
        "status_transition_counts": {
            str(key): int(value)
            for key, value in sorted(transition_counts.items())
        },
        "best_available_path_counts": dict(
            sorted(
                (str(key), int(value))
                for key, value in deployment_report.summary.get("best_available_path_counts", {}).items()
            )
        ),
        "unlocked_base_ids": [entry.base_id for entry in entries if entry.unlocked_by_outer_path],
        "future_scope_outer_path_base_count": deployment_report.summary.get(
            "future_scope_outer_path_base_count", 0
        ),
    }
    return FullDemandSupportOverviewReport(
        canonical_report=canonical_report,
        deployment_report=deployment_report,
        entries=tuple(entries),
        summary=summary,
        decision_signals=_decision_signals(entries=entries, summary=summary, scope=scope),
        scope=scope,
    )


def _render_json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _render_full_demand_support_suite_output_texts(
    *,
    report: FullDemandSupportOverviewReport,
) -> dict[str, str]:
    return {
        _BASE_MATRIX_JSON_NAME: _render_json_text(report.canonical_report.to_dict()),
        _BASE_MATRIX_MARKDOWN_NAME: report.canonical_report.to_markdown(),
        _DEPLOYMENT_MATRIX_JSON_NAME: _render_json_text(report.deployment_report.to_dict()),
        _DEPLOYMENT_MATRIX_MARKDOWN_NAME: report.deployment_report.to_markdown(),
        _OVERVIEW_JSON_NAME: _render_json_text(report.to_dict()),
        _OVERVIEW_MARKDOWN_NAME: report.to_markdown(),
    }


def check_full_demand_support_suite_outputs(
    *,
    output_dir: Path,
    report: FullDemandSupportOverviewReport,
) -> FullDemandSupportSuiteCheckResult:
    expected_outputs = _render_full_demand_support_suite_output_texts(report=report)
    drift_entries: list[FullDemandSupportSuiteDriftEntry] = []
    for filename, expected_text in expected_outputs.items():
        output_path = output_dir / filename
        if not output_path.exists():
            drift_entries.append(
                FullDemandSupportSuiteDriftEntry(filename=filename, drift_kind="missing")
            )
            continue
        actual_text = output_path.read_text(encoding="utf-8")
        if actual_text != expected_text:
            drift_entries.append(
                FullDemandSupportSuiteDriftEntry(filename=filename, drift_kind="content_mismatch")
            )
    return FullDemandSupportSuiteCheckResult(
        output_dir=output_dir,
        checked_file_count=len(expected_outputs),
        drift_entries=tuple(drift_entries),
    )


def write_full_demand_support_suite_outputs(
    *,
    output_dir: Path,
    report: FullDemandSupportOverviewReport,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "canonical_matrix_json": output_dir / _BASE_MATRIX_JSON_NAME,
        "canonical_matrix_markdown": output_dir / _BASE_MATRIX_MARKDOWN_NAME,
        "deployment_matrix_json": output_dir / _DEPLOYMENT_MATRIX_JSON_NAME,
        "deployment_matrix_markdown": output_dir / _DEPLOYMENT_MATRIX_MARKDOWN_NAME,
        "overview_json": output_dir / _OVERVIEW_JSON_NAME,
        "overview_markdown": output_dir / _OVERVIEW_MARKDOWN_NAME,
    }
    atomic_write_json(paths["canonical_matrix_json"], report.canonical_report.to_dict())
    paths["canonical_matrix_markdown"].write_text(report.canonical_report.to_markdown(), encoding="utf-8")
    atomic_write_json(paths["deployment_matrix_json"], report.deployment_report.to_dict())
    paths["deployment_matrix_markdown"].write_text(report.deployment_report.to_markdown(), encoding="utf-8")
    atomic_write_json(paths["overview_json"], report.to_dict())
    paths["overview_markdown"].write_text(report.to_markdown(), encoding="utf-8")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate the active single-base IndustrialPlanner support suite: the strict canonical full-demand matrix, "
            "the preserved companion deployment-path matrix, and the umbrella overview."
        )
    )
    parser.add_argument(
        "--base-id",
        dest="base_ids",
        action="append",
        default=None,
        help="Optional base id to audit. Repeat the flag to restrict the overview to an explicit subset.",
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
        "--output-dir",
        default=None,
        help=(
            "Optional directory for the full support-suite outputs. When supplied, the workflow writes the "
            "canonical matrix, deployment-path matrix, and overview JSON/Markdown files together. In --check "
            "mode this becomes the comparison target; when omitted there, the default checked-in example directory "
            f"{_DEFAULT_OUTPUT_DIR} is used."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "No-drift mode. Compare the freshly regenerated full support-suite outputs against the target "
            "directory and exit non-zero if any required JSON/Markdown artifact is missing or stale."
        ),
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional path for just the overview JSON report.",
    )
    parser.add_argument(
        "--markdown-output",
        default=None,
        help="Optional path for just the overview Markdown report.",
    )
    args = parser.parse_args()

    report = build_full_demand_support_overview(
        base_ids=tuple(args.base_ids) if args.base_ids else None,
        blueprint_path=Path(args.blueprint),
        evaluate_future_scope_outer_path=bool(args.evaluate_future_scope_outer_path),
    )

    if args.output_dir:
        output_dir = Path(args.output_dir)
        if args.check:
            check_result = check_full_demand_support_suite_outputs(
                output_dir=output_dir,
                report=report,
            )
            print(check_result.to_console_text())
            if not check_result.is_clean:
                raise SystemExit(1)
        else:
            write_full_demand_support_suite_outputs(output_dir=output_dir, report=report)
            print(f"wrote full-demand support suite outputs under {output_dir}")
            return

    if args.check:
        output_dir = _DEFAULT_OUTPUT_DIR
        check_result = check_full_demand_support_suite_outputs(
            output_dir=output_dir,
            report=report,
        )
        print(check_result.to_console_text())
        if not check_result.is_clean:
            raise SystemExit(1)
        return

    if args.json_output:
        atomic_write_json(Path(args.json_output), report.to_dict())
    if args.markdown_output:
        markdown_path = Path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(report.to_markdown(), encoding="utf-8")
    if not args.json_output and not args.markdown_output and not args.output_dir:
        print(report.to_markdown())


if __name__ == "__main__":
    main()
