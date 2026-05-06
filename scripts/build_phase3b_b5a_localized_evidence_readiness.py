from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_b5a_localized_evidence_readiness import (
    DEFAULT_GHOST_RUNTIME_PROBE_PATH,
    DEFAULT_POST_ACCEPTANCE_PREFLIGHT_PATH,
    DEFAULT_REASON_LOCALIZATION_PATH,
    DEFAULT_SIGNATURE_PRECEDENT_PATH,
    DEFAULT_SIGNATURE_RUNTIME_PROBE_PATH,
    build_phase3b_b5a_localized_evidence_readiness,
    write_phase3b_b5a_localized_evidence_readiness,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B B5A localized evidence readiness report."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--reason-localization",
        type=Path,
        default=DEFAULT_REASON_LOCALIZATION_PATH,
    )
    parser.add_argument(
        "--post-acceptance-preflight",
        type=Path,
        default=DEFAULT_POST_ACCEPTANCE_PREFLIGHT_PATH,
    )
    parser.add_argument(
        "--signature-runtime-probe",
        type=Path,
        default=DEFAULT_SIGNATURE_RUNTIME_PROBE_PATH,
    )
    parser.add_argument(
        "--ghost-runtime-probe",
        type=Path,
        default=DEFAULT_GHOST_RUNTIME_PROBE_PATH,
    )
    parser.add_argument(
        "--signature-precedent",
        type=Path,
        default=DEFAULT_SIGNATURE_PRECEDENT_PATH,
    )
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_b5a_localized_evidence_readiness_20260425"),
    )
    parser.add_argument("--output-prefix", default="b5a_localized_evidence_readiness")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_b5a_localized_evidence_readiness(
        project_root,
        reason_localization_path=args.reason_localization,
        post_acceptance_preflight_path=args.post_acceptance_preflight,
        signature_runtime_probe_path=args.signature_runtime_probe,
        ghost_runtime_probe_path=args.ghost_runtime_probe,
        signature_precedent_path=args.signature_precedent,
        expected_candidate=str(args.candidate),
    )
    _print_summary(report)
    if not bool(args.no_write):
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        paths = write_phase3b_b5a_localized_evidence_readiness(
            report,
            output_dir,
            output_prefix=str(args.output_prefix),
        )
        for key, value in paths.items():
            print(
                "b5a_localized_evidence_readiness_"
                f"{key}={_display_path(project_root, Path(value))}"
            )
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    failed = [
        str(check.get("check_id"))
        for check in list(report.get("checks", []))
        if isinstance(check, Mapping) and str(check.get("status")) == "fail"
    ]
    print("phase3b B5A localized evidence readiness")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- readiness ready: {bool(status.get('readiness_ready', False))}")
    print(f"- certified anchor found: {bool(status.get('certified_anchor_found', False))}")
    print(f"- proof_source: {bool(status.get('proof_source', False))}")
    print(
        "- runtime_semantics_changed: "
        f"{bool(status.get('runtime_semantics_changed', False))}"
    )
    for lane in list(report.get("lanes", [])):
        if isinstance(lane, Mapping):
            print(
                "- lane "
                f"{lane.get('lane_id')}: "
                f"covered={lane.get('covered_anchors')} "
                f"current_source_complete={lane.get('current_source_complete')} "
                f"probe_supports_lane={lane.get('probe_supports_lane')}"
            )
    if failed:
        print(f"- failed checks: {failed}")


def _resolve_output_dir(project_root: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.is_absolute():
        return output_dir.resolve()
    return (project_root / output_dir).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())
