from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.search.phase3b_anchor_differential_audit import (
    build_phase3b_anchor_differential_audit,
    render_phase3b_anchor_differential_audit_markdown,
    render_phase3b_anchor_differential_audit_text,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / ".artifacts" / "phase3b_anchor_differential_audit"


def main() -> int:
    args = _parse_args()
    report = build_phase3b_anchor_differential_audit(
        args.project_root,
        campaign_state_path=args.campaign_state,
        candidate=args.candidate,
        anchor_indices=_parse_anchor_indices(args.anchor_indices),
        sample_limit=args.sample_limit,
        master_search_profile=args.master_search_profile,
    )
    print("phase3b anchor differential audit")
    print(f"- candidate: {report['candidate']['key']}")
    print(f"- evaluated: {bool(report['status'].get('evaluated', False))}")
    print(f"- outcome: {report['status'].get('outcome')}")
    print(f"- solver_invoked: {bool(report['metadata'].get('solver_invoked', True))}")
    if not args.no_write:
        output_dir = args.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "anchor_differential_audit.json"
        md_path = output_dir / "anchor_differential_audit.md"
        txt_path = output_dir / "anchor_differential_audit.txt"
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(render_phase3b_anchor_differential_audit_markdown(report), encoding="utf-8")
        txt_path.write_text(render_phase3b_anchor_differential_audit_text(report), encoding="utf-8")
        print(f"anchor_differential_audit_json={json_path}")
        print(f"anchor_differential_audit_md={md_path}")
        print(f"anchor_differential_audit_txt={txt_path}")
    return 0 if report["status"].get("completed") else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--campaign-state", type=Path, default=None)
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument("--anchor-indices", default="118,125")
    parser.add_argument("--sample-limit", type=int, default=2)
    parser.add_argument("--master-search-profile", default="exact_coordinate_guided_branching_v4")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def _parse_anchor_indices(raw_value: str) -> list[int]:
    return [int(token.strip()) for token in str(raw_value).split(",") if token.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
