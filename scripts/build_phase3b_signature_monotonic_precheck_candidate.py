from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_signature_monotonic_precheck_candidate import (
    DEFAULT_AUDIT_DIR,
    build_phase3b_signature_monotonic_precheck_candidate_summary,
    write_phase3b_signature_monotonic_precheck_candidate_summary,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B signature-monotonic precheck candidate gate."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--control-audit", type=Path, default=None)
    parser.add_argument("--min-infeasible-count", type=int, default=3)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_signature_monotonic_precheck_candidate"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    summary = build_phase3b_signature_monotonic_precheck_candidate_summary(
        project_root,
        audit_dir=args.audit_dir,
        control_audit_path=args.control_audit,
        min_infeasible_count=int(args.min_infeasible_count),
    )
    _print_summary(summary)
    if not bool(args.no_write):
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        paths = write_phase3b_signature_monotonic_precheck_candidate_summary(summary, output_dir)
        for key, value in paths.items():
            print(f"signature_monotonic_precheck_candidate_{key}={_display_path(project_root, Path(value))}")
    return 0


def _print_summary(summary: Mapping[str, Any]) -> None:
    gate = _mapping(summary.get("gate"))
    evidence = _mapping(summary.get("evidence"))
    failed = [
        str(check.get("check_id"))
        for check in list(summary.get("checks", []))
        if isinstance(check, Mapping) and str(check.get("status")) == "fail"
    ]
    print("phase3b signature-monotonic precheck candidate gate")
    print(f"- design gate passed: {bool(gate.get('design_gate_passed', False))}")
    print(f"- runtime promotion ready: {bool(gate.get('runtime_promotion_ready', False))}")
    print(f"- monotonic infeasible count: {evidence.get('monotonic_infeasible_count')}")
    print(f"- monotonic feasible controls: {evidence.get('monotonic_feasible_control_count')}")
    print(f"- recommendation: {gate.get('recommendation')}")
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
