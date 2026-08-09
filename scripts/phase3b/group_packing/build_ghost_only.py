from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.group_packing.ghost_only import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
    build_phase3b_group_packing_ghost_only_verifier,
    render_phase3b_group_packing_ghost_only_markdown,
    render_phase3b_group_packing_ghost_only_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B ghost-only group-packing verifier."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--campaign-state", type=Path, default=DEFAULT_CAMPAIGN_STATE_PATH)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument("--sample-limit", type=int, default=8)
    parser.add_argument("--time-limit-seconds", type=float, default=0.5)
    parser.add_argument("--max-candidates", type=int, default=2500)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_group_packing_ghost_only"),
    )
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_group_packing_ghost_only_verifier(
        project_root,
        campaign_state_path=args.campaign_state,
        candidate=str(args.candidate),
        sample_limit=int(args.sample_limit),
        time_limit_seconds=float(args.time_limit_seconds),
        max_candidates=int(args.max_candidates),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = args.output_prefix or f"ghost_only_group_packing_{str(args.candidate)}"
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_group_packing_ghost_only_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_group_packing_ghost_only_text(report))
        print(f"ghost_only_group_packing_json={_display_path(project_root, json_path)}")
        print(f"ghost_only_group_packing_md={_display_path(project_root, md_path)}")
        print(f"ghost_only_group_packing_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    verifier = _mapping(report.get("ghost_only_verifier"))
    print("phase3b ghost-only group-packing verifier")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(
        "- samples: "
        f"{verifier.get('sample_count', 0)} "
        f"feasible={verifier.get('feasible_count', 0)} "
        f"infeasible={verifier.get('infeasible_count', 0)} "
        f"unknown={verifier.get('unknown_count', 0)} "
        f"skipped={verifier.get('skipped_count', 0)}"
    )
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
