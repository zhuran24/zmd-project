from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_coordinate_group_precheck_candidate import (
    DEFAULT_FIELD_CHANNEL_DELTA_PATH,
    DEFAULT_GROUP_DELTA_PATH,
    build_phase3b_coordinate_group_precheck_candidate,
    render_phase3b_coordinate_group_precheck_candidate_markdown,
    render_phase3b_coordinate_group_precheck_candidate_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B coordinate group precheck candidate report."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--group-delta", type=Path, default=DEFAULT_GROUP_DELTA_PATH)
    parser.add_argument(
        "--field-channel-delta",
        type=Path,
        default=DEFAULT_FIELD_CHANNEL_DELTA_PATH,
    )
    parser.add_argument(
        "--target-group-id",
        default="group::manufacturing_5x5::planter_buckwheat::9",
    )
    parser.add_argument("--target-field-variant", default="x_y")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_coordinate_group_precheck_candidate"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    summary = build_phase3b_coordinate_group_precheck_candidate(
        project_root,
        group_delta_path=args.group_delta,
        field_channel_delta_path=args.field_channel_delta,
        target_group_id=str(args.target_group_id),
        target_field_variant=str(args.target_field_variant),
    )
    _print_summary(summary)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "coordinate_group_precheck_candidate.json"
        md_path = output_dir / "coordinate_group_precheck_candidate.md"
        txt_path = output_dir / "coordinate_group_precheck_candidate.txt"
        atomic_write_json(json_path, summary)
        _atomic_write_text(
            md_path,
            render_phase3b_coordinate_group_precheck_candidate_markdown(summary),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_coordinate_group_precheck_candidate_text(summary),
        )
        print(f"coordinate_group_precheck_candidate_json={_display_path(project_root, json_path)}")
        print(f"coordinate_group_precheck_candidate_md={_display_path(project_root, md_path)}")
        print(f"coordinate_group_precheck_candidate_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(summary: Mapping[str, Any]) -> None:
    candidate = _mapping(summary.get("candidate"))
    target = _mapping(summary.get("target"))
    gate = _mapping(summary.get("gate"))
    failed_checks = [
        str(check.get("check_id"))
        for check in list(summary.get("checks", []))
        if isinstance(check, Mapping) and str(check.get("status")) == "fail"
    ]
    print("phase3b coordinate group precheck candidate")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- anchor: {candidate.get('anchor_idx')}")
    print(f"- target group: {target.get('group_id')}")
    print(f"- target field: {target.get('field_variant')}")
    print(f"- design gate passed: {bool(gate.get('design_gate_passed', False))}")
    print(f"- runtime promotion ready: {bool(gate.get('runtime_promotion_ready', False))}")
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
