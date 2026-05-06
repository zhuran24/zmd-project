from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b_anchor119_guarded_precheck_runtime import (
    ANCHOR119_GUARDED_PRECHECK_ENV,
    DEFAULT_GUARDED_PRECHECK_SPEC_PATH,
    evaluate_phase3b_anchor119_guarded_precheck_advisory,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Phase 3B anchor119 guarded precheck advisory."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--ghost-w", type=int, default=67)
    parser.add_argument("--ghost-h", type=int, default=13)
    parser.add_argument("--anchor-index", type=int, default=119)
    parser.add_argument("--spec-path", type=Path, default=DEFAULT_GUARDED_PRECHECK_SPEC_PATH)
    parser.add_argument(
        "--enable-advisory",
        action="store_true",
        help=f"Enable advisory evaluation regardless of {ANCHOR119_GUARDED_PRECHECK_ENV}.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=Path(
            ".artifacts/phase3b_anchor119_guarded_precheck_advisory_20260424/"
            "guarded_precheck_advisory.json"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = evaluate_phase3b_anchor119_guarded_precheck_advisory(
        project_root=project_root,
        ghost_w=int(args.ghost_w),
        ghost_h=int(args.ghost_h),
        anchor_idx=int(args.anchor_index),
        spec_path=Path(args.spec_path),
        enabled=True if bool(args.enable_advisory) else None,
    )
    _print_summary(report)
    if not bool(args.no_write):
        output_path = _resolve(project_root, Path(args.output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"guarded_precheck_advisory_json={_display(project_root, output_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    print("phase3b anchor119 guarded precheck advisory")
    print(f"- enabled: {bool(report.get('enabled', False))}")
    print(f"- triggered: {bool(report.get('triggered', False))}")
    print(f"- would_trigger: {bool(report.get('would_trigger', False))}")
    print(f"- status: {report.get('status')}")
    print(f"- reason: {report.get('reason')}")
    print("- runtime_precheck_enabled: false")
    print("- runtime_semantics_changed: false")
    print("- proof_source: false")


def _resolve(project_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
