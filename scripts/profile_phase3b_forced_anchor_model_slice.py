from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.forced_anchor.master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
)
from src.search.phase3b.forced_anchor.model_slice import (
    ALLOWED_SLICE_VARIANTS,
    DEFAULT_SLICE_VARIANTS,
    build_phase3b_forced_anchor_model_slice_diagnostic,
    render_phase3b_forced_anchor_model_slice_markdown,
    render_phase3b_forced_anchor_model_slice_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile diagnostic forced-anchor model slices with mutated residual optional layers."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--campaign-state", type=Path, default=DEFAULT_CAMPAIGN_STATE_PATH)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument("--sample-limit", type=int, default=1)
    parser.add_argument(
        "--anchor-indices",
        default=None,
        help="Optional comma-separated anchor indices to inspect instead of the first sampled anchors.",
    )
    parser.add_argument("--time-limit-seconds", type=float, default=20.0)
    parser.add_argument("--worker-count", type=int, default=4)
    parser.add_argument(
        "--variants",
        default=",".join(DEFAULT_SLICE_VARIANTS),
        help="Comma-separated variants. Known variants: "
        + ",".join(ALLOWED_SLICE_VARIANTS),
    )
    parser.add_argument(
        "--target-power-family",
        default=None,
        help="Power-pole family id for target_power_family_bound_relaxed diagnostic variants, e.g. family_009.",
    )
    parser.add_argument(
        "--solver-profile-json",
        default=None,
        help="Optional JSON solver parameter profile for diagnostic probes.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_forced_anchor_model_slice"),
    )
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_forced_anchor_model_slice_diagnostic(
        project_root,
        campaign_state_path=args.campaign_state,
        candidate=str(args.candidate),
        sample_limit=int(args.sample_limit),
        anchor_indices=_parse_anchor_indices(args.anchor_indices),
        time_limit_seconds=float(args.time_limit_seconds),
        worker_count=int(args.worker_count),
        variants=_parse_csv(args.variants),
        target_power_family=(
            str(args.target_power_family).strip()
            if args.target_power_family is not None
            and str(args.target_power_family).strip()
            else None
        ),
        solver_parameter_profile=_parse_solver_profile(args.solver_profile_json),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = args.output_prefix or f"forced_anchor_model_slice_{str(args.candidate)}"
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_forced_anchor_model_slice_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_forced_anchor_model_slice_text(report))
        print(f"forced_anchor_model_slice_json={_display_path(project_root, json_path)}")
        print(f"forced_anchor_model_slice_md={_display_path(project_root, md_path)}")
        print(f"forced_anchor_model_slice_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    matrix = _mapping(report.get("slice_matrix"))
    print("phase3b forced-anchor model-slice diagnostic")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- status counts: {matrix.get('status_counts', {})}")
    print(f"- by variant: {matrix.get('status_counts_by_variant', {})}")
    print(f"- diagnostic findings: {matrix.get('diagnostic_findings', [])}")
    print("- diagnostic semantics: mutated_model_slice_not_proof_source")
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_anchor_indices(raw_value: str | None) -> list[int] | None:
    if raw_value is None or not str(raw_value).strip():
        return None
    return [int(token.strip()) for token in str(raw_value).split(",") if token.strip()]


def _parse_csv(raw_value: str) -> list[str]:
    return [token.strip() for token in str(raw_value).split(",") if token.strip()]


def _parse_solver_profile(raw_value: str | None) -> dict[str, Any] | None:
    if raw_value is None or not str(raw_value).strip():
        return None
    text = str(raw_value).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = json.loads(text.replace("'", '"'))
    if not isinstance(parsed, Mapping):
        raise ValueError("--solver-profile-json must be a JSON object")
    return dict(parsed)


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
