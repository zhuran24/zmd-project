from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.active_guard.residual_surface import (
    DEFAULT_ACTIVE_GUARD_PROBE_PATHS,
    DEFAULT_FAMILY_BOUND_AUDIT_PATH,
    DEFAULT_PROTOCOL_AUDIT_PATH,
    build_phase3b_active_guard_residual_surface,
    render_phase3b_active_guard_residual_surface_markdown,
    render_phase3b_active_guard_residual_surface_text,
)
from src.search.phase3b.forced_anchor.master import _display_path, _mapping


DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_active_guard_residual_surface")


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    probe_paths = _parse_paths(args.active_guard_probe_paths)
    report = build_phase3b_active_guard_residual_surface(
        project_root,
        protocol_audit_path=args.protocol_audit,
        family_bound_audit_path=args.family_bound_audit,
        active_guard_probe_paths=probe_paths,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "active_guard_residual_surface.json"
        md_path = output_dir / "active_guard_residual_surface.md"
        txt_path = output_dir / "active_guard_residual_surface.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_active_guard_residual_surface_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_active_guard_residual_surface_text(report),
        )
        print(f"active_guard_residual_surface_json={_display_path(project_root, json_path)}")
        print(f"active_guard_residual_surface_md={_display_path(project_root, md_path)}")
        print(f"active_guard_residual_surface_txt={_display_path(project_root, txt_path)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a no-solve ActiveGuard residual-surface synthesis report."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--protocol-audit", type=Path, default=DEFAULT_PROTOCOL_AUDIT_PATH)
    parser.add_argument("--family-bound-audit", type=Path, default=DEFAULT_FAMILY_BOUND_AUDIT_PATH)
    parser.add_argument(
        "--active-guard-probe-paths",
        default=",".join(str(path) for path in DEFAULT_ACTIVE_GUARD_PROBE_PATHS),
        help="Comma-separated forced-anchor proto-reduction JSON paths.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def _parse_paths(raw: str) -> list[Path]:
    return [Path(token.strip()) for token in str(raw).split(",") if token.strip()]


def _resolve_output_dir(project_root: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.is_absolute():
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    path = project_root / output_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def _print_summary(report: dict[str, object]) -> None:
    status = _mapping(report.get("status"))
    probes = _mapping(report.get("active_guard_probe_summary"))
    protocol = _mapping(report.get("protocol_surface"))
    relationship = _mapping(report.get("relationship"))
    print("phase3b active-guard residual surface")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}")
    print(f"- probes: {probes.get('probe_count')}")
    print(f"- zero-branch UNKNOWN: {probes.get('zero_branch_unknown_count')}")
    print(f"- mapped protocol slots: {protocol.get('mapped_protocol_slot_count')}")
    print(f"- classification: {relationship.get('classification')}")
    print(f"- next: {relationship.get('recommended_next_action')}")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
