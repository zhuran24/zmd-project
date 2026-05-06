from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_b5_anchor_sprint import (
    build_phase3b_b5_anchor_sprint_summary,
    render_phase3b_b5_anchor_sprint_markdown,
    render_phase3b_b5_anchor_sprint_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize a Phase 3B B5A first-certified-anchor sprint workspace."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Workspace/project root to summarize.",
    )
    parser.add_argument(
        "--campaign-state",
        type=Path,
        default=None,
        help="Campaign state JSON path. Defaults to data/checkpoints/exact_campaign_state.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_b5_anchor_sprint"),
        help="Directory for operator_summary.json/md/txt.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print the summary but do not write report files.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    summary = build_phase3b_b5_anchor_sprint_summary(
        project_root=project_root,
        campaign_state_path=args.campaign_state,
    )
    _print_summary(summary)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "operator_summary.json"
        md_path = output_dir / "operator_summary.md"
        txt_path = output_dir / "operator_summary.txt"
        atomic_write_json(json_path, summary)
        _atomic_write_text(md_path, render_phase3b_b5_anchor_sprint_markdown(summary))
        _atomic_write_text(txt_path, render_phase3b_b5_anchor_sprint_text(summary))
        print(f"operator_summary_json={_display_path(project_root, json_path)}")
        print(f"operator_summary_md={_display_path(project_root, md_path)}")
        print(f"operator_summary_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(summary: Mapping[str, Any]) -> None:
    status = _mapping(summary.get("status"))
    campaign = _mapping(summary.get("campaign"))
    telemetry = _mapping(summary.get("telemetry"))
    triage = _mapping(summary.get("triage"))
    runtime_group_packing = _mapping(summary.get("runtime_group_packing"))
    print("phase3b b5a anchor sprint summary")
    print(f"- anchor found: {bool(status.get('anchor_found', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- recommendation: {status.get('recommendation')}")
    print(f"- campaign final status: {campaign.get('final_status')}")
    print(f"- telemetry waves: {telemetry.get('wave_count', 0)}")
    print(f"- triage blockers: {triage.get('blocker_count', 0)}")
    print(
        "- runtime group-packing diagnostics: "
        f"{runtime_group_packing.get('diagnostic_count', 0)}"
    )
    print(
        "- runtime group-packing diagnostics for current candidate: "
        f"{runtime_group_packing.get('relevant_diagnostic_count', 0)}"
    )
    print(
        "- stale runtime group-packing diagnostics: "
        f"{runtime_group_packing.get('stale_diagnostic_count', 0)}"
    )


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
