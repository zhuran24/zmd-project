from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.signature_monotonic.precheck_promotion_spec import (
    DEFAULT_PRECHECK_CANDIDATE_PATH,
    build_phase3b_signature_monotonic_precheck_promotion_spec,
    write_phase3b_signature_monotonic_precheck_promotion_spec,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B signature-monotonic precheck promotion spec."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--precheck-candidate", type=Path, default=DEFAULT_PRECHECK_CANDIDATE_PATH)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_signature_monotonic_precheck_promotion_spec"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    spec = build_phase3b_signature_monotonic_precheck_promotion_spec(
        project_root,
        precheck_candidate_path=args.precheck_candidate,
    )
    _print_summary(spec)
    if not bool(args.no_write):
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        paths = write_phase3b_signature_monotonic_precheck_promotion_spec(spec, output_dir)
        for key, value in paths.items():
            print(f"signature_monotonic_precheck_promotion_{key}={_display_path(project_root, Path(value))}")
    return 0


def _print_summary(spec: Mapping[str, Any]) -> None:
    status = _mapping(spec.get("promotion_status"))
    failed = [
        str(check.get("check_id"))
        for check in list(spec.get("checks", []))
        if isinstance(check, Mapping) and str(check.get("status")) == "fail"
    ]
    print("phase3b signature-monotonic precheck promotion spec")
    print(f"- spec ready for runtime slice: {bool(status.get('spec_ready_for_runtime_slice', False))}")
    print(f"- runtime slice implemented: {bool(status.get('runtime_slice_implemented', False))}")
    print(f"- runtime promotion ready: {bool(status.get('runtime_promotion_ready', False))}")
    print(f"- recommendation: {status.get('recommendation')}")
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
