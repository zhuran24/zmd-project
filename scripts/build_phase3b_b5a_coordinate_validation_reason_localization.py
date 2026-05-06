from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_b5a_coordinate_validation_reason_localization import (
    DEFAULT_FAILED_ANCHOR_INVENTORY_PATH,
    DEFAULT_POST_ACCEPTANCE_BLOCKER_SUMMARY_PATH,
    build_phase3b_b5a_coordinate_validation_reason_localization,
    render_phase3b_b5a_coordinate_validation_reason_localization_markdown,
    render_phase3b_b5a_coordinate_validation_reason_localization_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a report-only B5A coordinate-validation reason-localization "
            "artifact from existing B5A telemetry."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--workspace-root",
        type=Path,
        action="append",
        default=None,
        help="B5A workspace root to inspect. Can be supplied multiple times.",
    )
    parser.add_argument(
        "--post-acceptance-blocker-summary",
        type=Path,
        default=DEFAULT_POST_ACCEPTANCE_BLOCKER_SUMMARY_PATH,
    )
    parser.add_argument(
        "--failed-anchor-inventory",
        type=Path,
        default=DEFAULT_FAILED_ANCHOR_INVENTORY_PATH,
    )
    parser.add_argument("--anchor-min", type=int, default=118)
    parser.add_argument("--anchor-max", type=int, default=125)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_b5a_coordinate_validation_reason_localization_20260425"
        ),
    )
    parser.add_argument(
        "--output-prefix",
        default="b5a_coordinate_validation_reason_localization",
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_b5a_coordinate_validation_reason_localization(
        project_root,
        workspace_roots=args.workspace_root,
        post_acceptance_blocker_summary_path=args.post_acceptance_blocker_summary,
        failed_anchor_inventory_path=args.failed_anchor_inventory,
        anchor_min=int(args.anchor_min),
        anchor_max=int(args.anchor_max),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = str(args.output_prefix)
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_b5a_coordinate_validation_reason_localization_markdown(
                report
            ),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_b5a_coordinate_validation_reason_localization_text(
                report
            ),
        )
        print(
            "b5a_coordinate_validation_reason_localization_json="
            f"{_display_path(project_root, json_path)}"
        )
        print(
            "b5a_coordinate_validation_reason_localization_md="
            f"{_display_path(project_root, md_path)}"
        )
        print(
            "b5a_coordinate_validation_reason_localization_txt="
            f"{_display_path(project_root, txt_path)}"
        )
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    localization = _mapping(report.get("reason_localization"))
    selected = _mapping(report.get("selected_surface"))
    print("phase3b b5a coordinate-validation reason localization")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- reason localization ready: {status.get('reason_localization_ready')}")
    print(f"- selected workspace: {selected.get('workspace_root')}")
    print(f"- category counts: {localization.get('category_counts')}")
    print(f"- certified anchor found: {status.get('certified_anchor_found')}")
    print(f"- recommendation: {status.get('recommendation')}")


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
