from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.forced_anchor.master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
)
from src.search.phase3b.residual_optional.residual_optional_encoding import (
    build_phase3b_residual_optional_encoding_inventory,
    render_phase3b_residual_optional_encoding_markdown,
    render_phase3b_residual_optional_encoding_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B residual optional encoding inventory."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--campaign-state", type=Path, default=DEFAULT_CAMPAIGN_STATE_PATH)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_residual_optional_encoding"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_residual_optional_encoding_inventory(
        project_root,
        campaign_state_path=args.campaign_state,
        candidate=str(args.candidate),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "residual_optional_encoding.json"
        md_path = output_dir / "residual_optional_encoding.md"
        txt_path = output_dir / "residual_optional_encoding.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_residual_optional_encoding_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_residual_optional_encoding_text(report))
        print(f"residual_optional_encoding_json={_display_path(project_root, json_path)}")
        print(f"residual_optional_encoding_md={_display_path(project_root, md_path)}")
        print(f"residual_optional_encoding_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    encoding = _mapping(report.get("encoding"))
    proto = _mapping(encoding.get("proto"))
    residual = _mapping(encoding.get("residual_optional_slots"))
    power = _mapping(encoding.get("power_coverage"))
    print("phase3b residual optional encoding inventory")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- residual slots: {residual.get('by_template', {})}")
    print(f"- power coverage: {power}")
    print(f"- proto variables: {proto.get('variable_count')}")
    print(f"- proto constraints: {proto.get('constraint_count')}")
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
