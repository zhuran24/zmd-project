from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.coordinate_validation.order_capacity_certificate_candidate import (
    DEFAULT_ORDER_CAPACITY_EXPLANATION_PATH,
    DEFAULT_PAIR_X_CORE_SYNTHESIS_PATH,
    DEFAULT_PAIR_X_NO_GHOST_SPACE_SYNTHESIS_PATH,
    build_phase3b_coordinate_validation_order_capacity_certificate_candidate,
    render_phase3b_coordinate_validation_order_capacity_certificate_candidate_markdown,
    render_phase3b_coordinate_validation_order_capacity_certificate_candidate_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B coordinate-validation order-capacity certificate candidate."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--pair-x-core-synthesis",
        type=Path,
        default=DEFAULT_PAIR_X_CORE_SYNTHESIS_PATH,
        help="Path to anchor119 pair-x core synthesis json.",
    )
    parser.add_argument(
        "--pair-x-no-ghost-space-synthesis",
        type=Path,
        default=DEFAULT_PAIR_X_NO_GHOST_SPACE_SYNTHESIS_PATH,
        help="Path to anchor119 pair-x no-ghost-space synthesis json.",
    )
    parser.add_argument(
        "--order-capacity-explanation",
        type=Path,
        default=DEFAULT_ORDER_CAPACITY_EXPLANATION_PATH,
        help="Path to order-implied capacity explanation json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_order_capacity_certificate_candidate"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_coordinate_validation_order_capacity_certificate_candidate(
        project_root,
        pair_x_core_synthesis_path=args.pair_x_core_synthesis,
        pair_x_no_ghost_space_synthesis_path=args.pair_x_no_ghost_space_synthesis,
        order_capacity_explanation_path=args.order_capacity_explanation,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "order_capacity_certificate_candidate.json"
        md_path = output_dir / "order_capacity_certificate_candidate.md"
        txt_path = output_dir / "order_capacity_certificate_candidate.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_coordinate_validation_order_capacity_certificate_candidate_markdown(
                report
            ),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_coordinate_validation_order_capacity_certificate_candidate_text(
                report
            ),
        )
        print(
            "order_capacity_certificate_candidate_json="
            + _display_path(project_root, json_path)
        )
        print(
            "order_capacity_certificate_candidate_md="
            + _display_path(project_root, md_path)
        )
        print(
            "order_capacity_certificate_candidate_txt="
            + _display_path(project_root, txt_path)
        )
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    gate = _mapping(report.get("gate"))
    evidence = _mapping(report.get("evidence"))
    failed_checks = [
        str(check.get("check_id"))
        for check in list(report.get("checks", []))
        if isinstance(check, Mapping) and str(check.get("status")) == "fail"
    ]
    print("phase3b coordinate-validation order-capacity certificate candidate")
    print(f"- design gate passed: {bool(gate.get('design_gate_passed', False))}")
    print(
        f"- proof-preserving precheck ready: {bool(gate.get('proof_preserving_precheck_ready', False))}"
    )
    print(f"- core outcome: {evidence.get('core_outcome')}")
    print(
        f"- exceeded infeasible slot indices: {evidence.get('exceeded_infeasible_slot_indices')}"
    )
    print(f"- recommendation: {gate.get('recommendation')}")
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
