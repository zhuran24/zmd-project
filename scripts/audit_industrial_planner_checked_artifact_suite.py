"""Repo-level no-drift gate for checked IndustrialPlanner artifacts."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib
from pathlib import Path
import sys
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_industrial_planner_full_demand_support_suite_inventory import (  # noqa: E402
    _DEFAULT_INVENTORY_PATH as _DEFAULT_SUPPORT_INVENTORY,
)
from scripts.audit_industrial_planner_outer_base_bundle_suite import (  # noqa: E402
    _DEFAULT_INVENTORY_PATH as _DEFAULT_OUTER_BUNDLE_INVENTORY,
)
from src.search.exact_campaign import atomic_write_json  # noqa: E402

_DEFAULT_FAMILY_INVENTORY_PATH = (
    PROJECT_ROOT
    / "data"
    / "examples"
    / "industrial_planner"
    / "checked_artifact_family_inventory.json"
)

_SUPPORT_RESULT_BUILDER = (
    "scripts.audit_industrial_planner_full_demand_support_suite_inventory:"
    "build_full_demand_support_suite_inventory_result"
)
_OUTER_RESULT_BUILDER = (
    "scripts.audit_industrial_planner_outer_base_bundle_suite:"
    "build_outer_base_bundle_suite_result"
)


@dataclass(frozen=True)
class CheckedArtifactFamilyInventoryEntry:
    family_id: str
    family_label: str
    inventory_path: Path
    result_builder: str
    scope_label_singular: str
    checked_scope_count_attr: str
    clean_scope_count_attr: str
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "family_id": self.family_id,
            "family_label": self.family_label,
            "inventory_path": str(self.inventory_path),
            "result_builder": self.result_builder,
            "scope_label_singular": self.scope_label_singular,
            "checked_scope_count_attr": self.checked_scope_count_attr,
            "clean_scope_count_attr": self.clean_scope_count_attr,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class CheckedArtifactFamilyEntryResult:
    inventory_entry: CheckedArtifactFamilyInventoryEntry
    family_result: Any

    @property
    def family_id(self) -> str:
        return self.inventory_entry.family_id

    @property
    def family_label(self) -> str:
        return self.inventory_entry.family_label

    @property
    def inventory_path(self) -> Path:
        return self.inventory_entry.inventory_path

    @property
    def result_builder(self) -> str:
        return self.inventory_entry.result_builder

    @property
    def scope_label_singular(self) -> str:
        return self.inventory_entry.scope_label_singular

    @property
    def checked_scope_count(self) -> int:
        return int(getattr(self.family_result, self.inventory_entry.checked_scope_count_attr))

    @property
    def clean_scope_count(self) -> int:
        return int(getattr(self.family_result, self.inventory_entry.clean_scope_count_attr))

    @property
    def drift_scope_count(self) -> int:
        return self.checked_scope_count - self.clean_scope_count

    @property
    def checked_file_count(self) -> int:
        return int(self.family_result.checked_file_count)

    @property
    def drift_entry_count(self) -> int:
        return int(self.family_result.drift_entry_count)

    @property
    def is_clean(self) -> bool:
        return bool(self.family_result.is_clean)

    @property
    def scope_units_text(self) -> str:
        count = self.checked_scope_count
        label = self.scope_label_singular if count == 1 else f"{self.scope_label_singular}s"
        return f"{count} {label}"

    @property
    def console_lines(self) -> tuple[str, ...]:
        console_text = str(self.family_result.to_console_text()).rstrip()
        if not console_text:
            return ()
        return tuple(console_text.splitlines())

    def to_dict(self) -> dict[str, Any]:
        return {
            "inventory_entry": self.inventory_entry.to_dict(),
            "family_summary": {
                "checked_scope_count": self.checked_scope_count,
                "clean_scope_count": self.clean_scope_count,
                "drift_scope_count": self.drift_scope_count,
                "checked_file_count": self.checked_file_count,
                "drift_entry_count": self.drift_entry_count,
                "is_clean": self.is_clean,
            },
            "family_result": self.family_result.to_dict(),
        }


@dataclass(frozen=True)
class IndustrialPlannerCheckedArtifactSuiteResult:
    family_inventory_path: Path | None
    entries: tuple[CheckedArtifactFamilyEntryResult, ...]

    @property
    def checked_family_count(self) -> int:
        return len(self.entries)

    @property
    def checked_suite_count(self) -> int:
        return self.checked_family_count

    @property
    def clean_family_count(self) -> int:
        return sum(1 for entry in self.entries if entry.is_clean)

    @property
    def clean_suite_count(self) -> int:
        return self.clean_family_count

    @property
    def drift_family_count(self) -> int:
        return self.checked_family_count - self.clean_family_count

    @property
    def drift_suite_count(self) -> int:
        return self.drift_family_count

    @property
    def checked_file_count(self) -> int:
        return sum(entry.checked_file_count for entry in self.entries)

    @property
    def drift_entry_count(self) -> int:
        return sum(entry.drift_entry_count for entry in self.entries)

    @property
    def is_clean(self) -> bool:
        return self.clean_family_count == self.checked_family_count

    @property
    def support_suite_result(self) -> Any | None:
        for entry in self.entries:
            if entry.result_builder == _SUPPORT_RESULT_BUILDER:
                return entry.family_result
        return None

    @property
    def outer_bundle_suite_result(self) -> Any | None:
        for entry in self.entries:
            if entry.result_builder == _OUTER_RESULT_BUILDER:
                return entry.family_result
        return None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "summary": {
                "checked_family_count": self.checked_family_count,
                "clean_family_count": self.clean_family_count,
                "drift_family_count": self.drift_family_count,
                "checked_suite_count": self.checked_suite_count,
                "clean_suite_count": self.clean_suite_count,
                "drift_suite_count": self.drift_suite_count,
                "checked_file_count": self.checked_file_count,
                "drift_entry_count": self.drift_entry_count,
                "is_clean": self.is_clean,
            },
            "family_inventory_path": (
                str(self.family_inventory_path) if self.family_inventory_path is not None else None
            ),
            "families": [entry.to_dict() for entry in self.entries],
        }
        support_suite_result = self.support_suite_result
        if support_suite_result is not None:
            payload["support_suite"] = support_suite_result.to_dict()
        outer_bundle_suite_result = self.outer_bundle_suite_result
        if outer_bundle_suite_result is not None:
            payload["outer_bundle_suite"] = outer_bundle_suite_result.to_dict()
        return payload

    def to_markdown(self) -> str:
        lines = [
            "# IndustrialPlanner Checked Artifact Suite",
            "",
            "This report is a repo-level no-drift gate driven by a checked-in checked-artifact family inventory. The current active inventory is intentionally minimal and points at the single full-demand support-suite family, while dormant future-scope families can stay preserved without re-entering the active CI gate.",
            "",
        ]
        if self.family_inventory_path is not None:
            lines.append(f"- Family inventory: `{self.family_inventory_path}`")
        else:
            lines.append("- Family inventory: `(legacy explicit support/outer targets)`")
        lines.extend(
            [
                f"- Families checked: {self.checked_family_count}",
                f"- Families clean: {self.clean_family_count}",
                f"- Files checked: {self.checked_file_count}",
                f"- Drift entries: {self.drift_entry_count}",
                f"- Overall status: `{'clean' if self.is_clean else 'drift_detected'}`",
                "",
                "## Family summary",
                "",
                "| Family | Label | Inventory | Scope units | Status | Files checked | Drift entries |",
                "|---|---|---|---:|---|---:|---:|",
            ]
        )
        for entry in self.entries:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{entry.family_id}`",
                        entry.family_label,
                        f"`{entry.inventory_path}`",
                        entry.scope_units_text,
                        f"`{'clean' if entry.is_clean else 'drift_detected'}`",
                        str(entry.checked_file_count),
                        str(entry.drift_entry_count),
                    ]
                )
                + " |"
            )

        drift_entries = [entry for entry in self.entries if not entry.is_clean]
        if drift_entries:
            lines.extend(["", "## Drift details", ""])
            for entry in drift_entries:
                lines.extend(
                    [
                        f"### `{entry.family_id}`",
                        "",
                        f"- Label: {entry.family_label}",
                        f"- Inventory: `{entry.inventory_path}`",
                        f"- Builder: `{entry.result_builder}`",
                        f"- Status: `{'clean' if entry.is_clean else 'drift_detected'}`",
                        "",
                        "```text",
                    ]
                )
                lines.extend(entry.console_lines)
                lines.extend(["```", ""])

        lines.extend(
            [
                "## Operational notes",
                "",
                "- The family inventory is an inventory-of-inventories: each entry names one checked-artifact family, points at that family's own inventory file, and names the result builder that can regenerate/check it.",
                "- That means adding more support-report sets or more outer-deployment bundles still happens in the family-specific inventories, while adding a brand-new checked-artifact family now mostly becomes a family-inventory change plus that family's own suite implementation instead of another round of repo-level gate rewiring.",
                "- This workflow stays postprocess-only and does not widen canonical truth or the certified proof boundary.",
            ]
        )
        return "\n".join(lines)

    def to_console_text(self) -> str:
        location_text = (
            f" via {self.family_inventory_path}" if self.family_inventory_path is not None else ""
        )
        if self.is_clean:
            return (
                f"IndustrialPlanner checked artifact suite is in sync{location_text} "
                f"({self.checked_family_count} families, {self.checked_file_count} files checked)"
            )
        lines = [
            (
                f"IndustrialPlanner checked artifact drift detected{location_text}: {self.drift_entry_count} issue"
                f"{'s' if self.drift_entry_count != 1 else ''} across {self.checked_family_count} families"
            )
        ]
        for entry in self.entries:
            lines.append(
                f"- {entry.family_id}: {'clean' if entry.is_clean else 'drift_detected'} ({entry.family_label})"
            )
            if entry.is_clean:
                continue
            for nested_line in entry.console_lines:
                lines.append(f"  {nested_line}")
        return "\n".join(lines)


def _resolve_inventory_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def _load_result_builder(target: str) -> Callable[..., Any]:
    module_name, separator, attribute_name = target.partition(":")
    if not separator or not module_name.strip() or not attribute_name.strip():
        raise ValueError(
            f"checked-artifact family result_builder '{target}' must use 'module.submodule:function_name' syntax"
        )
    module = importlib.import_module(module_name)
    builder = getattr(module, attribute_name, None)
    if builder is None or not callable(builder):
        raise ValueError(
            f"checked-artifact family result_builder '{target}' did not resolve to a callable"
        )
    return builder


def load_checked_artifact_family_inventory(
    inventory_path: Path = _DEFAULT_FAMILY_INVENTORY_PATH,
) -> tuple[CheckedArtifactFamilyInventoryEntry, ...]:
    import json

    resolved_inventory_path = Path(inventory_path)
    payload = json.loads(resolved_inventory_path.read_text(encoding="utf-8"))
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("checked-artifact family inventory must contain a non-empty 'entries' list")

    seen_family_ids: set[str] = set()
    entries: list[CheckedArtifactFamilyInventoryEntry] = []
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"checked-artifact family inventory entry {index} must be an object")
        family_id = str(raw_entry.get("family_id", "")).strip()
        family_label = str(raw_entry.get("family_label", "")).strip()
        inventory_raw = raw_entry.get("inventory_path")
        result_builder = str(raw_entry.get("result_builder", "")).strip()
        scope_label_singular = str(raw_entry.get("scope_label_singular", "")).strip()
        checked_scope_count_attr = str(raw_entry.get("checked_scope_count_attr", "")).strip()
        clean_scope_count_attr = str(raw_entry.get("clean_scope_count_attr", "")).strip()
        if not family_id:
            raise ValueError(f"checked-artifact family inventory entry {index} is missing family_id")
        if family_id in seen_family_ids:
            raise ValueError(f"duplicate checked-artifact family inventory family_id '{family_id}'")
        if not family_label:
            raise ValueError(
                f"checked-artifact family inventory entry {index} is missing family_label"
            )
        if not inventory_raw:
            raise ValueError(
                f"checked-artifact family inventory entry {index} is missing inventory_path"
            )
        if not result_builder:
            raise ValueError(
                f"checked-artifact family inventory entry {index} is missing result_builder"
            )
        if not scope_label_singular:
            raise ValueError(
                f"checked-artifact family inventory entry {index} is missing scope_label_singular"
            )
        if not checked_scope_count_attr:
            raise ValueError(
                f"checked-artifact family inventory entry {index} is missing checked_scope_count_attr"
            )
        if not clean_scope_count_attr:
            raise ValueError(
                f"checked-artifact family inventory entry {index} is missing clean_scope_count_attr"
            )
        seen_family_ids.add(family_id)
        inventory_file_path = _resolve_inventory_path(str(inventory_raw))
        notes = tuple(str(note) for note in raw_entry.get("notes", []) if str(note).strip())
        entries.append(
            CheckedArtifactFamilyInventoryEntry(
                family_id=family_id,
                family_label=family_label,
                inventory_path=inventory_file_path,
                result_builder=result_builder,
                scope_label_singular=scope_label_singular,
                checked_scope_count_attr=checked_scope_count_attr,
                clean_scope_count_attr=clean_scope_count_attr,
                notes=notes,
            )
        )
    return tuple(entries)


def _build_family_entry_result(
    inventory_entry: CheckedArtifactFamilyInventoryEntry,
) -> CheckedArtifactFamilyEntryResult:
    builder = _load_result_builder(inventory_entry.result_builder)
    family_result = builder(inventory_path=inventory_entry.inventory_path)
    missing_attrs = [
        attribute_name
        for attribute_name in (
            inventory_entry.checked_scope_count_attr,
            inventory_entry.clean_scope_count_attr,
            "checked_file_count",
            "drift_entry_count",
            "is_clean",
            "to_dict",
            "to_console_text",
        )
        if not hasattr(family_result, attribute_name)
    ]
    if missing_attrs:
        raise ValueError(
            f"checked-artifact family '{inventory_entry.family_id}' result is missing required attributes: "
            + ", ".join(sorted(missing_attrs))
        )
    return CheckedArtifactFamilyEntryResult(
        inventory_entry=inventory_entry,
        family_result=family_result,
    )


def _legacy_family_entries(
    *,
    support_inventory_path: Path,
    outer_inventory_path: Path,
) -> tuple[CheckedArtifactFamilyInventoryEntry, ...]:
    return (
        CheckedArtifactFamilyInventoryEntry(
            family_id="full_demand_support_suite",
            family_label="IndustrialPlanner full-demand support report sets",
            inventory_path=Path(support_inventory_path),
            result_builder=_SUPPORT_RESULT_BUILDER,
            scope_label_singular="report set",
            checked_scope_count_attr="checked_report_set_count",
            clean_scope_count_attr="clean_report_set_count",
            notes=(
                "legacy explicit support inventory target synthesized by the repo-level gate",
            ),
        ),
        CheckedArtifactFamilyInventoryEntry(
            family_id="outer_base_bundle_suite",
            family_label="IndustrialPlanner outer-deployment bundles",
            inventory_path=Path(outer_inventory_path),
            result_builder=_OUTER_RESULT_BUILDER,
            scope_label_singular="bundle",
            checked_scope_count_attr="checked_bundle_count",
            clean_scope_count_attr="clean_bundle_count",
            notes=(
                "legacy explicit outer inventory target synthesized by the repo-level gate",
            ),
        ),
    )


def build_checked_artifact_suite_result(
    *,
    family_inventory_path: Path | None = None,
    support_inventory_path: Path | None = None,
    outer_inventory_path: Path | None = None,
) -> IndustrialPlannerCheckedArtifactSuiteResult:
    if family_inventory_path is not None and (
        support_inventory_path is not None or outer_inventory_path is not None
    ):
        raise ValueError(
            "family_inventory_path cannot be combined with legacy support_inventory_path/outer_inventory_path"
        )
    if family_inventory_path is None and (support_inventory_path is None) != (outer_inventory_path is None):
        raise ValueError(
            "support_inventory_path and outer_inventory_path must both be provided when using legacy mode"
        )

    resolved_family_inventory_path: Path | None = family_inventory_path
    if (
        resolved_family_inventory_path is None
        and support_inventory_path is None
        and outer_inventory_path is None
    ):
        resolved_family_inventory_path = _DEFAULT_FAMILY_INVENTORY_PATH

    if resolved_family_inventory_path is not None:
        inventory_entries = load_checked_artifact_family_inventory(resolved_family_inventory_path)
    else:
        inventory_entries = _legacy_family_entries(
            support_inventory_path=Path(support_inventory_path or _DEFAULT_SUPPORT_INVENTORY),
            outer_inventory_path=Path(outer_inventory_path or _DEFAULT_OUTER_BUNDLE_INVENTORY),
        )

    entry_results = tuple(_build_family_entry_result(entry) for entry in inventory_entries)
    return IndustrialPlannerCheckedArtifactSuiteResult(
        family_inventory_path=resolved_family_inventory_path,
        entries=entry_results,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the repo-level IndustrialPlanner checked-artifact gate: validate every checked-artifact family listed "
            "in the family inventory (or, for legacy callers, the explicitly provided support/outer inventories)."
        )
    )
    parser.add_argument(
        "--family-inventory",
        default=None,
        help=(
            "Checked-artifact family inventory JSON. Each entry points at a family-specific inventory-driven workflow. "
            f"Defaults to {str(_DEFAULT_FAMILY_INVENTORY_PATH)} when no legacy support/outer inventories are provided."
        ),
    )
    parser.add_argument(
        "--support-inventory",
        default=None,
        help="Legacy explicit support-suite inventory path. Must be paired with --outer-inventory.",
    )
    parser.add_argument(
        "--outer-inventory",
        default=None,
        help="Legacy explicit outer-bundle inventory path. Must be paired with --support-inventory.",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional path for a machine-readable suite summary JSON sidecar.",
    )
    parser.add_argument(
        "--markdown-output",
        default=None,
        help="Optional path for a human-readable suite summary Markdown sidecar.",
    )
    parser.add_argument(
        "--console-output",
        default=None,
        help="Optional path for a plain-text console summary copy that CI can upload directly.",
    )
    args = parser.parse_args()

    if args.family_inventory and (args.support_inventory or args.outer_inventory):
        parser.error("--family-inventory cannot be combined with --support-inventory/--outer-inventory")
    if bool(args.support_inventory) != bool(args.outer_inventory):
        parser.error("--support-inventory and --outer-inventory must be provided together")

    result = build_checked_artifact_suite_result(
        family_inventory_path=(Path(args.family_inventory) if args.family_inventory else None),
        support_inventory_path=(Path(args.support_inventory) if args.support_inventory else None),
        outer_inventory_path=(Path(args.outer_inventory) if args.outer_inventory else None),
    )

    if args.json_output:
        atomic_write_json(Path(args.json_output), result.to_dict())
    if args.markdown_output:
        markdown_path = Path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(result.to_markdown(), encoding="utf-8")

    console_text = result.to_console_text()
    if args.console_output:
        console_path = Path(args.console_output)
        console_path.parent.mkdir(parents=True, exist_ok=True)
        console_path.write_text(console_text + "\n", encoding="utf-8")

    print(console_text)
    if not result.is_clean:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
