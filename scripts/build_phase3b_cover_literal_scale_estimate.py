from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_cover_literal_scale_estimate import (
    build_phase3b_cover_literal_scale_estimate,
    render_phase3b_cover_literal_scale_estimate_markdown,
    render_phase3b_cover_literal_scale_estimate_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B full-proto cover literal replacement scale estimate."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--campaign-state", type=Path, default=None)
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument("--sample-limit", type=int, default=1)
    parser.add_argument(
        "--anchor-indices",
        default=None,
        help="Optional comma-separated anchor indices to inspect.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_cover_literal_scale_estimate"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_cover_literal_scale_estimate(
        project_root,
        campaign_state_path=args.campaign_state,
        candidate=str(args.candidate),
        sample_limit=int(args.sample_limit),
        anchor_indices=_parse_anchor_indices(args.anchor_indices),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "cover_literal_scale_estimate.json"
        md_path = output_dir / "cover_literal_scale_estimate.md"
        txt_path = output_dir / "cover_literal_scale_estimate.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_cover_literal_scale_estimate_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_cover_literal_scale_estimate_text(report))
        print(f"cover_literal_scale_json={_display_path(project_root, json_path)}")
        print(f"cover_literal_scale_md={_display_path(project_root, md_path)}")
        print(f"cover_literal_scale_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    print("phase3b cover-literal scale estimate")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- anchors: {summary.get('present_anchor_count')}/{summary.get('anchor_count')}")
    print(f"- max static-pruned pairs: {summary.get('max_static_pruned_pair_count')}")
    print(f"- max selected-coordinate constraints: {summary.get('max_selected_coord_total_constraints_estimate')}")
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_anchor_indices(raw_value: Optional[str]) -> Optional[list[int]]:
    if raw_value is None or not str(raw_value).strip():
        return None
    result: list[int] = []
    for token in str(raw_value).split(","):
        token = token.strip()
        if token:
            result.append(int(token))
    return result


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
