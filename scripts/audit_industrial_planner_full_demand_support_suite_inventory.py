"""Inventory-driven workflow for checked-in full-demand support-suite report sets.

The active checked-in inventory is intentionally small: one default-contract
report set for the single 70×70 `valley4_protocol_core` scope. The loader and
summary logic still support explicit subset entries so dormant future-scope
slices can be reactivated later without reworking the workflow.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_industrial_planner_full_demand_support_suite import (  # noqa: E402
    build_full_demand_support_overview,
    check_full_demand_support_suite_outputs,
    write_full_demand_support_suite_outputs,
)
from src.search.exact_campaign import atomic_write_json  # noqa: E402

_DEFAULT_INVENTORY_PATH = (
    PROJECT_ROOT
    / "data"
    / "examples"
    / "industrial_planner"
    / "full_demand_support_suite_inventory.json"
)
_DEFAULT_SCOPE_KIND = "default_contract_scope"
_EXPLICIT_SCOPE_KIND = "explicit_subset"


def _ordered_unique(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = str(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


@dataclass(frozen=True)
class FullDemandSupportSuiteInventoryEntry:
    report_set_id: str
    blueprint_path: Path
    output_dir: Path
    base_ids: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_set_id": self.report_set_id,
            "blueprint_path": str(self.blueprint_path),
            "output_dir": str(self.output_dir),
            "base_ids": list(self.base_ids),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class FullDemandSupportSuiteInventoryEntryResult:
    inventory_entry: FullDemandSupportSuiteInventoryEntry
    overview_summary: dict[str, Any]
    check_result: Any

    @property
    def report_set_id(self) -> str:
        return self.inventory_entry.report_set_id

    @property
    def output_dir(self) -> Path:
        return self.inventory_entry.output_dir

    @property
    def blueprint_path(self) -> Path:
        return self.inventory_entry.blueprint_path

    @property
    def base_ids(self) -> tuple[str, ...]:
        return self.inventory_entry.base_ids

    @property
    def notes(self) -> tuple[str, ...]:
        return self.inventory_entry.notes

    @property
    def scope_kind(self) -> str:
        explicit_summary_scope = str(self.overview_summary.get("scope_mode", "")).strip()
        if explicit_summary_scope:
            return explicit_summary_scope
        return _DEFAULT_SCOPE_KIND if not self.base_ids else _EXPLICIT_SCOPE_KIND

    @property
    def audited_base_ids(self) -> tuple[str, ...]:
        summary_ids = self.overview_summary.get("audited_base_ids", [])
        normalized = [str(base_id) for base_id in summary_ids if str(base_id)]
        if normalized:
            return tuple(normalized)
        return self.base_ids

    @property
    def future_scope_base_ids(self) -> tuple[str, ...]:
        return tuple(
            str(base_id)
            for base_id in self.overview_summary.get("future_scope_base_ids", [])
            if str(base_id)
        )

    @property
    def status_transition_base_ids(self) -> tuple[str, ...]:
        return tuple(
            str(base_id)
            for base_id in self.overview_summary.get("status_transition_base_ids", [])
            if str(base_id)
        )

    @property
    def unlocked_base_ids(self) -> tuple[str, ...]:
        return tuple(
            str(base_id)
            for base_id in self.overview_summary.get("unlocked_base_ids", [])
            if str(base_id)
        )

    @property
    def best_available_proven_equivalent_base_ids(self) -> tuple[str, ...]:
        return tuple(
            str(base_id)
            for base_id in self.overview_summary.get("best_available_proven_equivalent_base_ids", [])
            if str(base_id)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "inventory_entry": self.inventory_entry.to_dict(),
            "scope_kind": self.scope_kind,
            "audited_base_ids": list(self.audited_base_ids),
            "future_scope_base_ids": list(self.future_scope_base_ids),
            "status_transition_base_ids": list(self.status_transition_base_ids),
            "unlocked_base_ids": list(self.unlocked_base_ids),
            "best_available_proven_equivalent_base_ids": list(
                self.best_available_proven_equivalent_base_ids
            ),
            "overview_summary": dict(self.overview_summary),
            "check_result": self.check_result.to_dict(),
        }


@dataclass(frozen=True)
class FullDemandSupportSuiteInventoryResult:
    inventory_path: Path
    entries: tuple[FullDemandSupportSuiteInventoryEntryResult, ...]

    @property
    def checked_report_set_count(self) -> int:
        return len(self.entries)

    @property
    def clean_report_set_count(self) -> int:
        return sum(1 for entry in self.entries if entry.check_result.is_clean)

    @property
    def checked_file_count(self) -> int:
        return sum(int(entry.check_result.checked_file_count) for entry in self.entries)

    @property
    def drift_entry_count(self) -> int:
        return sum(len(entry.check_result.drift_entries) for entry in self.entries)

    @property
    def default_contract_scope_report_set_count(self) -> int:
        return sum(1 for entry in self.entries if entry.scope_kind == _DEFAULT_SCOPE_KIND)

    @property
    def explicit_subset_report_set_count(self) -> int:
        return sum(1 for entry in self.entries if entry.scope_kind == _EXPLICIT_SCOPE_KIND)

    @property
    def summed_audited_base_membership_count(self) -> int:
        return sum(len(entry.audited_base_ids) for entry in self.entries)

    @property
    def audited_base_ids(self) -> tuple[str, ...]:
        ordered: list[str] = []
        for entry in self.entries:
            ordered.extend(entry.audited_base_ids)
        return _ordered_unique(ordered)

    @property
    def unique_audited_base_count(self) -> int:
        return len(self.audited_base_ids)

    @property
    def future_scope_base_ids(self) -> tuple[str, ...]:
        ordered: list[str] = []
        for entry in self.entries:
            ordered.extend(entry.future_scope_base_ids)
        return _ordered_unique(ordered)

    @property
    def future_scope_base_count(self) -> int:
        return len(self.future_scope_base_ids)

    @property
    def repeated_audited_base_ids(self) -> tuple[str, ...]:
        counts: Counter[str] = Counter()
        ordered: list[str] = []
        for entry in self.entries:
            for base_id in entry.audited_base_ids:
                normalized = str(base_id)
                counts[normalized] += 1
                ordered.append(normalized)
        return tuple(base_id for base_id in _ordered_unique(ordered) if counts[base_id] > 1)

    @property
    def repeated_audited_base_count(self) -> int:
        return len(self.repeated_audited_base_ids)

    @property
    def status_transition_report_set_count(self) -> int:
        return sum(1 for entry in self.entries if entry.status_transition_base_ids)

    @property
    def status_transition_base_ids(self) -> tuple[str, ...]:
        ordered: list[str] = []
        for entry in self.entries:
            ordered.extend(entry.status_transition_base_ids)
        return _ordered_unique(ordered)

    @property
    def unique_status_transition_base_count(self) -> int:
        return len(self.status_transition_base_ids)

    @property
    def unlocked_base_ids(self) -> tuple[str, ...]:
        ordered: list[str] = []
        for entry in self.entries:
            ordered.extend(entry.unlocked_base_ids)
        return _ordered_unique(ordered)

    @property
    def unlocked_base_count(self) -> int:
        return len(self.unlocked_base_ids)

    @property
    def best_available_proven_equivalent_base_count(self) -> int:
        return sum(
            int(entry.overview_summary.get("best_available_proven_equivalent_base_count", 0))
            for entry in self.entries
        )

    @property
    def best_available_proven_equivalent_base_ids(self) -> tuple[str, ...]:
        ordered: list[str] = []
        for entry in self.entries:
            ordered.extend(entry.best_available_proven_equivalent_base_ids)
        return _ordered_unique(ordered)

    @property
    def unique_best_available_proven_equivalent_base_count(self) -> int:
        return len(self.best_available_proven_equivalent_base_ids)

    @property
    def is_clean(self) -> bool:
        return self.clean_report_set_count == self.checked_report_set_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "checked_report_set_count": self.checked_report_set_count,
                "clean_report_set_count": self.clean_report_set_count,
                "drift_report_set_count": self.checked_report_set_count - self.clean_report_set_count,
                "checked_file_count": self.checked_file_count,
                "drift_entry_count": self.drift_entry_count,
                "default_contract_scope_report_set_count": self.default_contract_scope_report_set_count,
                "explicit_subset_report_set_count": self.explicit_subset_report_set_count,
                "summed_audited_base_membership_count": self.summed_audited_base_membership_count,
                "unique_audited_base_count": self.unique_audited_base_count,
                "audited_base_ids": list(self.audited_base_ids),
                "future_scope_base_count": self.future_scope_base_count,
                "future_scope_base_ids": list(self.future_scope_base_ids),
                "repeated_audited_base_count": self.repeated_audited_base_count,
                "repeated_audited_base_ids": list(self.repeated_audited_base_ids),
                "status_transition_report_set_count": self.status_transition_report_set_count,
                "unique_status_transition_base_count": self.unique_status_transition_base_count,
                "status_transition_base_ids": list(self.status_transition_base_ids),
                "unlocked_base_count": self.unlocked_base_count,
                "unlocked_base_ids": list(self.unlocked_base_ids),
                "best_available_proven_equivalent_base_count": self.best_available_proven_equivalent_base_count,
                "unique_best_available_proven_equivalent_base_count": self.unique_best_available_proven_equivalent_base_count,
                "best_available_proven_equivalent_base_ids": list(
                    self.best_available_proven_equivalent_base_ids
                ),
                "is_clean": self.is_clean,
            },
            "inventory_path": str(self.inventory_path),
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def to_markdown(self) -> str:
        lines = [
            "# IndustrialPlanner Full-Demand Support Suite Inventory",
            "",
            "This inventory-driven workflow rechecks every checked-in full-demand decision-surface report set listed in the support-suite inventory. The active inventory is intentionally narrowed to the default single-base contract, while explicit subset entries remain available for future-scope/debug reactivation.",
            "",
            f"- Inventory: `{self.inventory_path}`",
            f"- Report sets checked: {self.checked_report_set_count}",
            f"- Report sets clean: {self.clean_report_set_count}",
            f"- Files checked: {self.checked_file_count}",
            f"- Drift entries: {self.drift_entry_count}",
            f"- Default-contract report sets: {self.default_contract_scope_report_set_count}",
            f"- Explicit-subset report sets: {self.explicit_subset_report_set_count}",
            f"- Unique audited bases across listed report sets: {self.unique_audited_base_count}",
            f"- Preserved future-scope bases referenced by listed report sets: {self.future_scope_base_count}",
            f"- Bases appearing in multiple report sets: {self.repeated_audited_base_count}",
            f"- Report sets with status transitions: {self.status_transition_report_set_count}",
            f"- Unique transitioned bases across listed report sets: {self.unique_status_transition_base_count}",
            f"- Unlocked bases across listed report sets: {self.unlocked_base_count}",
            f"- Unique best-available `proven_equivalent` bases across listed report sets: {self.unique_best_available_proven_equivalent_base_count}",
            f"- Summed best-available `proven_equivalent` memberships: {self.best_available_proven_equivalent_base_count}",
            f"- Overall status: `{'clean' if self.is_clean else 'drift_detected'}`",
            "",
            "## Report-set summary",
            "",
            "| Report set | Scope | Output dir | Bases | Future-scope bases | Status | Files | Best available proven | Transition bases | Unlocked bases |",
            "|---|---|---|---:|---:|---|---:|---:|---:|---:|",
        ]
        for entry in self.entries:
            base_count = len(entry.audited_base_ids)
            future_scope_count = len(entry.future_scope_base_ids)
            best_available_proven = len(entry.best_available_proven_equivalent_base_ids)
            transition_count = len(entry.status_transition_base_ids)
            unlocked_count = len(entry.unlocked_base_ids)
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{entry.report_set_id}`",
                        f"`{entry.scope_kind}`",
                        f"`{entry.output_dir}`",
                        str(base_count),
                        str(future_scope_count),
                        f"`{'clean' if entry.check_result.is_clean else 'drift_detected'}`",
                        str(entry.check_result.checked_file_count),
                        str(best_available_proven),
                        str(transition_count),
                        str(unlocked_count),
                    ]
                )
                + " |"
            )

        drift_entries = [entry for entry in self.entries if entry.check_result.drift_entries]
        if drift_entries:
            lines.extend(["", "## Drift details", ""])
            for entry in drift_entries:
                lines.append(f"### `{entry.report_set_id}`")
                lines.append("")
                lines.append(f"- Scope: `{entry.scope_kind}`")
                lines.append(f"- Output dir: `{entry.output_dir}`")
                for drift_entry in entry.check_result.drift_entries:
                    lines.append(f"- `{drift_entry.drift_kind}`: `{drift_entry.filename}`")
                lines.append("")

        lines.extend(
            [
                "## Operational notes",
                "",
                "- Each inventory entry reuses the existing single-report-set support-suite regeneration path.",
                "- The checked-in inventory now defaults to one active default-contract report set; explicit subset entries remain supported for future-scope/debug use but are not required by the active CI gate.",
                "- The suite summary still tracks unique audited-base coverage and repeated-base overlap so any future explicit subsets do not silently double-count the repo-level decision surface.",
                "- This suite stays postprocess-only: it validates checked-in strict/deployment decision reports without widening canonical truth or certified evidence.",
                "- The repo-level checked-artifact gate consumes this suite instead of hard-coding a single support-report directory.",
            ]
        )
        return "\n".join(lines)

    def to_console_text(self) -> str:
        if self.is_clean:
            return (
                f"full-demand support suite inventory is in sync via {self.inventory_path} "
                f"({self.checked_report_set_count} report sets, {self.checked_file_count} files checked)"
            )
        lines = [
            (
                f"full-demand support suite inventory drift detected via {self.inventory_path}: "
                f"{self.drift_entry_count} issue{'s' if self.drift_entry_count != 1 else ''} "
                f"across {self.checked_report_set_count} report set{'s' if self.checked_report_set_count != 1 else ''}"
            )
        ]
        for entry in self.entries:
            if not entry.check_result.drift_entries:
                continue
            lines.append(
                f"- {entry.report_set_id}: {'clean' if entry.check_result.is_clean else 'drift_detected'}"
            )
            for drift_entry in entry.check_result.drift_entries:
                lines.append(f"  - {drift_entry.drift_kind}: {drift_entry.filename}")
        lines.append(
            "regenerate with: "
            f"python scripts/audit_industrial_planner_full_demand_support_suite_inventory.py --inventory {self.inventory_path}"
        )
        return "\n".join(lines)


def _resolve_inventory_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def load_full_demand_support_suite_inventory(
    inventory_path: Path = _DEFAULT_INVENTORY_PATH,
) -> tuple[FullDemandSupportSuiteInventoryEntry, ...]:
    resolved_inventory_path = Path(inventory_path)
    payload = json.loads(resolved_inventory_path.read_text(encoding="utf-8"))
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("support suite inventory must contain a non-empty 'entries' list")

    seen_report_set_ids: set[str] = set()
    entries: list[FullDemandSupportSuiteInventoryEntry] = []
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"support suite inventory entry {index} must be an object")
        report_set_id = str(raw_entry.get("report_set_id", "")).strip()
        blueprint_raw = raw_entry.get("blueprint_path")
        output_raw = raw_entry.get("output_dir")
        if not report_set_id:
            raise ValueError(f"support suite inventory entry {index} is missing report_set_id")
        if report_set_id in seen_report_set_ids:
            raise ValueError(f"duplicate support suite inventory report_set_id '{report_set_id}'")
        if not blueprint_raw:
            raise ValueError(f"support suite inventory entry {index} is missing blueprint_path")
        if not output_raw:
            raise ValueError(f"support suite inventory entry {index} is missing output_dir")
        seen_report_set_ids.add(report_set_id)
        blueprint_path = _resolve_inventory_path(str(blueprint_raw))
        output_dir = _resolve_inventory_path(str(output_raw))
        base_ids = tuple(
            str(base_id).strip()
            for base_id in raw_entry.get("base_ids", [])
            if str(base_id).strip()
        )
        notes = tuple(str(note) for note in raw_entry.get("notes", []) if str(note).strip())
        entries.append(
            FullDemandSupportSuiteInventoryEntry(
                report_set_id=report_set_id,
                blueprint_path=blueprint_path,
                output_dir=output_dir,
                base_ids=base_ids,
                notes=notes,
            )
        )
    return tuple(entries)


def build_full_demand_support_suite_inventory_result(
    *,
    inventory_path: Path = _DEFAULT_INVENTORY_PATH,
) -> FullDemandSupportSuiteInventoryResult:
    entries = load_full_demand_support_suite_inventory(inventory_path)
    entry_results: list[FullDemandSupportSuiteInventoryEntryResult] = []
    for entry in entries:
        report = build_full_demand_support_overview(
            base_ids=entry.base_ids or None,
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


def write_full_demand_support_suite_inventory_outputs(
    *,
    inventory_path: Path = _DEFAULT_INVENTORY_PATH,
) -> dict[str, dict[str, Path]]:
    entries = load_full_demand_support_suite_inventory(inventory_path)
    output_paths: dict[str, dict[str, Path]] = {}
    for entry in entries:
        report = build_full_demand_support_overview(
            base_ids=entry.base_ids or None,
            blueprint_path=entry.blueprint_path,
        )
        output_paths[entry.report_set_id] = write_full_demand_support_suite_outputs(
            output_dir=entry.output_dir,
            report=report,
        )
    return output_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate or validate all checked-in IndustrialPlanner full-demand support report sets listed in the inventory."
        )
    )
    parser.add_argument(
        "--inventory",
        default=str(_DEFAULT_INVENTORY_PATH),
        help="Inventory JSON listing the checked-in full-demand support report sets to refresh or validate.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "No-drift mode. Rebuild every inventory entry in memory, compare it against the listed output directories, "
            "and exit non-zero if any required support-report artifact is missing or stale."
        ),
    )
    parser.add_argument(
        "--check-json-output",
        default=None,
        help="Optional path for a machine-readable suite summary JSON sidecar. Valid with --check only.",
    )
    parser.add_argument(
        "--check-markdown-output",
        default=None,
        help="Optional path for a human-readable suite summary Markdown sidecar. Valid with --check only.",
    )
    parser.add_argument(
        "--check-console-output",
        default=None,
        help="Optional path for a plain-text suite summary copy. Valid with --check only.",
    )
    args = parser.parse_args()

    if not args.check and (args.check_json_output or args.check_markdown_output or args.check_console_output):
        parser.error("--check-json-output/--check-markdown-output/--check-console-output require --check")

    inventory_path = Path(args.inventory)
    if args.check:
        result = build_full_demand_support_suite_inventory_result(inventory_path=inventory_path)
        print(result.to_console_text())
        if args.check_json_output:
            atomic_write_json(Path(args.check_json_output), result.to_dict())
        if args.check_markdown_output:
            markdown_path = Path(args.check_markdown_output)
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(result.to_markdown(), encoding="utf-8")
        if args.check_console_output:
            console_path = Path(args.check_console_output)
            console_path.parent.mkdir(parents=True, exist_ok=True)
            console_path.write_text(result.to_console_text() + "\n", encoding="utf-8")
        if not result.is_clean:
            raise SystemExit(1)
        return

    output_paths = write_full_demand_support_suite_inventory_outputs(inventory_path=inventory_path)
    print(f"wrote support-suite outputs for {len(output_paths)} report set(s)")


if __name__ == "__main__":
    main()
