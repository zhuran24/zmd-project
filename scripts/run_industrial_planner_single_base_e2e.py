"""Active IndustrialPlanner single-base end-to-end runbook workflow.

This script operationalizes the current single-base plan for the active
IndustrialPlanner contract:

1. regenerate the canonical 70×70 full-demand fixture from current truth;
2. export the IndustrialPlanner delivery bundle plus manifest/validator/
   throughput sidecars;
3. regenerate a fresh support-suite report set for the requested single-base
   scope;
4. recheck the checked-in support-suite inventory and repo-level checked-artifact
   gate; and
5. emit one self-contained run summary with explicit failure classification.

The default mode stays locked to the active contract base
`valley4_protocol_core`. Other bases remain available only for explicit debug
runs and do not widen the repository's active checked-in scope.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import traceback
from typing import Any, Mapping, Sequence
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_industrial_planner_checked_artifact_suite import (  # noqa: E402
    _DEFAULT_FAMILY_INVENTORY_PATH,
    _SUPPORT_RESULT_BUILDER,
    CheckedArtifactFamilyEntryResult,
    IndustrialPlannerCheckedArtifactSuiteResult,
    _build_family_entry_result,
    load_checked_artifact_family_inventory,
)
from scripts.audit_industrial_planner_full_demand_support_suite import (  # noqa: E402
    _DEFAULT_BLUEPRINT as _DEFAULT_SUPPORT_BLUEPRINT,
    build_full_demand_support_overview,
    check_full_demand_support_suite_outputs,
    write_full_demand_support_suite_outputs,
)
from scripts.audit_industrial_planner_full_demand_support_suite_inventory import (  # noqa: E402
    _DEFAULT_INVENTORY_PATH,
    FullDemandSupportSuiteInventoryEntryResult,
    FullDemandSupportSuiteInventoryResult,
    load_full_demand_support_suite_inventory,
)
from scripts.build_industrial_planner_full_demand_fixture import (  # noqa: E402
    FullDemandFixturePlanReport,
    FullDemandFixturePlanningError,
    plan_full_demand_recipe_capacity_fixture,
)
from src.adapters.industrial_planner import (  # noqa: E402
    DEFAULT_BASE_ID,
    write_industrial_planner_export_bundle,
)
from src.search.exact_campaign import atomic_write_json  # noqa: E402
from src.render.industrial_planner_exact_status import NON_AUTHORITATIVE_EXACT_OPEN_NOTE  # noqa: E402

_DEFAULT_RUN_DIR = PROJECT_ROOT / ".artifacts" / "industrial_planner_single_base_e2e"

_CANONICAL_SUBDIR = "canonical"
_BUNDLE_SUBDIR = "bundle"
_SUPPORT_SUBDIR = "support_suite"
_CHECKS_SUBDIR = "checks"

_PLAN_FIXTURE_FILENAME = "full_demand_recipe_capacity_canonical_blueprint.json"
_PLAN_REPORT_JSON_FILENAME = "full_demand_fixture_plan_report.json"
_PLAN_REPORT_MARKDOWN_FILENAME = "full_demand_fixture_plan_report.md"
_SUPPORT_INVENTORY_SUMMARY_JSON_FILENAME = "support_suite_inventory_summary.json"
_SUPPORT_INVENTORY_SUMMARY_MARKDOWN_FILENAME = "support_suite_inventory_summary.md"
_SUPPORT_INVENTORY_SUMMARY_CONSOLE_FILENAME = "support_suite_inventory_summary.txt"
_CHECKED_ARTIFACT_SUMMARY_JSON_FILENAME = "checked_artifact_suite_summary.json"
_CHECKED_ARTIFACT_SUMMARY_MARKDOWN_FILENAME = "checked_artifact_suite_summary.md"
_CHECKED_ARTIFACT_SUMMARY_CONSOLE_FILENAME = "checked_artifact_suite_summary.txt"
_RUN_SUMMARY_JSON_FILENAME = "run_summary.json"
_RUN_SUMMARY_MARKDOWN_FILENAME = "run_summary.md"
_RUN_SUMMARY_CONSOLE_FILENAME = "run_summary.txt"

_DEFAULT_SCOPE_STATEMENT = (
    "Current active IndustrialPlanner contract: `valley4_protocol_core` (70×70) only. "
    "Other known bases and the larger-base outer-deployment path remain preserved as `future_scope` "
    "and do not re-enter the active checked-in CI surface through this workflow."
)
_EXACT_CERTIFIED_NOTE = NON_AUTHORITATIVE_EXACT_OPEN_NOTE


@dataclass(frozen=True)
class SingleBaseE2EArtifact:
    artifact_id: str
    path: Path
    role: str
    stage: str
    required_for_delivery: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "path": _display_path(self.path),
            "role": self.role,
            "stage": self.stage,
            "required_for_delivery": self.required_for_delivery,
        }


@dataclass(frozen=True)
class SingleBaseE2EResult:
    requested_base_id: str
    active_contract_base_id: str
    run_dir: Path
    scope_statement: str
    requested_base_is_active_contract: bool
    overall_status: str
    failure_stage: str | None
    failure_classification: str | None
    deliverable_status: str
    exact_full_scale_certified_status: str
    exact_full_scale_certified_note: str
    planning_summary: dict[str, Any]
    export_summary: dict[str, Any]
    validation_summary: dict[str, Any]
    throughput_summary: dict[str, Any]
    fresh_support_suite_summary: dict[str, Any]
    checked_in_support_suite_summary: dict[str, Any]
    checked_artifact_suite_summary: dict[str, Any]
    artifacts: tuple[SingleBaseE2EArtifact, ...]
    notes: tuple[str, ...] = ()

    @property
    def run_summary_json_path(self) -> Path:
        return self.run_dir / _RUN_SUMMARY_JSON_FILENAME

    @property
    def run_summary_markdown_path(self) -> Path:
        return self.run_dir / _RUN_SUMMARY_MARKDOWN_FILENAME

    @property
    def run_summary_console_path(self) -> Path:
        return self.run_dir / _RUN_SUMMARY_CONSOLE_FILENAME

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_base_id": self.requested_base_id,
            "active_contract_base_id": self.active_contract_base_id,
            "requested_base_is_active_contract": self.requested_base_is_active_contract,
            "run_dir": _display_path(self.run_dir),
            "scope_statement": self.scope_statement,
            "overall_status": self.overall_status,
            "failure_stage": self.failure_stage,
            "failure_classification": self.failure_classification,
            "deliverable_status": self.deliverable_status,
            "exact_full_scale_certified": {
                "status": self.exact_full_scale_certified_status,
                "note": self.exact_full_scale_certified_note,
            },
            "planning": dict(self.planning_summary),
            "export_bundle": dict(self.export_summary),
            "validation": dict(self.validation_summary),
            "throughput": dict(self.throughput_summary),
            "fresh_support_suite": dict(self.fresh_support_suite_summary),
            "checked_in_support_suite_inventory": dict(self.checked_in_support_suite_summary),
            "checked_artifact_suite": dict(self.checked_artifact_suite_summary),
            "artifact_roles": [artifact.to_dict() for artifact in self.artifacts],
            "notes": list(self.notes),
        }

    def to_markdown(self) -> str:
        lines = [
            "# IndustrialPlanner Single-Base End-to-End Run Summary",
            "",
            self.scope_statement,
            "",
            f"- Requested base: `{self.requested_base_id}`",
            f"- Active contract base: `{self.active_contract_base_id}`",
            f"- Requested base is active contract: {self.requested_base_is_active_contract}",
            f"- Overall status: `{self.overall_status}`",
            f"- Delivery readiness: `{self.deliverable_status}`",
            f"- Full-scale exact `CERTIFIED` status: `{self.exact_full_scale_certified_status}`",
            f"- Exact-status note: {self.exact_full_scale_certified_note}",
        ]
        if self.failure_stage is not None:
            lines.append(f"- Failure stage: `{self.failure_stage}`")
        if self.failure_classification is not None:
            lines.append(f"- Failure classification: `{self.failure_classification}`")

        lines.extend(
            [
                "",
                "## Step summary",
                "",
                "| Step | Status | Key outcome |",
                "|---|---|---|",
                "| Canonical truth / planning | "
                f"`{self.planning_summary.get('status', '-')}` | "
                f"fixture `{self.planning_summary.get('fixture_path', '-')}`; report `{self.planning_summary.get('report_markdown_path', '-')}` |",
                "| Export bundle | "
                f"`{self.export_summary.get('status', '-')}` | "
                f"bundle `{self.export_summary.get('output_dir', '-')}`; warnings `{self.export_summary.get('warning_count', '-')}` |",
                "| Validator | "
                f"`{self.validation_summary.get('delivery_validation_status', '-')}` | "
                f"import/layout `{self.validation_summary.get('is_import_compatible', '-')}`/"
                f"`{self.validation_summary.get('is_layout_healthy', '-')}`; port warnings `{self.validation_summary.get('port_warning_count', '-')}` |",
                "| Throughput audit | "
                f"`{self.throughput_summary.get('status', '-')}` | "
                f"recipes proven `{self.throughput_summary.get('proven_recipe_count', '-')}` / "
                f"required `{self.throughput_summary.get('required_recipe_count', '-')}`; boundary proven `{self.throughput_summary.get('proven_boundary_commodity_count', '-')}` / required `{self.throughput_summary.get('required_boundary_commodity_count', '-')}` |",
                "| Fresh support reports | "
                f"`{self.fresh_support_suite_summary.get('status', '-')}` | "
                f"scope `{self.fresh_support_suite_summary.get('scope_kind', '-')}`; audited bases `{', '.join(self.fresh_support_suite_summary.get('audited_base_ids', [])) or '(none)'}` |",
                "| Checked-in support-suite inventory | "
                f"`{self.checked_in_support_suite_summary.get('status', '-')}` | "
                f"report sets `{self.checked_in_support_suite_summary.get('checked_report_set_count', '-')}`; drift entries `{self.checked_in_support_suite_summary.get('drift_entry_count', '-')}` |",
                "| Checked-artifact family gate | "
                f"`{self.checked_artifact_suite_summary.get('status', '-')}` | "
                f"families `{self.checked_artifact_suite_summary.get('checked_family_count', '-')}`; drift entries `{self.checked_artifact_suite_summary.get('drift_entry_count', '-')}` |",
            ]
        )

        validation_status = str(self.validation_summary.get("delivery_validation_status", "")).strip()
        if validation_status == "validator_acceptable_with_warnings":
            lines.extend(
                [
                    "",
                    "## Validator interpretation",
                    "",
                    "`validation_report.is_clean` is allowed to be `false` here when the only remaining issues are non-fatal `port_warnings`. "
                    "Delivery readiness for this workflow is gated by `is_import_compatible=true` and `is_layout_healthy=true`, not by a warning-free export.",
                ]
            )

        lines.extend(
            [
                "",
                "## Failure classes",
                "",
                "- `planning_failed`: the deterministic fixture planner did not produce a canonical single-base source blueprint.",
                "- `export_failed`: a canonical blueprint existed, but the IndustrialPlanner bundle could not be materialized.",
                "- `validation_failed`: the exporter wrote a bundle, but import compatibility or layout health failed.",
                "- `throughput_not_proven_equivalent`: the bundle exported, but the static recipe/capacity audit did not land at `proven_equivalent`.",
                "- `support_generation_failed`: the single-base support report set could not be regenerated.",
                "- `checked_in_support_drift_detected`: the checked-in support-suite inventory no longer matches current code/truth.",
                "- `checked_artifact_drift_detected`: the repo-level checked-artifact family gate detected stale checked-in artifacts.",
                "",
                "## Artifact roles",
                "",
            ]
        )
        for artifact in self.artifacts:
            required_text = "required" if artifact.required_for_delivery else "optional"
            lines.append(
                f"- `{artifact.artifact_id}` ({required_text}, {artifact.stage}) → `{_display_path(artifact.path)}` — {artifact.role}"
            )

        lines.extend(
            [
                "",
                "## Interpretation boundary",
                "",
                "- `industrial_planner.blueprint.json` is the actual target delivery blueprint for IndustrialPlanner import.",
                "- `industrial_planner.compatibility_manifest.json` is a translation / fallback / validation sidecar; it explains the export, but it is not the blueprint itself.",
                "- `throughput_report.*` is a static recipe/capacity audit only; it does not simulate steady-state runtime behavior or replace the exact proof chain.",
                "- `full_demand_support_*` files are contract-surface reports that tell you whether the active single-base support surface and its future-scope metadata are still in sync.",
                "- This workflow does not reactivate other bases. They remain `future_scope` until the single-base line is fully closed and a new base contract is explicitly defined.",
            ]
        )

        if self.notes:
            lines.extend(["", "## Additional notes", ""])
            for note in self.notes:
                lines.append(f"- {note}")
        lines.append("")
        return "\n".join(lines)

    def to_console_text(self) -> str:
        summary_location = _display_path(self.run_summary_markdown_path)
        if self.overall_status == "success":
            return (
                "IndustrialPlanner single-base e2e run succeeded for "
                f"{self.requested_base_id} with delivery status `{self.deliverable_status}`; "
                f"summary: {summary_location}"
            )
        failure_bits = []
        if self.failure_stage is not None:
            failure_bits.append(self.failure_stage)
        if self.failure_classification is not None:
            failure_bits.append(self.failure_classification)
        failure_text = " / ".join(failure_bits) if failure_bits else self.overall_status
        return (
            "IndustrialPlanner single-base e2e run did not fully close for "
            f"{self.requested_base_id}: {failure_text}; summary: {summary_location}"
        )


@dataclass(frozen=True)
class _RunLayout:
    run_dir: Path
    canonical_dir: Path
    bundle_dir: Path
    support_dir: Path
    checks_dir: Path
    fixture_path: Path
    plan_report_json_path: Path
    plan_report_markdown_path: Path
    support_inventory_summary_json_path: Path
    support_inventory_summary_markdown_path: Path
    support_inventory_summary_console_path: Path
    checked_artifact_summary_json_path: Path
    checked_artifact_summary_markdown_path: Path
    checked_artifact_summary_console_path: Path
    run_summary_json_path: Path
    run_summary_markdown_path: Path
    run_summary_console_path: Path


@dataclass(frozen=True)
class _SummaryPaths:
    support_inventory_json: Path
    support_inventory_markdown: Path
    support_inventory_console: Path
    checked_artifact_json: Path
    checked_artifact_markdown: Path
    checked_artifact_console: Path


@dataclass(frozen=True)
class SingleBaseE2EAssemblyStageResults:
    planning_summary: dict[str, Any]
    export_summary: dict[str, Any]
    validation_summary: dict[str, Any]
    throughput_summary: dict[str, Any]
    fresh_support_suite_summary: dict[str, Any]
    checked_in_support_suite_summary: dict[str, Any]
    checked_artifact_suite_summary: dict[str, Any]
    artifacts: tuple[SingleBaseE2EArtifact, ...] = ()
    notes: tuple[str, ...] = ()
    synthetic_for_test: bool = False


@dataclass(frozen=True)
class _SupportOverviewCache:
    report: Any
    base_ids: tuple[str, ...] | None
    blueprint_path: Path


@dataclass(frozen=True)
class _PlanningStageResult:
    blueprint_payload: dict[str, Any] | None
    summary: dict[str, Any]
    fixture_written: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _ExportStageResult:
    export_written: Any | None
    summary: dict[str, Any]
    validation_summary: dict[str, Any]
    throughput_summary: dict[str, Any]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _FreshSupportStageResult:
    report: Any | None
    output_paths: Mapping[str, Path] | None
    summary: dict[str, Any]
    cache: _SupportOverviewCache | None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _CheckedSupportStageResult:
    result: Any | None
    summary: dict[str, Any]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _CheckedArtifactStageResult:
    result: Any | None
    summary: dict[str, Any]
    notes: tuple[str, ...] = ()


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _safe_exception_text(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _ensure_layout(run_dir: Path) -> _RunLayout:
    canonical_dir = run_dir / _CANONICAL_SUBDIR
    bundle_dir = run_dir / _BUNDLE_SUBDIR
    support_dir = run_dir / _SUPPORT_SUBDIR
    checks_dir = run_dir / _CHECKS_SUBDIR
    canonical_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    support_dir.mkdir(parents=True, exist_ok=True)
    checks_dir.mkdir(parents=True, exist_ok=True)
    return _RunLayout(
        run_dir=run_dir,
        canonical_dir=canonical_dir,
        bundle_dir=bundle_dir,
        support_dir=support_dir,
        checks_dir=checks_dir,
        fixture_path=canonical_dir / _PLAN_FIXTURE_FILENAME,
        plan_report_json_path=canonical_dir / _PLAN_REPORT_JSON_FILENAME,
        plan_report_markdown_path=canonical_dir / _PLAN_REPORT_MARKDOWN_FILENAME,
        support_inventory_summary_json_path=checks_dir / _SUPPORT_INVENTORY_SUMMARY_JSON_FILENAME,
        support_inventory_summary_markdown_path=checks_dir / _SUPPORT_INVENTORY_SUMMARY_MARKDOWN_FILENAME,
        support_inventory_summary_console_path=checks_dir / _SUPPORT_INVENTORY_SUMMARY_CONSOLE_FILENAME,
        checked_artifact_summary_json_path=checks_dir / _CHECKED_ARTIFACT_SUMMARY_JSON_FILENAME,
        checked_artifact_summary_markdown_path=checks_dir / _CHECKED_ARTIFACT_SUMMARY_MARKDOWN_FILENAME,
        checked_artifact_summary_console_path=checks_dir / _CHECKED_ARTIFACT_SUMMARY_CONSOLE_FILENAME,
        run_summary_json_path=run_dir / _RUN_SUMMARY_JSON_FILENAME,
        run_summary_markdown_path=run_dir / _RUN_SUMMARY_MARKDOWN_FILENAME,
        run_summary_console_path=run_dir / _RUN_SUMMARY_CONSOLE_FILENAME,
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_plan_report(report: FullDemandFixturePlanReport, *, json_path: Path, markdown_path: Path) -> None:
    atomic_write_json(json_path, report.to_dict())
    _write_text(markdown_path, report.to_markdown())


def _write_support_inventory_summary(result: Any, *, layout: _RunLayout) -> _SummaryPaths:
    atomic_write_json(layout.support_inventory_summary_json_path, result.to_dict())
    _write_text(layout.support_inventory_summary_markdown_path, result.to_markdown())
    _write_text(layout.support_inventory_summary_console_path, result.to_console_text() + "\n")
    return _SummaryPaths(
        support_inventory_json=layout.support_inventory_summary_json_path,
        support_inventory_markdown=layout.support_inventory_summary_markdown_path,
        support_inventory_console=layout.support_inventory_summary_console_path,
        checked_artifact_json=layout.checked_artifact_summary_json_path,
        checked_artifact_markdown=layout.checked_artifact_summary_markdown_path,
        checked_artifact_console=layout.checked_artifact_summary_console_path,
    )


def _write_checked_artifact_summary(result: Any, *, layout: _RunLayout) -> None:
    atomic_write_json(layout.checked_artifact_summary_json_path, result.to_dict())
    _write_text(layout.checked_artifact_summary_markdown_path, result.to_markdown())
    _write_text(layout.checked_artifact_summary_console_path, result.to_console_text() + "\n")


def _validation_state(validation_report: Mapping[str, Any] | None) -> dict[str, Any]:
    if validation_report is None:
        return {
            "delivery_validation_status": "skipped",
            "is_import_compatible": None,
            "is_layout_healthy": None,
            "is_clean": None,
            "port_warning_count": None,
        }
    import_ok = bool(validation_report.get("is_import_compatible"))
    layout_ok = bool(validation_report.get("is_layout_healthy"))
    is_clean = bool(validation_report.get("is_clean"))
    port_warning_count = len(validation_report.get("port_warnings", []) or [])
    if import_ok and layout_ok and is_clean:
        delivery_validation_status = "validator_clean"
    elif import_ok and layout_ok:
        delivery_validation_status = "validator_acceptable_with_warnings"
    else:
        delivery_validation_status = "validator_failed"
    return {
        "delivery_validation_status": delivery_validation_status,
        "is_import_compatible": import_ok,
        "is_layout_healthy": layout_ok,
        "is_clean": is_clean,
        "port_warning_count": port_warning_count,
        "schema_error_count": len(validation_report.get("schema_errors", []) or []),
        "registry_error_count": len(validation_report.get("registry_errors", []) or []),
        "lot_boundary_error_count": len(validation_report.get("lot_boundary_errors", []) or []),
        "placement_constraint_error_count": len(validation_report.get("placement_constraint_errors", []) or []),
        "unsupported_rule_error_count": len(validation_report.get("unsupported_rule_errors", []) or []),
        "overlap_error_count": len(validation_report.get("overlap_errors", []) or []),
        "port_mismatch_error_count": len(validation_report.get("port_mismatch_errors", []) or []),
    }


def _throughput_state(throughput_report: Mapping[str, Any] | None) -> dict[str, Any]:
    if throughput_report is None:
        return {
            "status": "skipped",
            "required_recipe_count": None,
            "proven_recipe_count": None,
            "required_boundary_commodity_count": None,
            "proven_boundary_commodity_count": None,
            "warning_count": None,
        }
    summary = throughput_report.get("summary") if isinstance(throughput_report.get("summary"), Mapping) else {}
    return {
        "status": str(throughput_report.get("status", "unknown")),
        "required_recipe_count": int(summary.get("required_recipe_count", 0)),
        "proven_recipe_count": int(summary.get("proven_recipe_count", 0)),
        "partial_recipe_count": int(summary.get("partial_recipe_count", 0)),
        "insufficient_recipe_count": int(summary.get("insufficient_recipe_count", 0)),
        "required_boundary_commodity_count": int(summary.get("required_boundary_commodity_count", 0)),
        "proven_boundary_commodity_count": int(summary.get("proven_boundary_commodity_count", 0)),
        "partial_boundary_commodity_count": int(summary.get("partial_boundary_commodity_count", 0)),
        "insufficient_boundary_commodity_count": int(summary.get("insufficient_boundary_commodity_count", 0)),
        "warning_count": len(throughput_report.get("warnings", []) or []),
    }


def _fresh_support_scope(base_id: str) -> Sequence[str] | None:
    return None if base_id == DEFAULT_BASE_ID else (base_id,)


def _normalized_base_scope(base_ids: Sequence[str] | None) -> tuple[str, ...] | None:
    if base_ids is None:
        return None
    normalized = tuple(str(base_id) for base_id in base_ids)
    return normalized or None


def _same_resolved_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:  # pragma: no cover - defensive fallback for odd Windows paths.
        return left.absolute() == right.absolute()


def _support_cache_matches(
    cache: _SupportOverviewCache | None,
    *,
    base_ids: Sequence[str] | None,
    blueprint_path: Path,
) -> bool:
    if cache is None:
        return False
    return (
        cache.base_ids == _normalized_base_scope(base_ids)
        and _same_resolved_path(cache.blueprint_path, Path(blueprint_path))
    )


def _fresh_support_state(
    *,
    support_report: Any | None,
    support_output_paths: Mapping[str, Path] | None,
    support_check_result: Any | None,
    error_text: str | None,
) -> dict[str, Any]:
    if error_text is not None:
        return {
            "status": "failed",
            "error": error_text,
            "scope_kind": None,
            "audited_base_ids": [],
            "future_scope_base_count": None,
            "checked_file_count": None,
            "drift_entry_count": None,
        }
    if support_report is None or support_output_paths is None or support_check_result is None:
        return {
            "status": "skipped",
            "scope_kind": None,
            "audited_base_ids": [],
            "future_scope_base_count": None,
            "checked_file_count": None,
            "drift_entry_count": None,
        }
    summary = support_report.summary if isinstance(getattr(support_report, "summary", None), Mapping) else {}
    return {
        "status": "written" if bool(getattr(support_check_result, "is_clean", False)) else "drift_detected",
        "scope_kind": str(summary.get("scope_mode", "unknown")),
        "audited_base_ids": [str(base_id) for base_id in summary.get("audited_base_ids", [])],
        "future_scope_base_count": int(summary.get("future_scope_base_count", 0)),
        "checked_file_count": int(getattr(support_check_result, "checked_file_count", 0)),
        "drift_entry_count": int(len(getattr(support_check_result, "drift_entries", ()) or ())),
        "output_dir": _display_path(Path(getattr(support_check_result, "output_dir", Path(".")))),
        "overview_json_path": _display_path(Path(support_output_paths["overview_json"])),
        "overview_markdown_path": _display_path(Path(support_output_paths["overview_markdown"])),
    }


def _checked_in_support_state(result: Any | None, *, layout: _RunLayout, error_text: str | None) -> dict[str, Any]:
    if error_text is not None:
        return {
            "status": "failed",
            "error": error_text,
            "inventory_path": None,
            "checked_report_set_count": None,
            "drift_entry_count": None,
        }
    if result is None:
        return {
            "status": "skipped",
            "inventory_path": None,
            "checked_report_set_count": None,
            "drift_entry_count": None,
        }
    return {
        "status": "clean" if bool(result.is_clean) else "drift_detected",
        "inventory_path": _display_path(Path(result.inventory_path)),
        "checked_report_set_count": int(result.checked_report_set_count),
        "clean_report_set_count": int(result.clean_report_set_count),
        "drift_entry_count": int(result.drift_entry_count),
        "checked_file_count": int(result.checked_file_count),
        "audited_base_ids": list(result.audited_base_ids),
        "future_scope_base_ids": list(result.future_scope_base_ids),
        "summary_json_path": _display_path(layout.support_inventory_summary_json_path),
        "summary_markdown_path": _display_path(layout.support_inventory_summary_markdown_path),
        "summary_console_path": _display_path(layout.support_inventory_summary_console_path),
    }


def _checked_artifact_state(result: Any | None, *, layout: _RunLayout, error_text: str | None) -> dict[str, Any]:
    if error_text is not None:
        return {
            "status": "failed",
            "error": error_text,
            "family_inventory_path": None,
            "checked_family_count": None,
            "drift_entry_count": None,
        }
    if result is None:
        return {
            "status": "skipped",
            "family_inventory_path": None,
            "checked_family_count": None,
            "drift_entry_count": None,
        }
    return {
        "status": "clean" if bool(result.is_clean) else "drift_detected",
        "family_inventory_path": _display_path(Path(result.family_inventory_path)) if result.family_inventory_path is not None else None,
        "checked_family_count": int(result.checked_family_count),
        "clean_family_count": int(result.clean_family_count),
        "drift_entry_count": int(result.drift_entry_count),
        "checked_file_count": int(result.checked_file_count),
        "summary_json_path": _display_path(layout.checked_artifact_summary_json_path),
        "summary_markdown_path": _display_path(layout.checked_artifact_summary_markdown_path),
        "summary_console_path": _display_path(layout.checked_artifact_summary_console_path),
    }


def _build_support_inventory_result_with_run_cache(
    *,
    inventory_path: Path,
    support_cache: _SupportOverviewCache | None,
) -> FullDemandSupportSuiteInventoryResult:
    entries = load_full_demand_support_suite_inventory(inventory_path)
    entry_results: list[FullDemandSupportSuiteInventoryEntryResult] = []
    for entry in entries:
        entry_base_ids = entry.base_ids or None
        if _support_cache_matches(
            support_cache,
            base_ids=entry_base_ids,
            blueprint_path=entry.blueprint_path,
        ):
            report = support_cache.report
        else:
            report = build_full_demand_support_overview(
                base_ids=entry_base_ids,
                blueprint_path=entry.blueprint_path,
            )
        check_result = check_full_demand_support_suite_outputs(
            output_dir=entry.output_dir,
            report=report,
        )
        entry_results.append(
            FullDemandSupportSuiteInventoryEntryResult(
                inventory_entry=entry,
                overview_summary=dict(report.summary),
                check_result=check_result,
            )
        )
    return FullDemandSupportSuiteInventoryResult(
        inventory_path=Path(inventory_path),
        entries=tuple(entry_results),
    )


def _build_checked_artifact_result_with_run_cache(
    *,
    family_inventory_path: Path,
    support_inventory_path: Path,
    support_result: Any | None,
) -> IndustrialPlannerCheckedArtifactSuiteResult:
    family_entries = load_checked_artifact_family_inventory(family_inventory_path)
    entry_results: list[CheckedArtifactFamilyEntryResult] = []
    for entry in family_entries:
        if (
            support_result is not None
            and entry.result_builder == _SUPPORT_RESULT_BUILDER
            and _same_resolved_path(entry.inventory_path, Path(support_inventory_path))
        ):
            entry_results.append(
                CheckedArtifactFamilyEntryResult(
                    inventory_entry=entry,
                    family_result=support_result,
                )
            )
            continue
        entry_results.append(_build_family_entry_result(entry))
    return IndustrialPlannerCheckedArtifactSuiteResult(
        family_inventory_path=Path(family_inventory_path),
        entries=tuple(entry_results),
    )


def _build_artifacts(
    *,
    layout: _RunLayout,
    export_written: Any | None,
    fresh_support_output_paths: Mapping[str, Path] | None,
    include_support_checks: bool,
    include_checked_artifact_checks: bool,
) -> tuple[SingleBaseE2EArtifact, ...]:
    artifacts: list[SingleBaseE2EArtifact] = [
        SingleBaseE2EArtifact(
            artifact_id="canonical_fixture",
            path=layout.fixture_path,
            role="Regenerated canonical single-base source blueprint for this run.",
            stage="planning",
            required_for_delivery=True,
        ),
        SingleBaseE2EArtifact(
            artifact_id="fixture_plan_report_json",
            path=layout.plan_report_json_path,
            role="Machine-readable planning/generation report with slot choices and blocking classification.",
            stage="planning",
            required_for_delivery=True,
        ),
        SingleBaseE2EArtifact(
            artifact_id="fixture_plan_report_markdown",
            path=layout.plan_report_markdown_path,
            role="Operator-facing planning/generation report for the canonical fixture step.",
            stage="planning",
            required_for_delivery=True,
        ),
    ]
    if export_written is not None:
        artifacts.extend(
            [
                SingleBaseE2EArtifact(
                    artifact_id="industrial_planner_blueprint",
                    path=Path(export_written.blueprint_path),
                    role="Actual IndustrialPlanner delivery blueprint for import.",
                    stage="export",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="industrial_planner_compatibility_manifest",
                    path=Path(export_written.compatibility_manifest_path),
                    role="Translation / fallback / validation sidecar explaining the export boundary.",
                    stage="export",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="validation_report_json",
                    path=Path(export_written.validation_report_path),
                    role="Machine-readable offline import/layout validation report.",
                    stage="validator",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="validation_report_markdown",
                    path=Path(export_written.validation_report_markdown_path),
                    role="Human-readable offline import/layout validation report.",
                    stage="validator",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="throughput_report_json",
                    path=Path(export_written.throughput_report_path),
                    role="Machine-readable static recipe/capacity audit report.",
                    stage="throughput",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="throughput_report_markdown",
                    path=Path(export_written.throughput_report_markdown_path),
                    role="Human-readable static recipe/capacity audit report.",
                    stage="throughput",
                    required_for_delivery=True,
                ),
            ]
        )
    if fresh_support_output_paths is not None:
        artifacts.extend(
            [
                SingleBaseE2EArtifact(
                    artifact_id="fresh_support_canonical_matrix_json",
                    path=Path(fresh_support_output_paths["canonical_matrix_json"]),
                    role="Freshly regenerated canonical single-base support matrix for this run.",
                    stage="support_reports",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="fresh_support_canonical_matrix_markdown",
                    path=Path(fresh_support_output_paths["canonical_matrix_markdown"]),
                    role="Operator-facing canonical single-base support matrix for this run.",
                    stage="support_reports",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="fresh_support_deployment_matrix_json",
                    path=Path(fresh_support_output_paths["deployment_matrix_json"]),
                    role="Freshly regenerated companion deployment-path support matrix for this run.",
                    stage="support_reports",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="fresh_support_deployment_matrix_markdown",
                    path=Path(fresh_support_output_paths["deployment_matrix_markdown"]),
                    role="Operator-facing companion deployment-path support matrix for this run.",
                    stage="support_reports",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="fresh_support_overview_json",
                    path=Path(fresh_support_output_paths["overview_json"]),
                    role="Freshly regenerated umbrella support summary for this run.",
                    stage="support_reports",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="fresh_support_overview_markdown",
                    path=Path(fresh_support_output_paths["overview_markdown"]),
                    role="Operator-facing umbrella support summary for this run.",
                    stage="support_reports",
                    required_for_delivery=True,
                ),
            ]
        )
    if include_support_checks:
        artifacts.extend(
            [
                SingleBaseE2EArtifact(
                    artifact_id="support_suite_inventory_summary_json",
                    path=layout.support_inventory_summary_json_path,
                    role="Machine-readable verdict for the checked-in support-suite inventory.",
                    stage="checked_in_support_suite",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="support_suite_inventory_summary_markdown",
                    path=layout.support_inventory_summary_markdown_path,
                    role="Human-readable verdict for the checked-in support-suite inventory.",
                    stage="checked_in_support_suite",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="support_suite_inventory_summary_console",
                    path=layout.support_inventory_summary_console_path,
                    role="Plain-text console verdict for the checked-in support-suite inventory.",
                    stage="checked_in_support_suite",
                    required_for_delivery=False,
                ),
            ]
        )
    if include_checked_artifact_checks:
        artifacts.extend(
            [
                SingleBaseE2EArtifact(
                    artifact_id="checked_artifact_suite_summary_json",
                    path=layout.checked_artifact_summary_json_path,
                    role="Machine-readable repo-level checked-artifact gate verdict.",
                    stage="checked_artifact_gate",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="checked_artifact_suite_summary_markdown",
                    path=layout.checked_artifact_summary_markdown_path,
                    role="Human-readable repo-level checked-artifact gate verdict.",
                    stage="checked_artifact_gate",
                    required_for_delivery=True,
                ),
                SingleBaseE2EArtifact(
                    artifact_id="checked_artifact_suite_summary_console",
                    path=layout.checked_artifact_summary_console_path,
                    role="Plain-text console verdict for the repo-level checked-artifact gate.",
                    stage="checked_artifact_gate",
                    required_for_delivery=False,
                ),
            ]
        )
    return tuple(artifacts)


def _planning_summary(
    *,
    report: FullDemandFixturePlanReport | None,
    layout: _RunLayout,
    error_text: str | None,
    fixture_written: bool,
) -> dict[str, Any]:
    if report is None and error_text is not None:
        return {
            "status": "failed",
            "error": error_text,
            "fixture_path": _display_path(layout.fixture_path),
            "report_json_path": _display_path(layout.plan_report_json_path),
            "report_markdown_path": _display_path(layout.plan_report_markdown_path),
        }
    if report is None:
        return {
            "status": "skipped",
            "fixture_path": _display_path(layout.fixture_path),
            "report_json_path": _display_path(layout.plan_report_json_path),
            "report_markdown_path": _display_path(layout.plan_report_markdown_path),
        }
    return {
        "status": report.status,
        "fixture_written": fixture_written,
        "fixture_path": _display_path(layout.fixture_path),
        "report_json_path": _display_path(layout.plan_report_json_path),
        "report_markdown_path": _display_path(layout.plan_report_markdown_path),
        "selected_base_placeable_size": int(report.selected_base_placeable_size),
        "required_recipe_facility_count": int(report.required_recipe_facility_count),
        "required_recipe_area_cells": int(report.required_recipe_area_cells),
        "required_boundary_output_slots": int(report.required_boundary_output_slots),
        "required_boundary_input_slots": int(report.required_boundary_input_slots),
        "selected_input_slots": list(report.selected_input_slots),
        "selected_output_edge_counts": {
            edge: len(positions)
            for edge, positions in report.selected_output_slots_by_edge
        },
        "validation_probe_count": int(report.validation_probe_count),
        "throughput_status": report.throughput_status,
        "validator_import_compatible": report.validator_import_compatible,
        "validator_layout_healthy": report.validator_layout_healthy,
        "error_message": report.error_message,
        "warning_count": len(report.warnings),
    }


def _export_summary(export_written: Any | None, *, layout: _RunLayout, error_text: str | None) -> dict[str, Any]:
    if error_text is not None:
        return {
            "status": "failed",
            "error": error_text,
            "output_dir": _display_path(layout.bundle_dir),
        }
    if export_written is None:
        return {
            "status": "skipped",
            "output_dir": _display_path(layout.bundle_dir),
        }
    return {
        "status": "written",
        "output_dir": _display_path(layout.bundle_dir),
        "blueprint_path": _display_path(Path(export_written.blueprint_path)),
        "compatibility_manifest_path": _display_path(Path(export_written.compatibility_manifest_path)),
        "validation_report_path": _display_path(Path(export_written.validation_report_path)),
        "validation_report_markdown_path": _display_path(Path(export_written.validation_report_markdown_path)),
        "throughput_report_path": _display_path(Path(export_written.throughput_report_path)),
        "throughput_report_markdown_path": _display_path(Path(export_written.throughput_report_markdown_path)),
        "warning_count": len(export_written.warnings),
    }


def _derive_failure(
    *,
    planning_summary: Mapping[str, Any],
    export_summary: Mapping[str, Any],
    validation_summary: Mapping[str, Any],
    throughput_summary: Mapping[str, Any],
    fresh_support_suite_summary: Mapping[str, Any],
    checked_in_support_suite_summary: Mapping[str, Any],
    checked_artifact_suite_summary: Mapping[str, Any],
) -> tuple[str, str | None, str | None]:
    planning_status = str(planning_summary.get("status", "")).strip()
    if planning_status == "failed":
        return "planning_failed", "planning", "unexpected_exception"
    if planning_status and planning_status not in {"proven_equivalent", "skipped"}:
        return "planning_failed", "planning", planning_status

    export_status = str(export_summary.get("status", "")).strip()
    if export_status == "failed":
        return "export_failed", "export", "export_exception"
    if export_status != "written":
        return "export_failed", "export", export_status or "not_written"

    validation_status = str(validation_summary.get("delivery_validation_status", "")).strip()
    if validation_status == "validator_failed":
        import_ok = bool(validation_summary.get("is_import_compatible"))
        layout_ok = bool(validation_summary.get("is_layout_healthy"))
        if not import_ok and not layout_ok:
            classification = "import_and_layout_failed"
        elif not import_ok:
            classification = "import_not_compatible"
        else:
            classification = "layout_not_healthy"
        return "validation_failed", "validator", classification

    throughput_status = str(throughput_summary.get("status", "")).strip()
    if throughput_status != "proven_equivalent":
        return "throughput_not_proven_equivalent", "throughput", throughput_status or "unknown"

    fresh_support_status = str(fresh_support_suite_summary.get("status", "")).strip()
    if fresh_support_status == "failed":
        return "support_generation_failed", "support_reports", "support_generation_exception"
    if fresh_support_status == "drift_detected":
        return "support_generation_failed", "support_reports", "fresh_support_output_drift"
    if fresh_support_status != "written":
        return "support_generation_failed", "support_reports", fresh_support_status or "unknown"

    checked_support_status = str(checked_in_support_suite_summary.get("status", "")).strip()
    if checked_support_status == "failed":
        return "checked_in_support_drift_detected", "checked_in_support_suite", "support_inventory_exception"
    if checked_support_status == "drift_detected":
        return "checked_in_support_drift_detected", "checked_in_support_suite", "support_suite_inventory_drift"

    checked_artifact_status = str(checked_artifact_suite_summary.get("status", "")).strip()
    if checked_artifact_status == "failed":
        return "checked_artifact_drift_detected", "checked_artifact_gate", "checked_artifact_exception"
    if checked_artifact_status == "drift_detected":
        return "checked_artifact_drift_detected", "checked_artifact_gate", "checked_artifact_suite_drift"

    return "success", None, None


def _derive_deliverable_status(
    *,
    validation_summary: Mapping[str, Any],
    throughput_summary: Mapping[str, Any],
    fresh_support_suite_summary: Mapping[str, Any],
    checked_in_support_suite_summary: Mapping[str, Any],
    checked_artifact_suite_summary: Mapping[str, Any],
) -> str:
    bundle_ready = (
        str(validation_summary.get("delivery_validation_status", "")).strip()
        in {"validator_clean", "validator_acceptable_with_warnings"}
        and str(throughput_summary.get("status", "")).strip() == "proven_equivalent"
        and str(fresh_support_suite_summary.get("status", "")).strip() == "written"
    )
    if not bundle_ready:
        return "not_ready"
    gate_clean = (
        str(checked_in_support_suite_summary.get("status", "")).strip() == "clean"
        and str(checked_artifact_suite_summary.get("status", "")).strip() == "clean"
    )
    if gate_clean:
        return "ready_for_single_base_delivery"
    return "bundle_ready_repo_reports_drifting"


def _run_planning_stage(*, requested_base_id: str, layout: _RunLayout) -> _PlanningStageResult:
    notes: list[str] = []
    plan_report: FullDemandFixturePlanReport | None = None
    blueprint_payload: dict[str, Any] | None = None
    planning_error_text: str | None = None
    fixture_written = False

    try:
        blueprint_payload, plan_report = plan_full_demand_recipe_capacity_fixture(
            base_id=requested_base_id
        )
    except FullDemandFixturePlanningError as exc:
        plan_report = exc.report
        planning_error_text = exc.report.error_message or exc.report.status
        notes.append(
            "Fixture planning failed closed before export; see the planning report for the precise blocker classification."
        )
    except Exception as exc:  # pragma: no cover - defensive guard.
        planning_error_text = _safe_exception_text(exc)
        notes.append(f"Unexpected planning exception: {planning_error_text}")
        notes.append(traceback.format_exc().strip())

    if plan_report is not None:
        _write_plan_report(
            plan_report,
            json_path=layout.plan_report_json_path,
            markdown_path=layout.plan_report_markdown_path,
        )
    if blueprint_payload is not None:
        atomic_write_json(layout.fixture_path, blueprint_payload)
        fixture_written = True

    return _PlanningStageResult(
        blueprint_payload=blueprint_payload,
        summary=_planning_summary(
            report=plan_report,
            layout=layout,
            error_text=planning_error_text,
            fixture_written=fixture_written,
        ),
        fixture_written=fixture_written,
        notes=tuple(notes),
    )


def _run_export_stage(
    *,
    requested_base_id: str,
    layout: _RunLayout,
    blueprint_payload: dict[str, Any] | None,
) -> _ExportStageResult:
    notes: list[str] = []
    export_written: Any | None = None
    export_error_text: str | None = None
    if blueprint_payload is not None:
        try:
            export_written = write_industrial_planner_export_bundle(
                output_dir=layout.bundle_dir,
                blueprint_payload=blueprint_payload,
                base_id=requested_base_id,
            )
        except Exception as exc:  # pragma: no cover - defensive guard.
            export_error_text = _safe_exception_text(exc)
            notes.append(f"Export step failed: {export_error_text}")
            notes.append(traceback.format_exc().strip())
    else:
        notes.append("Export step skipped because no canonical fixture payload was produced.")

    return _ExportStageResult(
        export_written=export_written,
        summary=_export_summary(export_written, layout=layout, error_text=export_error_text),
        validation_summary=_validation_state(
            export_written.validation_report if export_written is not None else None
        ),
        throughput_summary=_throughput_state(
            export_written.throughput_report if export_written is not None else None
        ),
        notes=tuple(notes),
    )


def _run_fresh_support_stage(
    *,
    requested_base_id: str,
    layout: _RunLayout,
) -> _FreshSupportStageResult:
    notes: list[str] = []
    fresh_support_report: Any | None = None
    fresh_support_output_paths: Mapping[str, Path] | None = None
    fresh_support_check_result: Any | None = None
    fresh_support_error_text: str | None = None
    support_scope = _fresh_support_scope(requested_base_id)
    try:
        fresh_support_report = build_full_demand_support_overview(base_ids=support_scope)
        fresh_support_output_paths = write_full_demand_support_suite_outputs(
            output_dir=layout.support_dir,
            report=fresh_support_report,
        )
        fresh_support_check_result = check_full_demand_support_suite_outputs(
            output_dir=layout.support_dir,
            report=fresh_support_report,
        )
        if not bool(fresh_support_check_result.is_clean):
            notes.append(
                "Fresh support-suite output drift was detected immediately after writing; inspect the support-suite directory."
            )
    except Exception as exc:  # pragma: no cover - defensive guard.
        fresh_support_error_text = _safe_exception_text(exc)
        notes.append(f"Support-suite regeneration failed: {fresh_support_error_text}")
        notes.append(traceback.format_exc().strip())

    cache = (
        _SupportOverviewCache(
            report=fresh_support_report,
            base_ids=_normalized_base_scope(support_scope),
            blueprint_path=_DEFAULT_SUPPORT_BLUEPRINT,
        )
        if fresh_support_report is not None
        else None
    )
    return _FreshSupportStageResult(
        report=fresh_support_report,
        output_paths=fresh_support_output_paths,
        summary=_fresh_support_state(
            support_report=fresh_support_report,
            support_output_paths=fresh_support_output_paths,
            support_check_result=fresh_support_check_result,
            error_text=fresh_support_error_text,
        ),
        cache=cache,
        notes=tuple(notes),
    )


def _run_checked_in_support_stage(
    *,
    layout: _RunLayout,
    support_inventory_path: Path,
    support_cache: _SupportOverviewCache | None,
) -> _CheckedSupportStageResult:
    notes: list[str] = []
    checked_in_support_result: Any | None = None
    checked_in_support_error_text: str | None = None
    try:
        checked_in_support_result = _build_support_inventory_result_with_run_cache(
            inventory_path=Path(support_inventory_path),
            support_cache=support_cache,
        )
        _write_support_inventory_summary(checked_in_support_result, layout=layout)
    except Exception as exc:  # pragma: no cover - defensive guard.
        checked_in_support_error_text = _safe_exception_text(exc)
        notes.append(f"Checked-in support-suite inventory check failed: {checked_in_support_error_text}")
        notes.append(traceback.format_exc().strip())

    return _CheckedSupportStageResult(
        result=checked_in_support_result,
        summary=_checked_in_support_state(
            checked_in_support_result,
            layout=layout,
            error_text=checked_in_support_error_text,
        ),
        notes=tuple(notes),
    )


def _run_checked_artifact_stage(
    *,
    layout: _RunLayout,
    family_inventory_path: Path,
    support_inventory_path: Path,
    checked_in_support_result: Any | None,
) -> _CheckedArtifactStageResult:
    notes: list[str] = []
    checked_artifact_result: Any | None = None
    checked_artifact_error_text: str | None = None
    try:
        checked_artifact_result = _build_checked_artifact_result_with_run_cache(
            family_inventory_path=Path(family_inventory_path),
            support_inventory_path=Path(support_inventory_path),
            support_result=checked_in_support_result,
        )
        _write_checked_artifact_summary(checked_artifact_result, layout=layout)
    except Exception as exc:  # pragma: no cover - defensive guard.
        checked_artifact_error_text = _safe_exception_text(exc)
        notes.append(f"Checked-artifact suite check failed: {checked_artifact_error_text}")
        notes.append(traceback.format_exc().strip())

    return _CheckedArtifactStageResult(
        result=checked_artifact_result,
        summary=_checked_artifact_state(
            checked_artifact_result,
            layout=layout,
            error_text=checked_artifact_error_text,
        ),
        notes=tuple(notes),
    )


def _run_single_base_e2e_stages(
    *,
    layout: _RunLayout,
    requested_base_id: str,
    support_inventory_path: Path,
    family_inventory_path: Path,
) -> SingleBaseE2EAssemblyStageResults:
    planning_stage = _run_planning_stage(
        requested_base_id=requested_base_id,
        layout=layout,
    )
    export_stage = _run_export_stage(
        requested_base_id=requested_base_id,
        layout=layout,
        blueprint_payload=planning_stage.blueprint_payload,
    )
    fresh_support_stage = _run_fresh_support_stage(
        requested_base_id=requested_base_id,
        layout=layout,
    )
    checked_support_stage = _run_checked_in_support_stage(
        layout=layout,
        support_inventory_path=Path(support_inventory_path),
        support_cache=fresh_support_stage.cache,
    )
    checked_artifact_stage = _run_checked_artifact_stage(
        layout=layout,
        family_inventory_path=Path(family_inventory_path),
        support_inventory_path=Path(support_inventory_path),
        checked_in_support_result=checked_support_stage.result,
    )
    artifacts = _build_artifacts(
        layout=layout,
        export_written=export_stage.export_written,
        fresh_support_output_paths=fresh_support_stage.output_paths,
        include_support_checks=checked_support_stage.result is not None,
        include_checked_artifact_checks=checked_artifact_stage.result is not None,
    )
    notes = tuple(
        dict.fromkeys(
            note
            for stage_notes in (
                planning_stage.notes,
                export_stage.notes,
                fresh_support_stage.notes,
                checked_support_stage.notes,
                checked_artifact_stage.notes,
            )
            for note in stage_notes
            if str(note).strip()
        )
    )
    return SingleBaseE2EAssemblyStageResults(
        planning_summary=planning_stage.summary,
        export_summary=export_stage.summary,
        validation_summary=export_stage.validation_summary,
        throughput_summary=export_stage.throughput_summary,
        fresh_support_suite_summary=fresh_support_stage.summary,
        checked_in_support_suite_summary=checked_support_stage.summary,
        checked_artifact_suite_summary=checked_artifact_stage.summary,
        artifacts=artifacts,
        notes=notes,
    )


def assemble_single_base_e2e_result(
    *,
    run_dir: Path,
    requested_base_id: str,
    stage_results: SingleBaseE2EAssemblyStageResults,
    active_contract_base_id: str = DEFAULT_BASE_ID,
    scope_statement: str = _DEFAULT_SCOPE_STATEMENT,
) -> SingleBaseE2EResult:
    normalized_requested_base_id = str(requested_base_id)
    normalized_active_contract_base_id = str(active_contract_base_id)
    planning_summary = dict(stage_results.planning_summary)
    export_summary = dict(stage_results.export_summary)
    validation_summary = dict(stage_results.validation_summary)
    throughput_summary = dict(stage_results.throughput_summary)
    fresh_support_suite_summary = dict(stage_results.fresh_support_suite_summary)
    checked_in_support_suite_summary = dict(stage_results.checked_in_support_suite_summary)
    checked_artifact_suite_summary = dict(stage_results.checked_artifact_suite_summary)

    overall_status, failure_stage, failure_classification = _derive_failure(
        planning_summary=planning_summary,
        export_summary=export_summary,
        validation_summary=validation_summary,
        throughput_summary=throughput_summary,
        fresh_support_suite_summary=fresh_support_suite_summary,
        checked_in_support_suite_summary=checked_in_support_suite_summary,
        checked_artifact_suite_summary=checked_artifact_suite_summary,
    )
    deliverable_status = _derive_deliverable_status(
        validation_summary=validation_summary,
        throughput_summary=throughput_summary,
        fresh_support_suite_summary=fresh_support_suite_summary,
        checked_in_support_suite_summary=checked_in_support_suite_summary,
        checked_artifact_suite_summary=checked_artifact_suite_summary,
    )

    return SingleBaseE2EResult(
        requested_base_id=normalized_requested_base_id,
        active_contract_base_id=normalized_active_contract_base_id,
        run_dir=Path(run_dir),
        scope_statement=scope_statement,
        requested_base_is_active_contract=(
            normalized_requested_base_id == normalized_active_contract_base_id
        ),
        overall_status=overall_status,
        failure_stage=failure_stage,
        failure_classification=failure_classification,
        deliverable_status=deliverable_status,
        exact_full_scale_certified_status="open",
        exact_full_scale_certified_note=_EXACT_CERTIFIED_NOTE,
        planning_summary=planning_summary,
        export_summary=export_summary,
        validation_summary=validation_summary,
        throughput_summary=throughput_summary,
        fresh_support_suite_summary=fresh_support_suite_summary,
        checked_in_support_suite_summary=checked_in_support_suite_summary,
        checked_artifact_suite_summary=checked_artifact_suite_summary,
        artifacts=tuple(stage_results.artifacts),
        notes=tuple(
            dict.fromkeys(note for note in stage_results.notes if str(note).strip())
        ),
    )


def run_single_base_e2e_workflow(
    *,
    run_dir: Path = _DEFAULT_RUN_DIR,
    base_id: str = DEFAULT_BASE_ID,
    support_inventory_path: Path = _DEFAULT_INVENTORY_PATH,
    family_inventory_path: Path = _DEFAULT_FAMILY_INVENTORY_PATH,
) -> SingleBaseE2EResult:
    layout = _ensure_layout(Path(run_dir))
    requested_base_id = str(base_id)
    stage_results = _run_single_base_e2e_stages(
        layout=layout,
        requested_base_id=requested_base_id,
        support_inventory_path=Path(support_inventory_path),
        family_inventory_path=Path(family_inventory_path),
    )
    result = assemble_single_base_e2e_result(
        run_dir=layout.run_dir,
        requested_base_id=requested_base_id,
        stage_results=stage_results,
    )

    atomic_write_json(layout.run_summary_json_path, result.to_dict())
    _write_text(layout.run_summary_markdown_path, result.to_markdown())
    _write_text(layout.run_summary_console_path, result.to_console_text() + "\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the active IndustrialPlanner single-base end-to-end workflow: regenerate the canonical fixture, "
            "export the bundle, refresh a fresh support report set, recheck the checked-in inventories, and write one failure-classified summary."
        )
    )
    parser.add_argument(
        "--base-id",
        default=DEFAULT_BASE_ID,
        help=(
            "IndustrialPlanner base id to run. Defaults to the active single-base contract "
            f"{DEFAULT_BASE_ID!r}. Non-default bases are treated as explicit debug runs only and do not widen checked-in scope."
        ),
    )
    parser.add_argument(
        "--run-dir",
        default=str(_DEFAULT_RUN_DIR),
        help="Directory where the canonical fixture, export bundle, support reports, check summaries, and run summary should be written.",
    )
    parser.add_argument(
        "--support-inventory",
        default=str(_DEFAULT_INVENTORY_PATH),
        help="Checked-in support-suite inventory path to validate after the fresh run.",
    )
    parser.add_argument(
        "--family-inventory",
        default=str(_DEFAULT_FAMILY_INVENTORY_PATH),
        help="Checked-in checked-artifact family inventory path to validate after the fresh run.",
    )
    args = parser.parse_args()

    result = run_single_base_e2e_workflow(
        run_dir=Path(args.run_dir),
        base_id=str(args.base_id),
        support_inventory_path=Path(args.support_inventory),
        family_inventory_path=Path(args.family_inventory),
    )
    print(result.to_console_text())
    return 0 if result.overall_status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
