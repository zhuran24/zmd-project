from __future__ import annotations

import argparse
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
from src.search.phase3b.mandatory_core.mandatory_core_matrix import (
    DEFAULT_MASTER_PROFILES,
    build_phase3b_mandatory_core_profile_matrix,
    render_phase3b_mandatory_core_profile_matrix_markdown,
    render_phase3b_mandatory_core_profile_matrix_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile Phase 3B mandatory-only forced-anchor core across master profiles and symmetry modes."
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
    parser.add_argument("--time-limit-seconds", type=float, default=15.0)
    parser.add_argument("--worker-count", type=int, default=4)
    parser.add_argument(
        "--profiles",
        default=",".join(DEFAULT_MASTER_PROFILES),
        help="Comma-separated exact coordinate master profiles.",
    )
    parser.add_argument(
        "--symmetry",
        choices=["both", "on", "off"],
        default="both",
        help="Symmetry mode matrix.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_mandatory_core_matrix"),
    )
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_mandatory_core_profile_matrix(
        project_root,
        campaign_state_path=args.campaign_state,
        candidate=str(args.candidate),
        sample_limit=int(args.sample_limit),
        anchor_indices=_parse_anchor_indices(args.anchor_indices),
        time_limit_seconds=float(args.time_limit_seconds),
        worker_count=int(args.worker_count),
        master_profiles=_parse_csv(args.profiles),
        symmetry_modes=_parse_symmetry(args.symmetry),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = args.output_prefix or f"mandatory_core_matrix_{str(args.candidate)}"
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_mandatory_core_profile_matrix_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_mandatory_core_profile_matrix_text(report))
        print(f"mandatory_core_matrix_json={_display_path(project_root, json_path)}")
        print(f"mandatory_core_matrix_md={_display_path(project_root, md_path)}")
        print(f"mandatory_core_matrix_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    matrix = _mapping(report.get("matrix"))
    print("phase3b mandatory-core profile matrix")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- status counts: {matrix.get('status_counts', {})}")
    print(f"- by profile: {matrix.get('status_counts_by_profile', {})}")
    print(f"- by symmetry: {matrix.get('status_counts_by_symmetry', {})}")
    print("- diagnostic semantics: mutated_mandatory_core_not_proof_source")
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_anchor_indices(raw_value: str | None) -> list[int] | None:
    if raw_value is None or not str(raw_value).strip():
        return None
    return [int(token.strip()) for token in str(raw_value).split(",") if token.strip()]


def _parse_csv(raw_value: str) -> list[str]:
    return [token.strip() for token in str(raw_value).split(",") if token.strip()]


def _parse_symmetry(raw_value: str) -> list[bool]:
    token = str(raw_value).strip().lower()
    if token == "on":
        return [True]
    if token == "off":
        return [False]
    return [True, False]


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
