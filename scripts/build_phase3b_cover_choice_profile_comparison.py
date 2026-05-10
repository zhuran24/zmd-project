from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_cover_choice_profile_comparison import (
    DEFAULT_COVER_CHOICE_CANDIDATE,
    build_phase3b_cover_choice_profile_comparison,
    render_phase3b_cover_choice_profile_comparison_markdown,
    render_phase3b_cover_choice_profile_comparison_text,
)

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a no-solve Phase 3B cover-choice profile comparison."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--campaign-state",
        type=Path,
        default=None,
    )
    parser.add_argument("--candidate", default=DEFAULT_COVER_CHOICE_CANDIDATE)
    parser.add_argument("--block-size", type=int, default=64)
    parser.add_argument("--protocol-block-templates", default="protocol_storage_box")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_cover_choice_profile_comparison"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_cover_choice_profile_comparison(
        project_root,
        campaign_state_path=args.campaign_state,
        candidate=str(args.candidate),
        block_size=int(args.block_size),
        protocol_block_templates=_parse_csv(args.protocol_block_templates),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "cover_choice_profile_comparison.json"
        md_path = output_dir / "cover_choice_profile_comparison.md"
        txt_path = output_dir / "cover_choice_profile_comparison.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_cover_choice_profile_comparison_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_cover_choice_profile_comparison_text(report),
        )
        print(f"cover_choice_profile_comparison_json={_display_path(project_root, json_path)}")
        print(f"cover_choice_profile_comparison_md={_display_path(project_root, md_path)}")
        print(f"cover_choice_profile_comparison_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    assessment = _mapping(report.get("final_target_channel_assessment"))
    print("phase3b cover-choice profile comparison")
    print("- diagnostic semantics: proto_build_profile_not_proof_source")
    print(f"- solver_invoked: {bool(report.get('solver_invoked', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- proto variable delta: {comparison.get('proto_variable_delta_all_templates_minus_protocol_only')}")
    print(f"- element delta: {comparison.get('element_delta_all_templates_minus_protocol_only')}")
    print(f"- wide idx delta: {comparison.get('wide_idx_delta_all_templates_minus_protocol_only')}")
    print(
        "- selected block final target delta: "
        f"{comparison.get('final_target_delta_selected_block_minus_all_templates')}"
    )
    print(
        "- selected block element delta: "
        f"{comparison.get('element_delta_selected_block_minus_all_templates')}"
    )
    print(f"- final target verdict: {assessment.get('verdict')}")
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_csv(raw_value: str) -> list[str]:
    return [token.strip() for token in str(raw_value).split(",") if token.strip()]


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
