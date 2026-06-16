from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.protocol.protocol_witness_prefix_audit import (
    build_phase3b_protocol_witness_prefix_audit,
    render_phase3b_protocol_witness_prefix_audit_markdown,
    render_phase3b_protocol_witness_prefix_audit_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B protocol witness-prefix audit from existing diagnostics."
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
    parser.add_argument("--index-restrict", type=Path, default=None)
    parser.add_argument("--prefix-threshold", type=Path, default=None)
    parser.add_argument("--lookup-intact-prefix", type=Path, default=None)
    parser.add_argument("--window-restrict", type=Path, default=None)
    parser.add_argument("--active-prefix-guard", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_protocol_witness_prefix_audit"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_protocol_witness_prefix_audit(
        project_root,
        campaign_state_path=args.campaign_state,
        candidate=str(args.candidate),
        sample_limit=int(args.sample_limit),
        anchor_indices=_parse_anchor_indices(args.anchor_indices),
        index_restrict_path=args.index_restrict,
        prefix_threshold_path=args.prefix_threshold,
        lookup_intact_prefix_path=args.lookup_intact_prefix,
        window_restrict_path=args.window_restrict,
        active_prefix_guard_path=args.active_prefix_guard,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "protocol_witness_prefix_audit.json"
        md_path = output_dir / "protocol_witness_prefix_audit.md"
        txt_path = output_dir / "protocol_witness_prefix_audit.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_protocol_witness_prefix_audit_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_protocol_witness_prefix_audit_text(report),
        )
        print(f"protocol_witness_prefix_audit_json={_display_path(project_root, json_path)}")
        print(f"protocol_witness_prefix_audit_md={_display_path(project_root, md_path)}")
        print(f"protocol_witness_prefix_audit_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    analysis = _mapping(report.get("analysis"))
    overlay = _mapping(report.get("overlay"))
    print("phase3b protocol witness-prefix audit")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- recommendation: {status.get('recommendation')}")
    print(f"- power-pole slots: {overlay.get('power_pole_slot_count')}")
    print(f"- protocol slots: {overlay.get('protocol_slot_count')}")
    print(f"- best terminal first-prefix limit: {analysis.get('best_terminal_first_limit')}")
    print(f"- active-prefix guard outcome: {analysis.get('active_prefix_guard_outcome')}")
    print(f"- lookup-intact prefix outcome: {analysis.get('lookup_intact_prefix_outcome')}")


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
