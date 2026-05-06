from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_b5a_certified_anchor_promotion_review_packet import (
    DEFAULT_LOCALIZED_EVIDENCE_READINESS_PATH,
    DEFAULT_LOCALIZED_EVIDENCE_VALIDATOR_PATH,
    DEFAULT_POST_ACCEPTANCE_BLOCKER_SUMMARY_PATH,
    DEFAULT_REASON_LOCALIZATION_PATH,
    DEFAULT_REVIEW_STATE_PATH,
    build_phase3b_b5a_certified_anchor_promotion_review_packet,
    write_phase3b_b5a_certified_anchor_promotion_review_packet,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build Phase 3B B5A certified-anchor promotion review packet artifact."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--review-state",
        type=Path,
        default=DEFAULT_REVIEW_STATE_PATH,
    )
    parser.add_argument(
        "--localized-evidence-validator",
        type=Path,
        default=DEFAULT_LOCALIZED_EVIDENCE_VALIDATOR_PATH,
    )
    parser.add_argument(
        "--localized-evidence-readiness",
        type=Path,
        default=DEFAULT_LOCALIZED_EVIDENCE_READINESS_PATH,
    )
    parser.add_argument(
        "--reason-localization",
        type=Path,
        default=DEFAULT_REASON_LOCALIZATION_PATH,
    )
    parser.add_argument(
        "--post-acceptance-blocker-summary",
        type=Path,
        default=DEFAULT_POST_ACCEPTANCE_BLOCKER_SUMMARY_PATH,
    )
    parser.add_argument("--promotion-review-payload", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_b5a_certified_anchor_promotion_review_packet_20260425"
        ),
    )
    parser.add_argument(
        "--output-prefix",
        default="b5a_certified_anchor_promotion_review_packet",
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_b5a_certified_anchor_promotion_review_packet(
        project_root,
        review_state_path=args.review_state,
        localized_evidence_validator_path=args.localized_evidence_validator,
        localized_evidence_readiness_path=args.localized_evidence_readiness,
        reason_localization_path=args.reason_localization,
        post_acceptance_blocker_summary_path=args.post_acceptance_blocker_summary,
        promotion_review_payload_path=args.promotion_review_payload,
    )
    _print_summary(report)
    if not bool(args.no_write):
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        paths = write_phase3b_b5a_certified_anchor_promotion_review_packet(
            report,
            output_dir,
            output_prefix=str(args.output_prefix),
        )
        for key, value in paths.items():
            print(
                "b5a_certified_anchor_promotion_review_packet_"
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
    print("phase3b B5A certified-anchor promotion review packet")
    print(
        "- promotion review packet ready: "
        f"{bool(status.get('promotion_review_packet_ready', False))}"
    )
    print(
        "- promotion review payload provided: "
        f"{bool(status.get('promotion_review_payload_provided', False))}"
    )
    print(
        "- promotion review payload validated: "
        f"{bool(status.get('promotion_review_payload_validated', False))}"
    )
    print(
        "- promotion review payload validation status: "
        f"{status.get('promotion_review_payload_validation_status')}"
    )
    print(
        "- certified-anchor promotion review accepted: "
        f"{bool(status.get('certified_anchor_promotion_review_accepted', False))}"
    )
    print(f"- b5a anchor found: {bool(status.get('b5a_anchor_found', False))}")
    print(f"- certified anchor found: {bool(status.get('certified_anchor_found', False))}")
    print(f"- proof_source: {bool(status.get('proof_source', False))}")
    print(
        "- runtime_semantics_changed: "
        f"{bool(status.get('runtime_semantics_changed', False))}"
    )
    print(f"- checkpoint_written: {bool(status.get('checkpoint_written', False))}")
    print(f"- preflight_gate_mutated: {bool(status.get('preflight_gate_mutated', False))}")
    print(f"- still blocked gate ids: {status.get('still_blocked_gate_ids')}")
    print(f"- recommended next step: {status.get('recommended_next_step')}")
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
