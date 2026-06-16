from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.coordinate_validation.anchor119_row_domain.bridge_candidate import (
    build_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate,
    render_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B coordinate-validation anchor119 row-domain bridge candidate."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--row-domain-count-witness-payload", type=Path, default=None)
    parser.add_argument("--guarded-precheck-spec", type=Path, default=None)
    parser.add_argument("--guarded-precheck-advisory-enabled", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = build_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate(
        project_root,
        row_domain_count_witness_payload_path=args.row_domain_count_witness_payload,
        guarded_precheck_spec_path=args.guarded_precheck_spec,
        guarded_precheck_advisory_enabled_path=args.guarded_precheck_advisory_enabled,
    )

    if args.no_write:
        print("phase3b coordinate-validation anchor119 row-domain bridge candidate")
        print(
            "bridge_ready_for_review="
            + str(bool(report.get("status", {}).get("bridge_ready_for_review", False)))
        )
        print(
            "recommended_next_step="
            + str(report.get("status", {}).get("recommended_next_step"))
        )
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "anchor119_row_domain_bridge_candidate.json"
    md_path = output_dir / "anchor119_row_domain_bridge_candidate.md"
    txt_path = output_dir / "anchor119_row_domain_bridge_candidate.txt"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_anchor119_row_domain_bridge_candidate_text(
            report
        ),
        encoding="utf-8",
    )

    print(f"anchor119_row_domain_bridge_candidate_json={json_path.resolve()}")
    print(f"anchor119_row_domain_bridge_candidate_md={md_path.resolve()}")
    print(f"anchor119_row_domain_bridge_candidate_txt={txt_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
