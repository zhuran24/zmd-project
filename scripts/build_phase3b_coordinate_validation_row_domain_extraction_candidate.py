from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_coordinate_validation_row_domain_extraction_candidate import (
    DEFAULT_EXTRACTION_SPEC_PATH,
    DEFAULT_ORDER_CAPACITY_CERTIFICATE_CANDIDATE_PATH,
    DEFAULT_PAIR_X_CORE_DOMAIN_INSPECTION_PATH,
    build_phase3b_coordinate_validation_row_domain_extraction_candidate,
    render_phase3b_coordinate_validation_row_domain_extraction_candidate_markdown,
    render_phase3b_coordinate_validation_row_domain_extraction_candidate_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B coordinate-validation row-domain extraction candidate."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--extraction-spec",
        type=Path,
        default=DEFAULT_EXTRACTION_SPEC_PATH,
        help="Path to proof-preserving extraction spec json.",
    )
    parser.add_argument(
        "--order-capacity-certificate-candidate",
        type=Path,
        default=DEFAULT_ORDER_CAPACITY_CERTIFICATE_CANDIDATE_PATH,
        help="Path to order-capacity certificate candidate json.",
    )
    parser.add_argument(
        "--pair-x-core-domain-inspection",
        type=Path,
        default=DEFAULT_PAIR_X_CORE_DOMAIN_INSPECTION_PATH,
        help="Path to pair-x core domain inspection json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_row_domain_extraction_candidate"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_coordinate_validation_row_domain_extraction_candidate(
        project_root,
        extraction_spec_path=args.extraction_spec,
        order_capacity_certificate_candidate_path=args.order_capacity_certificate_candidate,
        pair_x_core_domain_inspection_path=args.pair_x_core_domain_inspection,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "row_domain_extraction_candidate.json"
        md_path = output_dir / "row_domain_extraction_candidate.md"
        txt_path = output_dir / "row_domain_extraction_candidate.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_coordinate_validation_row_domain_extraction_candidate_markdown(
                report
            ),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_coordinate_validation_row_domain_extraction_candidate_text(
                report
            ),
        )
        print(
            "row_domain_extraction_candidate_json="
            + _display_path(project_root, json_path)
        )
        print(
            "row_domain_extraction_candidate_md="
            + _display_path(project_root, md_path)
        )
        print(
            "row_domain_extraction_candidate_txt="
            + _display_path(project_root, txt_path)
        )
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    evidence = _mapping(report.get("evidence"))
    failed_checks = [
        str(check.get("check_id"))
        for check in list(report.get("checks", []))
        if isinstance(check, Mapping) and str(check.get("status")) == "fail"
    ]
    print("phase3b coordinate-validation row-domain extraction candidate")
    print(f"- design gate passed: {bool(status.get('design_gate_passed', False))}")
    print(f"- runtime promotion ready: {bool(status.get('runtime_promotion_ready', False))}")
    print(f"- core slot count: {evidence.get('core_slot_count')}")
    print(
        f"- planter order implication count: {evidence.get('planter_order_implication_count')}"
    )
    print(f"- recommendation: {status.get('recommendation')}")
    if failed_checks:
        print(f"- failed checks: {failed_checks}")


def _resolve_output_dir(project_root: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.is_absolute():
        return output_dir.resolve()
    return (project_root / output_dir).resolve()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())
