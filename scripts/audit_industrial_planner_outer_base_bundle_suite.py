"""Inventory-driven regeneration/check workflow for preserved future-scope IndustrialPlanner outer bundles."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.audit_industrial_planner_outer_base_bundle import (  # noqa: E402
    build_outer_base_bundle_artifacts,
    check_outer_base_bundle_outputs,
    write_outer_base_bundle_outputs,
)
from src.search.exact_campaign import atomic_write_json  # noqa: E402

_DEFAULT_INVENTORY_PATH = PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "outer_base_bundle_inventory.json"


@dataclass(frozen=True)
class OuterBaseBundleInventoryEntry:
    bundle_id: str
    base_id: str
    blueprint_path: Path
    output_dir: Path
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "base_id": self.base_id,
            "blueprint_path": str(self.blueprint_path),
            "output_dir": str(self.output_dir),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class OuterBaseBundleSuiteEntryResult:
    inventory_entry: OuterBaseBundleInventoryEntry
    check_result: Any

    @property
    def bundle_id(self) -> str:
        return self.inventory_entry.bundle_id

    @property
    def base_id(self) -> str:
        return self.inventory_entry.base_id

    @property
    def blueprint_path(self) -> Path:
        return self.inventory_entry.blueprint_path

    @property
    def output_dir(self) -> Path:
        return self.inventory_entry.output_dir

    @property
    def notes(self) -> tuple[str, ...]:
        return self.inventory_entry.notes

    def to_dict(self) -> dict[str, Any]:
        return {
            "inventory_entry": self.inventory_entry.to_dict(),
            "check_result": self.check_result.to_dict(),
        }


@dataclass(frozen=True)
class OuterBaseBundleSuiteResult:
    inventory_path: Path
    entries: tuple[OuterBaseBundleSuiteEntryResult, ...]

    @property
    def checked_bundle_count(self) -> int:
        return len(self.entries)

    @property
    def clean_bundle_count(self) -> int:
        return sum(1 for entry in self.entries if entry.check_result.is_clean)

    @property
    def checked_file_count(self) -> int:
        return sum(int(entry.check_result.checked_file_count) for entry in self.entries)

    @property
    def drift_entry_count(self) -> int:
        return sum(len(entry.check_result.drift_entries) for entry in self.entries)

    @property
    def proven_equivalent_bundle_count(self) -> int:
        return sum(1 for entry in self.entries if entry.check_result.throughput_status == "proven_equivalent")

    @property
    def validator_clean_bundle_count(self) -> int:
        return sum(
            1
            for entry in self.entries
            if entry.check_result.validator_import_compatible is True
            and entry.check_result.validator_layout_healthy is True
        )

    @property
    def translated_outer_bundle_count(self) -> int:
        return sum(
            1
            for entry in self.entries
            if entry.check_result.deployment_kind == "translated_outer_deployment"
        )

    @property
    def identity_outer_bundle_count(self) -> int:
        return sum(
            1
            for entry in self.entries
            if entry.check_result.deployment_kind == "identity_outer_deployment"
        )

    @property
    def is_clean(self) -> bool:
        return self.clean_bundle_count == self.checked_bundle_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "checked_bundle_count": self.checked_bundle_count,
                "clean_bundle_count": self.clean_bundle_count,
                "drift_bundle_count": self.checked_bundle_count - self.clean_bundle_count,
                "checked_file_count": self.checked_file_count,
                "drift_entry_count": self.drift_entry_count,
                "validator_clean_bundle_count": self.validator_clean_bundle_count,
                "proven_equivalent_bundle_count": self.proven_equivalent_bundle_count,
                "translated_outer_bundle_count": self.translated_outer_bundle_count,
                "identity_outer_bundle_count": self.identity_outer_bundle_count,
                "is_clean": self.is_clean,
            },
            "inventory_path": str(self.inventory_path),
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def to_markdown(self) -> str:
        lines = [
            "# IndustrialPlanner Outer Base Bundle Suite",
            "",
            "This inventory-driven workflow rechecks preserved future-scope IndustrialPlanner outer-deployment examples listed in the outer bundle inventory. The suite remains available for later reactivation, but it is intentionally outside the active single-base CI gate.",
            "",
            f"- Inventory: `{self.inventory_path}`",
            f"- Bundles checked: {self.checked_bundle_count}",
            f"- Bundles clean: {self.clean_bundle_count}",
            f"- Files checked: {self.checked_file_count}",
            f"- Drift entries: {self.drift_entry_count}",
            f"- Validator-clean bundles: {self.validator_clean_bundle_count}",
            f"- `proven_equivalent` bundles: {self.proven_equivalent_bundle_count}",
            f"- Translated outer bundles: {self.translated_outer_bundle_count}",
            f"- Identity outer bundles: {self.identity_outer_bundle_count}",
            f"- Overall status: `{'clean' if self.is_clean else 'drift_detected'}`",
            "",
            "## Bundle summary",
            "",
            "| Bundle | Base | Output dir | Status | Files | Deployment kind | Validator | Throughput |",
            "|---|---|---|---|---:|---|---|---|",
        ]
        for entry in self.entries:
            validator_text = "-"
            if (
                entry.check_result.validator_import_compatible is not None
                and entry.check_result.validator_layout_healthy is not None
            ):
                validator_text = (
                    f"{entry.check_result.validator_import_compatible}/"
                    f"{entry.check_result.validator_layout_healthy}"
                )
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{entry.bundle_id}`",
                        f"`{entry.base_id}`",
                        f"`{entry.output_dir}`",
                        f"`{'clean' if entry.check_result.is_clean else 'drift_detected'}`",
                        str(entry.check_result.checked_file_count),
                        f"`{entry.check_result.deployment_kind or '-'}`",
                        validator_text,
                        f"`{entry.check_result.throughput_status or '-'}`",
                    ]
                )
                + " |"
            )

        drift_entries = [entry for entry in self.entries if entry.check_result.drift_entries]
        if drift_entries:
            lines.extend(["", "## Drift details", ""])
            for entry in drift_entries:
                lines.append(f"### `{entry.bundle_id}`")
                lines.append("")
                lines.append(f"- Base id: `{entry.base_id}`")
                lines.append(f"- Output dir: `{entry.output_dir}`")
                for drift_entry in entry.check_result.drift_entries:
                    lines.append(f"- `{drift_entry.drift_kind}`: `{drift_entry.filename}`")
                lines.append("")

        lines.extend(
            [
                "## Operational notes",
                "",
                "- Each inventory entry reuses the existing single-bundle planner/probe/export/validator/throughput regeneration path.",
                "- The summary distinguishes true translated outer deployments from degenerate identity outer deployments, so mixed inventories can show whether they are really exercising larger-base geometry or just the zero-moat 70×70 path.",
                "- This suite stays postprocess-only: it validates checked-in outer-deployment examples without widening canonical truth or certified evidence.",
                "- This suite is preserved for later reactivation and is intentionally excluded from the active single-base checked-artifact gate.",
            ]
        )
        return "\n".join(lines)

    def to_console_text(self) -> str:
        if self.is_clean:
            return (
                f"outer base bundle suite is in sync via {self.inventory_path} "
                f"({self.checked_bundle_count} bundles, {self.checked_file_count} files checked)"
            )
        lines = [
            (
                f"outer base bundle suite drift detected via {self.inventory_path}: "
                f"{self.drift_entry_count} issue{'s' if self.drift_entry_count != 1 else ''} "
                f"across {self.checked_bundle_count} bundle{'s' if self.checked_bundle_count != 1 else ''}"
            )
        ]
        for entry in self.entries:
            if not entry.check_result.drift_entries:
                continue
            lines.append(
                f"- {entry.bundle_id}: {'clean' if entry.check_result.is_clean else 'drift_detected'}"
            )
            for drift_entry in entry.check_result.drift_entries:
                lines.append(f"  - {drift_entry.drift_kind}: {drift_entry.filename}")
        lines.append(
            "regenerate with: "
            f"python scripts/audit_industrial_planner_outer_base_bundle_suite.py --inventory {self.inventory_path}"
        )
        return "\n".join(lines)


def _resolve_inventory_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def load_outer_base_bundle_inventory(
    inventory_path: Path = _DEFAULT_INVENTORY_PATH,
) -> tuple[OuterBaseBundleInventoryEntry, ...]:
    resolved_inventory_path = Path(inventory_path)
    payload = json.loads(resolved_inventory_path.read_text(encoding="utf-8"))
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError("outer bundle inventory must contain a non-empty 'entries' list")

    seen_bundle_ids: set[str] = set()
    entries: list[OuterBaseBundleInventoryEntry] = []
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"outer bundle inventory entry {index} must be an object")
        bundle_id = str(raw_entry.get("bundle_id", "")).strip()
        base_id = str(raw_entry.get("base_id", "")).strip()
        blueprint_raw = raw_entry.get("blueprint_path")
        output_raw = raw_entry.get("output_dir")
        if not bundle_id:
            raise ValueError(f"outer bundle inventory entry {index} is missing bundle_id")
        if bundle_id in seen_bundle_ids:
            raise ValueError(f"duplicate outer bundle inventory bundle_id '{bundle_id}'")
        if not base_id:
            raise ValueError(f"outer bundle inventory entry {index} is missing base_id")
        if not blueprint_raw:
            raise ValueError(f"outer bundle inventory entry {index} is missing blueprint_path")
        if not output_raw:
            raise ValueError(f"outer bundle inventory entry {index} is missing output_dir")
        seen_bundle_ids.add(bundle_id)
        blueprint_path = _resolve_inventory_path(str(blueprint_raw))
        output_dir = _resolve_inventory_path(str(output_raw))
        notes = tuple(str(note) for note in raw_entry.get("notes", []) if str(note).strip())
        entries.append(
            OuterBaseBundleInventoryEntry(
                bundle_id=bundle_id,
                base_id=base_id,
                blueprint_path=blueprint_path,
                output_dir=output_dir,
                notes=notes,
            )
        )
    return tuple(entries)


def build_outer_base_bundle_suite_result(
    *,
    inventory_path: Path = _DEFAULT_INVENTORY_PATH,
) -> OuterBaseBundleSuiteResult:
    entries = load_outer_base_bundle_inventory(inventory_path)
    entry_results: list[OuterBaseBundleSuiteEntryResult] = []
    for entry in entries:
        artifacts = build_outer_base_bundle_artifacts(
            blueprint_path=entry.blueprint_path,
            base_id=entry.base_id,
        )
        check_result = check_outer_base_bundle_outputs(
            output_dir=entry.output_dir,
            artifacts=artifacts,
        )
        entry_results.append(
            OuterBaseBundleSuiteEntryResult(
                inventory_entry=entry,
                check_result=check_result,
            )
        )
    return OuterBaseBundleSuiteResult(
        inventory_path=Path(inventory_path),
        entries=tuple(entry_results),
    )


def write_outer_base_bundle_suite_outputs(
    *,
    inventory_path: Path = _DEFAULT_INVENTORY_PATH,
) -> dict[str, dict[str, Path]]:
    entries = load_outer_base_bundle_inventory(inventory_path)
    output_paths: dict[str, dict[str, Path]] = {}
    for entry in entries:
        artifacts = build_outer_base_bundle_artifacts(
            blueprint_path=entry.blueprint_path,
            base_id=entry.base_id,
        )
        output_paths[entry.bundle_id] = write_outer_base_bundle_outputs(
            output_dir=entry.output_dir,
            artifacts=artifacts,
        )
    return output_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate or validate preserved future-scope IndustrialPlanner outer-base bundles listed in the inventory."
        )
    )
    parser.add_argument(
        "--inventory",
        default=str(_DEFAULT_INVENTORY_PATH),
        help="Inventory JSON listing the preserved future-scope outer-base bundle entries to refresh or validate.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "No-drift mode. Rebuild every inventory entry in memory, compare it against the listed output directories, "
            "and exit non-zero if any required outer-bundle artifact is missing or stale."
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
        result = build_outer_base_bundle_suite_result(inventory_path=inventory_path)
        if args.check_json_output:
            atomic_write_json(Path(args.check_json_output), result.to_dict())
        if args.check_markdown_output:
            markdown_path = Path(args.check_markdown_output)
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(result.to_markdown(), encoding="utf-8")
        console_text = result.to_console_text()
        if args.check_console_output:
            console_path = Path(args.check_console_output)
            console_path.parent.mkdir(parents=True, exist_ok=True)
            console_path.write_text(console_text + "\n", encoding="utf-8")
        print(console_text)
        if not result.is_clean:
            raise SystemExit(1)
        return

    output_paths = write_outer_base_bundle_suite_outputs(inventory_path=inventory_path)
    print(f"outer base bundle suite written via {inventory_path}")
    print(f"bundles written: {len(output_paths)}")
    for bundle_id, bundle_paths in sorted(output_paths.items()):
        sample_path = next(iter(bundle_paths.values()))
        print(f"- {bundle_id}: {sample_path.parent}")


if __name__ == "__main__":
    main()
