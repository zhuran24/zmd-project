from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.b5a.gate_integration_marker import (
    build_phase3b_b5a_gate_integration_marker,
    write_phase3b_b5a_gate_integration_marker,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Phase3B B5A gate integration marker."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--promotion-review-packet", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_b5a_gate_integration_marker_20260426"),
    )
    parser.add_argument("--output-prefix", default="b5a_gate_integration_marker")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument(
        "--allow-failed-exit-zero",
        action="store_true",
        help="Return exit code 0 even when the marker is not ready.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_b5a_gate_integration_marker(
        project_root,
        promotion_review_packet_path=args.promotion_review_packet,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        paths = write_phase3b_b5a_gate_integration_marker(
            report,
            output_dir,
            output_prefix=str(args.output_prefix),
        )
        print(
            "b5a_gate_integration_marker_json="
            + _display_path(project_root, Path(paths["json"]))
        )
        print(
            "b5a_gate_integration_marker_md="
            + _display_path(project_root, Path(paths["md"]))
        )
        print(
            "b5a_gate_integration_marker_txt="
            + _display_path(project_root, Path(paths["txt"]))
        )
    ready = bool(
        _mapping(report.get("status")).get("gate_integration_marker_ready", False)
    )
    if ready:
        return 0
    return 0 if args.allow_failed_exit_zero else 2


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    print("phase3b B5A gate integration marker")
    print(f"- marker ready: {bool(status.get('gate_integration_marker_ready', False))}")
    print(
        "- repo-side B5A gate state updated: "
        f"{bool(status.get('repo_side_b5a_gate_state_updated', False))}"
    )
    print(f"- b5a_anchor_found: {bool(status.get('b5a_anchor_found', False))}")
    print(
        f"- certified_anchor_found: {bool(status.get('certified_anchor_found', False))}"
    )
    print(f"- proof_source: {bool(status.get('proof_source', False))}")
    print(
        "- runtime_semantics_changed: "
        f"{bool(status.get('runtime_semantics_changed', False))}"
    )
    print(f"- checkpoint_written: {bool(status.get('checkpoint_written', False))}")
    print(f"- recommended next step: {status.get('recommended_next_step')}")


def _resolve_output_dir(project_root: Path, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.is_absolute():
        return output_dir.resolve()
    return (project_root / output_dir).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())
