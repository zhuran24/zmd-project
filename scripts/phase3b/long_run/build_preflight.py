from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.long_run.preflight import (
    DEFAULT_MIN_FREE_GB,
    build_phase3b_long_run_preflight_summary,
    render_phase3b_long_run_preflight_markdown,
    render_phase3b_long_run_preflight_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Phase 3B final long-run preflight gate summary."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--b5a-summary", type=Path, default=None)
    parser.add_argument("--production-acceptance-summary", type=Path, default=None)
    parser.add_argument("--production-acceptance-result-validator", type=Path, default=None)
    parser.add_argument("--startline-manifest", type=Path, default=None)
    parser.add_argument("--group-packing-promotion-spec", type=Path, default=None)
    parser.add_argument("--group-packing-proof-promotion", type=Path, default=None)
    parser.add_argument("--coordinate-validation-precheck-candidate", type=Path, default=None)
    parser.add_argument("--coordinate-validation-promotion-spec", type=Path, default=None)
    parser.add_argument("--b5a-gate-integration-marker", type=Path, default=None)
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path("E:/phase3b_workspaces/endfield_phase3b_b5_anchor_20260417"),
    )
    parser.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_long_run_preflight"),
    )
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument(
        "--allow-failed-exit-zero",
        action="store_true",
        help="Return exit code 0 even when the preflight is not ready.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    summary = build_phase3b_long_run_preflight_summary(
        project_root,
        b5a_summary_path=args.b5a_summary,
        production_acceptance_path=args.production_acceptance_summary,
        production_acceptance_result_validator_path=(
            args.production_acceptance_result_validator
        ),
        startline_manifest_path=args.startline_manifest,
        group_packing_promotion_spec_path=args.group_packing_promotion_spec,
        group_packing_proof_promotion_path=args.group_packing_proof_promotion,
        coordinate_validation_precheck_candidate_path=args.coordinate_validation_precheck_candidate,
        coordinate_validation_promotion_spec_path=args.coordinate_validation_promotion_spec,
        b5a_gate_integration_marker_path=args.b5a_gate_integration_marker,
        workspace_root=args.workspace_root,
        min_free_gb=float(args.min_free_gb),
    )
    _print_summary(summary)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "preflight_summary.json"
        md_path = output_dir / "preflight_summary.md"
        txt_path = output_dir / "preflight_summary.txt"
        atomic_write_json(json_path, summary)
        _atomic_write_text(md_path, render_phase3b_long_run_preflight_markdown(summary))
        _atomic_write_text(txt_path, render_phase3b_long_run_preflight_text(summary))
        print(f"preflight_summary_json={_display_path(project_root, json_path)}")
        print(f"preflight_summary_md={_display_path(project_root, md_path)}")
        print(f"preflight_summary_txt={_display_path(project_root, txt_path)}")
    if bool(summary.get("ready_for_final_long_run", False)):
        return 0
    return 0 if args.allow_failed_exit_zero else 2


def _print_summary(summary: Mapping[str, Any]) -> None:
    print("phase3b final long-run preflight")
    print(f"- ready: {bool(summary.get('ready_for_final_long_run', False))}")
    print(
        "- ready to request human launch authorization: "
        f"{bool(summary.get('ready_to_request_human_launch_authorization', False))}"
    )
    print(f"- final 168h authorized: {bool(summary.get('final_168h_authorized', False))}")
    print(f"- execution allowed: {bool(summary.get('execution_allowed', False))}")
    print(f"- recommendation: {summary.get('recommendation')}")
    final_long_run = _mapping(summary.get("final_long_run"))
    print(f"- dry-run command: {final_long_run.get('dry_run_command')}")
    print("- non-dry-run command: not emitted without human authorization")
    failed = [
        str(check.get("check_id"))
        for check in list(summary.get("checks", []))
        if isinstance(check, Mapping) and str(check.get("status")) == "fail"
    ]
    print(f"- failed checks: {failed}")


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
