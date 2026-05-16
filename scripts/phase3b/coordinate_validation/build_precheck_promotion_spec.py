from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.coordinate_validation.precheck_promotion_spec import (
    DEFAULT_MIN_MATRIX_INFEASIBLE_COUNT,
    DEFAULT_MIN_REJECTED_ANCHOR_COUNT,
    DEFAULT_PRECHECK_CANDIDATE_PATH,
    build_phase3b_coordinate_validation_precheck_promotion_spec,
    render_phase3b_coordinate_validation_precheck_promotion_spec_markdown,
    render_phase3b_coordinate_validation_precheck_promotion_spec_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B coordinate-validation precheck runtime-promotion spec."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--precheck-candidate",
        type=Path,
        default=DEFAULT_PRECHECK_CANDIDATE_PATH,
    )
    parser.add_argument(
        "--min-rejected-anchor-count",
        type=int,
        default=DEFAULT_MIN_REJECTED_ANCHOR_COUNT,
    )
    parser.add_argument(
        "--min-matrix-infeasible-count",
        type=int,
        default=DEFAULT_MIN_MATRIX_INFEASIBLE_COUNT,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_coordinate_validation_precheck_promotion_spec"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    spec = build_phase3b_coordinate_validation_precheck_promotion_spec(
        project_root,
        precheck_candidate_path=args.precheck_candidate,
        min_rejected_anchor_count=int(args.min_rejected_anchor_count),
        min_matrix_infeasible_count=int(args.min_matrix_infeasible_count),
    )
    _print_summary(spec)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "promotion_spec.json"
        md_path = output_dir / "promotion_spec.md"
        txt_path = output_dir / "promotion_spec.txt"
        atomic_write_json(json_path, spec)
        _atomic_write_text(
            md_path,
            render_phase3b_coordinate_validation_precheck_promotion_spec_markdown(spec),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_coordinate_validation_precheck_promotion_spec_text(spec),
        )
        print(f"coordinate_promotion_spec_json={_display_path(project_root, json_path)}")
        print(f"coordinate_promotion_spec_md={_display_path(project_root, md_path)}")
        print(f"coordinate_promotion_spec_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(spec: Mapping[str, Any]) -> None:
    candidate = _mapping(spec.get("candidate"))
    status = _mapping(spec.get("promotion_status"))
    evidence = _mapping(spec.get("evidence_summary"))
    failed_checks = [
        str(check.get("check_id"))
        for check in list(spec.get("checks", []))
        if isinstance(check, Mapping) and str(check.get("status")) == "fail"
    ]
    print("phase3b coordinate-validation precheck promotion spec")
    print(f"- candidate: {candidate.get('key')}")
    print(
        "- spec ready for runtime slice: "
        f"{bool(status.get('spec_ready_for_runtime_slice', False))}"
    )
    print(
        "- runtime promotion ready: "
        f"{bool(status.get('runtime_promotion_ready', False))}"
    )
    print(f"- rejected anchors: {evidence.get('rejected_count', 0)}")
    print(f"- matrix infeasible count: {evidence.get('matrix_infeasible_count', 0)}")
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
