from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.exact_campaign_inspector import build_exact_campaign_inspection


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect certified exact campaign state without mutating solver evidence."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository/project root to inspect.",
    )
    parser.add_argument(
        "--campaign-state",
        type=Path,
        default=None,
        help="Campaign state JSON path. Defaults to data/checkpoints/exact_campaign_state.json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".artifacts/phase3b_exact_campaign_inspector/inspection_summary.json"),
        help="Inspection JSON output path.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the inspection summary but do not write the JSON report.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    inspection = build_exact_campaign_inspection(
        project_root=project_root,
        campaign_state_path=args.campaign_state,
    )
    _print_summary(inspection)
    if not args.no_write:
        output_path = _resolve_output_path(project_root, args.output)
        atomic_write_json(output_path, inspection)
        print(f"inspection_json={_display_path(project_root, output_path)}")
    return 0


def _print_summary(inspection: Mapping[str, Any]) -> None:
    campaign = _mapping(inspection.get("campaign"))
    telemetry = _mapping(inspection.get("telemetry"))
    delivery_manifest = _mapping(inspection.get("delivery_manifest"))
    checks = list(inspection.get("checks", []))
    failed_checks = [
        str(check.get("check_id", ""))
        for check in checks
        if isinstance(check, Mapping) and str(check.get("status", "")) == "fail"
    ]

    print("exact campaign inspection")
    print(f"- campaign present: {bool(campaign.get('present', False))}")
    print(f"- final status: {campaign.get('final_status')}")
    print(f"- last stop reason: {_reason_text(campaign.get('last_stop_reason'))}")
    print(
        "- resume compatible: "
        f"{bool(campaign.get('resume_compatible_with_current_hashes', False))}"
    )
    print(f"- resume validation reason: {campaign.get('resume_validation_reason')}")
    print(f"- candidate status counts: {campaign.get('candidate_status_counts')}")
    print(f"- telemetry present: {bool(telemetry.get('present', False))}")
    print(f"- telemetry waves: {telemetry.get('wave_count', 0)}")
    print(f"- delivery manifest present: {bool(delivery_manifest.get('present', False))}")
    print(f"- failed checks: {failed_checks}")


def _reason_text(value: Any) -> Any:
    if not isinstance(value, Mapping):
        return value
    return value.get("reason", value)


def _resolve_output_path(project_root: Path, output_path: Path) -> Path:
    output_path = Path(output_path)
    if output_path.is_absolute():
        return output_path.resolve()
    return (project_root / output_path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())
