from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.active_guard.proto_shape_audit import (
    DEFAULT_ACTIVE_GUARD_CANDIDATE,
    build_phase3b_active_guard_proto_shape_audit,
    render_phase3b_active_guard_proto_shape_audit_markdown,
    render_phase3b_active_guard_proto_shape_audit_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B no-solve active-guard proto shape audit."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", default=DEFAULT_ACTIVE_GUARD_CANDIDATE)
    parser.add_argument("--block-size", type=int, default=64)
    parser.add_argument(
        "--block-templates",
        default="",
        help="Comma-separated block templates; empty means all powered templates.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_active_guard_proto_shape_audit"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_active_guard_proto_shape_audit(
        project_root,
        candidate=str(args.candidate),
        block_size=int(args.block_size),
        block_templates=str(args.block_templates),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "active_guard_proto_shape_audit.json"
        md_path = output_dir / "active_guard_proto_shape_audit.md"
        txt_path = output_dir / "active_guard_proto_shape_audit.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_active_guard_proto_shape_audit_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_active_guard_proto_shape_audit_text(report),
        )
        print(f"active_guard_proto_shape_audit_json={_display_path(project_root, json_path)}")
        print(f"active_guard_proto_shape_audit_md={_display_path(project_root, md_path)}")
        print(f"active_guard_proto_shape_audit_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    shape = _mapping(report.get("active_guard_shape"))
    print("phase3b active-guard proto shape audit")
    print("- diagnostic semantics: no_solve_proto_bool_or_shape_audit")
    print(f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', False))}")
    print(f"- proof_source: {bool(_mapping(report.get('metadata')).get('proof_source', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- guard clauses: {shape.get('guard_clause_count')}")
    print(f"- valid guard clauses: {shape.get('valid_guard_clause_count')}")
    print(f"- invalid guard clauses: {shape.get('invalid_guard_clause_count')}")
    print(f"- matches expected: {shape.get('matches_expected_guard_clause_count')}")
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
