"""Regenerate or validate one preserved future-scope IndustrialPlanner outer-deployment bundle."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.adapters.base_planner.outer_deployment_plan import build_outer_base_deployment_plan  # noqa: E402
from src.adapters.industrial_planner.export_blueprint import build_industrial_planner_export_bundle  # noqa: E402
from src.adapters.industrial_planner.outer_export_probe import probe_outer_deployment_plan  # noqa: E402
from src.search.exact_campaign import atomic_write_json  # noqa: E402

_DEFAULT_BLUEPRINT = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "full_demand_recipe_capacity_canonical_blueprint.json"
)
_DEFAULT_BASE_ID = "wuling_protocol_core"
_DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "data" / "examples" / "industrial_planner" / "generated_outer_base_bundle"
)

_PLAN_JSON_NAME = "outer_deployment_plan.json"
_PLAN_MARKDOWN_NAME = "outer_deployment_plan.md"
_PROBE_JSON_NAME = "outer_export_probe.json"
_PROBE_MARKDOWN_NAME = "outer_export_probe.md"
_OUTER_EXPORT_BLUEPRINT_JSON_NAME = "outer_export.blueprint.json"
_TARGET_BLUEPRINT_JSON_NAME = "industrial_planner.blueprint.json"
_COMPATIBILITY_MANIFEST_JSON_NAME = "industrial_planner.compatibility_manifest.json"
_VALIDATION_JSON_NAME = "validation_report.json"
_VALIDATION_MARKDOWN_NAME = "validation_report.md"
_THROUGHPUT_JSON_NAME = "throughput_report.json"
_THROUGHPUT_MARKDOWN_NAME = "throughput_report.md"


@dataclass(frozen=True)
class OuterBaseBundleArtifacts:
    base_id: str
    blueprint_path: Path
    deployment_plan: Any
    probe_bundle: Any
    export_bundle: Mapping[str, Any]

    @property
    def validator_import_compatible(self) -> bool | None:
        return self.export_bundle.get("validation_report", {}).get("is_import_compatible")

    @property
    def validator_layout_healthy(self) -> bool | None:
        return self.export_bundle.get("validation_report", {}).get("is_layout_healthy")

    @property
    def throughput_status(self) -> str | None:
        return self.export_bundle.get("throughput_report", {}).get("status")

    @property
    def translated_mapping_count(self) -> int:
        return sum(
            1
            for entry in self.deployment_plan.export_mappings
            if str(getattr(entry, "mapping_mode", "identity")) != "identity"
        )

    @property
    def deployment_kind(self) -> str:
        return (
            "translated_outer_deployment"
            if self.translated_mapping_count > 0
            else "identity_outer_deployment"
        )


@dataclass(frozen=True)
class OuterBaseBundleDriftEntry:
    filename: str
    drift_kind: str


@dataclass(frozen=True)
class OuterBaseBundleCheckResult:
    output_dir: Path
    base_id: str
    checked_file_count: int
    drift_entries: tuple[OuterBaseBundleDriftEntry, ...] = ()
    validator_import_compatible: bool | None = None
    validator_layout_healthy: bool | None = None
    throughput_status: str | None = None
    deployment_kind: str | None = None

    @property
    def is_clean(self) -> bool:
        return not self.drift_entries

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": str(self.output_dir),
            "base_id": self.base_id,
            "checked_file_count": self.checked_file_count,
            "is_clean": self.is_clean,
            "validator_import_compatible": self.validator_import_compatible,
            "validator_layout_healthy": self.validator_layout_healthy,
            "throughput_status": self.throughput_status,
            "deployment_kind": self.deployment_kind,
            "drift_entries": [
                {"filename": entry.filename, "drift_kind": entry.drift_kind}
                for entry in self.drift_entries
            ],
        }

    def to_markdown(self) -> str:
        lines = [
            "# IndustrialPlanner Outer Base Bundle Check",
            "",
            f"- Base id: `{self.base_id}`",
            f"- Output directory: `{self.output_dir}`",
            f"- Files checked: {self.checked_file_count}",
            f"- Check status: `{'clean' if self.is_clean else 'drift_detected'}`",
        ]
        if self.deployment_kind is not None:
            lines.append(f"- Deployment kind: `{self.deployment_kind}`")
        if self.throughput_status is not None:
            lines.append(f"- Throughput status: `{self.throughput_status}`")
        if self.validator_import_compatible is not None and self.validator_layout_healthy is not None:
            lines.append(
                "- Validator import/layout: "
                f"{self.validator_import_compatible}/{self.validator_layout_healthy}"
            )
        if self.drift_entries:
            lines.extend(["", "## Drift entries", ""])
            for entry in self.drift_entries:
                lines.append(f"- `{entry.drift_kind}`: `{entry.filename}`")
        return "\n".join(lines)

    def to_console_text(self) -> str:
        if self.is_clean:
            return (
                f"outer base bundle is in sync under {self.output_dir} "
                f"for {self.base_id} ({self.checked_file_count} files checked)"
            )
        lines = [
            (
                f"outer base bundle drift detected under {self.output_dir} for {self.base_id}: "
                f"{len(self.drift_entries)} of {self.checked_file_count} files need refresh"
            )
        ]
        for entry in self.drift_entries:
            lines.append(f"- {entry.drift_kind}: {entry.filename}")
        lines.append(
            "regenerate with: "
            f"python scripts/audit_industrial_planner_outer_base_bundle.py --base-id {self.base_id} --output-dir {self.output_dir}"
        )
        return "\n".join(lines)


def _render_json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


def build_outer_base_bundle_artifacts(
    *,
    blueprint_path: Path = _DEFAULT_BLUEPRINT,
    base_id: str = _DEFAULT_BASE_ID,
) -> OuterBaseBundleArtifacts:
    blueprint_payload = json.loads(Path(blueprint_path).read_text(encoding="utf-8"))
    deployment_plan = build_outer_base_deployment_plan(
        blueprint_payload=blueprint_payload,
        base_id=str(base_id),
    )
    probe_bundle = probe_outer_deployment_plan(
        blueprint_payload=blueprint_payload,
        deployment_plan=deployment_plan,
    )
    export_bundle = build_industrial_planner_export_bundle(
        blueprint_payload=blueprint_payload,
        deployment_plan=deployment_plan,
    )
    return OuterBaseBundleArtifacts(
        base_id=str(base_id),
        blueprint_path=Path(blueprint_path),
        deployment_plan=deployment_plan,
        probe_bundle=probe_bundle,
        export_bundle=export_bundle,
    )


def _render_outer_base_bundle_output_texts(
    *,
    artifacts: OuterBaseBundleArtifacts,
) -> dict[str, str]:
    export_bundle = artifacts.export_bundle
    return {
        _PLAN_JSON_NAME: _render_json_text(artifacts.deployment_plan.to_dict()),
        _PLAN_MARKDOWN_NAME: artifacts.deployment_plan.to_markdown(),
        _PROBE_JSON_NAME: _render_json_text(artifacts.probe_bundle.to_dict()),
        _PROBE_MARKDOWN_NAME: artifacts.probe_bundle.to_markdown(),
        _OUTER_EXPORT_BLUEPRINT_JSON_NAME: _render_json_text(artifacts.probe_bundle.export_blueprint),
        _TARGET_BLUEPRINT_JSON_NAME: _render_json_text(export_bundle["blueprint"]),
        _COMPATIBILITY_MANIFEST_JSON_NAME: _render_json_text(export_bundle["compatibility_manifest"]),
        _VALIDATION_JSON_NAME: _render_json_text(export_bundle["validation_report"]),
        _VALIDATION_MARKDOWN_NAME: str(export_bundle["validation_report_markdown"]),
        _THROUGHPUT_JSON_NAME: _render_json_text(export_bundle["throughput_report"]),
        _THROUGHPUT_MARKDOWN_NAME: str(export_bundle["throughput_report_markdown"]),
    }


def check_outer_base_bundle_outputs(
    *,
    output_dir: Path,
    artifacts: OuterBaseBundleArtifacts,
) -> OuterBaseBundleCheckResult:
    expected_outputs = _render_outer_base_bundle_output_texts(artifacts=artifacts)
    drift_entries: list[OuterBaseBundleDriftEntry] = []
    for filename, expected_text in expected_outputs.items():
        output_path = output_dir / filename
        if not output_path.exists():
            drift_entries.append(OuterBaseBundleDriftEntry(filename=filename, drift_kind="missing"))
            continue
        actual_text = output_path.read_text(encoding="utf-8")
        if actual_text != expected_text:
            drift_entries.append(
                OuterBaseBundleDriftEntry(filename=filename, drift_kind="content_mismatch")
            )
    return OuterBaseBundleCheckResult(
        output_dir=output_dir,
        base_id=artifacts.base_id,
        checked_file_count=len(expected_outputs),
        drift_entries=tuple(drift_entries),
        validator_import_compatible=artifacts.validator_import_compatible,
        validator_layout_healthy=artifacts.validator_layout_healthy,
        throughput_status=artifacts.throughput_status,
        deployment_kind=artifacts.deployment_kind,
    )


def write_outer_base_bundle_outputs(
    *,
    output_dir: Path,
    artifacts: OuterBaseBundleArtifacts,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_texts = _render_outer_base_bundle_output_texts(artifacts=artifacts)
    paths = {
        "deployment_plan_json": output_dir / _PLAN_JSON_NAME,
        "deployment_plan_markdown": output_dir / _PLAN_MARKDOWN_NAME,
        "probe_json": output_dir / _PROBE_JSON_NAME,
        "probe_markdown": output_dir / _PROBE_MARKDOWN_NAME,
        "outer_export_blueprint_json": output_dir / _OUTER_EXPORT_BLUEPRINT_JSON_NAME,
        "target_blueprint_json": output_dir / _TARGET_BLUEPRINT_JSON_NAME,
        "compatibility_manifest_json": output_dir / _COMPATIBILITY_MANIFEST_JSON_NAME,
        "validation_json": output_dir / _VALIDATION_JSON_NAME,
        "validation_markdown": output_dir / _VALIDATION_MARKDOWN_NAME,
        "throughput_json": output_dir / _THROUGHPUT_JSON_NAME,
        "throughput_markdown": output_dir / _THROUGHPUT_MARKDOWN_NAME,
    }
    for key, output_path in paths.items():
        text = output_texts[output_path.name]
        if output_path.suffix == ".json":
            atomic_write_json(output_path, json.loads(text))
        else:
            output_path.write_text(text, encoding="utf-8")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Regenerate or validate one preserved future-scope IndustrialPlanner outer-deployment bundle "
            "(plan, probe, target export, compatibility manifest, validator, throughput)."
        )
    )
    parser.add_argument(
        "blueprint",
        nargs="?",
        default=str(_DEFAULT_BLUEPRINT),
        help="Canonical blueprint JSON used as the inner-island truth.",
    )
    parser.add_argument(
        "--base-id",
        default=_DEFAULT_BASE_ID,
        help=f"IndustrialPlanner base id to deploy into. Defaults to '{_DEFAULT_BASE_ID}'.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Optional directory for the outer bundle outputs. In --check mode this becomes the comparison target; "
            f"when omitted there, the default checked-in example directory {_DEFAULT_OUTPUT_DIR} is used."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "No-drift mode. Rebuild the preserved future-scope outer bundle in memory, compare it against the target directory, "
            "and exit non-zero if any required artifact is missing or stale."
        ),
    )
    parser.add_argument(
        "--check-json-output",
        default=None,
        help="Optional path for a machine-readable check-result JSON sidecar. Valid with --check only.",
    )
    parser.add_argument(
        "--check-markdown-output",
        default=None,
        help="Optional path for a human-readable check-result Markdown sidecar. Valid with --check only.",
    )
    args = parser.parse_args()

    if not args.check and (args.check_json_output or args.check_markdown_output):
        parser.error("--check-json-output/--check-markdown-output require --check")

    artifacts = build_outer_base_bundle_artifacts(
        blueprint_path=Path(args.blueprint),
        base_id=str(args.base_id),
    )

    if args.check:
        check_output_dir = Path(args.output_dir) if args.output_dir else _DEFAULT_OUTPUT_DIR
        check_result = check_outer_base_bundle_outputs(
            output_dir=check_output_dir,
            artifacts=artifacts,
        )
        if args.check_json_output:
            atomic_write_json(Path(args.check_json_output), check_result.to_dict())
        if args.check_markdown_output:
            markdown_path = Path(args.check_markdown_output)
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(check_result.to_markdown(), encoding="utf-8")
        print(check_result.to_console_text())
        if not check_result.is_clean:
            raise SystemExit(1)
        return

    output_dir = Path(args.output_dir) if args.output_dir else _DEFAULT_OUTPUT_DIR
    write_outer_base_bundle_outputs(output_dir=output_dir, artifacts=artifacts)
    print(f"outer base bundle written: {output_dir}")
    print(f"base id: {artifacts.base_id}")
    print(
        "validator import/layout: "
        f"{artifacts.validator_import_compatible}/{artifacts.validator_layout_healthy}"
    )
    print(f"throughput status: {artifacts.throughput_status}")


if __name__ == "__main__":
    main()
