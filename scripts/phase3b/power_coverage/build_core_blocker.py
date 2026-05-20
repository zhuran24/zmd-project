from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.power_coverage.core_blocker import (
    DEFAULT_CORE_SLICE_PATH,
    DEFAULT_CUSTOM_CORE_SLICE_PATH,
    build_phase3b_power_coverage_core_blocker_report,
    render_phase3b_power_coverage_core_blocker_markdown,
    render_phase3b_power_coverage_core_blocker_text,
)
from src.search.phase3b.power_protocol.interaction import (
    DEFAULT_POWER_COVERAGE_ANCHOR_DELTA_PATH,
    DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B power-coverage core blocker report from current model slices."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--core-slice", type=Path, default=DEFAULT_CORE_SLICE_PATH)
    parser.add_argument(
        "--custom-core-slice",
        type=Path,
        default=DEFAULT_CUSTOM_CORE_SLICE_PATH,
    )
    parser.add_argument(
        "--residual-optional-encoding",
        type=Path,
        default=DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
    )
    parser.add_argument(
        "--power-coverage-anchor-delta",
        type=Path,
        default=DEFAULT_POWER_COVERAGE_ANCHOR_DELTA_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_power_coverage_core_blocker"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_power_coverage_core_blocker_report(
        project_root,
        core_slice_path=args.core_slice,
        custom_core_slice_path=args.custom_core_slice,
        residual_optional_encoding_path=args.residual_optional_encoding,
        power_coverage_anchor_delta_path=args.power_coverage_anchor_delta,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "power_coverage_core_blocker.json"
        md_path = output_dir / "power_coverage_core_blocker.md"
        txt_path = output_dir / "power_coverage_core_blocker.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_power_coverage_core_blocker_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_power_coverage_core_blocker_text(report))
        print(f"power_coverage_core_blocker_json={_display_path(project_root, json_path)}")
        print(f"power_coverage_core_blocker_md={_display_path(project_root, md_path)}")
        print(f"power_coverage_core_blocker_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    matrix = _mapping(report.get("combined_matrix"))
    residual = _mapping(report.get("residual_optional_encoding"))
    power = _mapping(residual.get("power_coverage"))
    print("phase3b power-coverage core blocker")
    print(f"- classification: {report.get('classification')}")
    print(f"- anchor: {matrix.get('anchor_idx')}")
    print(f"- base status: {matrix.get('base_status')}")
    print(f"- skip power coverage status: {matrix.get('skip_power_coverage_core_status')}")
    print(f"- no protocol lower-bound status: {matrix.get('no_protocol_lower_bound_core_status')}")
    print(f"- witness indices: {power.get('witness_indices')}")
    print(f"- element constraints: {power.get('element_constraints')}")
    print(f"- recommendation: {report.get('recommendation')}")


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
