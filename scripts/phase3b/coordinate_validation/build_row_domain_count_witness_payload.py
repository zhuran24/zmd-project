from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.coordinate_validation.row_domain_count_witness_payload import (
    build_phase3b_coordinate_validation_row_domain_count_witness_payload,
    render_phase3b_coordinate_validation_row_domain_count_witness_payload_markdown,
    render_phase3b_coordinate_validation_row_domain_count_witness_payload_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Phase 3B coordinate-validation row-domain count witness payload artifact."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--row-domain-count-witness-design", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            ".artifacts/phase3b_coordinate_validation_row_domain_count_witness_payload"
        ),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = Path(args.output_dir)

    report = build_phase3b_coordinate_validation_row_domain_count_witness_payload(
        project_root,
        row_domain_count_witness_design_path=args.row_domain_count_witness_design,
    )

    if args.no_write:
        print("phase3b coordinate-validation row-domain count witness payload")
        print(f"payload_ready={bool(report.get('status', {}).get('payload_ready', False))}")
        print(
            "recommended_next_step="
            + str(report.get("status", {}).get("recommended_next_step"))
        )
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "row_domain_count_witness_payload.json"
    md_path = output_dir / "row_domain_count_witness_payload.md"
    txt_path = output_dir / "row_domain_count_witness_payload.txt"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(
        render_phase3b_coordinate_validation_row_domain_count_witness_payload_markdown(
            report
        ),
        encoding="utf-8",
    )
    txt_path.write_text(
        render_phase3b_coordinate_validation_row_domain_count_witness_payload_text(
            report
        ),
        encoding="utf-8",
    )

    print(f"row_domain_count_witness_payload_json={json_path.resolve()}")
    print(f"row_domain_count_witness_payload_md={md_path.resolve()}")
    print(f"row_domain_count_witness_payload_txt={txt_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
