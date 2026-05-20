from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.direct_equality.core_exchange import (
    build_phase3b_direct_equality_core_exchange,
    render_phase3b_direct_equality_core_exchange_markdown,
    render_phase3b_direct_equality_core_exchange_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded Phase 3B direct-equality core-exchange diagnostic."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--core-json", action="append", default=[])
    parser.add_argument(
        "--group-id",
        default="group::manufacturing_6x4::grinder_dense_blue_iron::14",
    )
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument("--anchor-index", type=int, default=119)
    parser.add_argument("--field-variant", default="x_y_mode")
    parser.add_argument("--subset-size", type=int, default=3)
    parser.add_argument("--max-subsets", type=int, default=16)
    parser.add_argument("--time-limit-seconds", type=float, default=2.0)
    parser.add_argument("--worker-count", type=int, default=1)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_direct_equality_core_exchange"),
    )
    parser.add_argument("--output-prefix", default="direct_equality_core_exchange_m6x4_anchor119")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    core_paths = [Path(item) for item in list(args.core_json)]
    if not core_paths:
        core_paths = [
            Path(
                ".artifacts/phase3b_direct_equality_core_manufacturing_template_followup_anchor119/"
                "core_m6x4_grinder_dense_blue_iron_x_y_mode_anchor119.json"
            ),
            Path(
                ".artifacts/phase3b_direct_equality_core_anchor_sweep_118_125/"
                "core_m6x4_grinder_dense_blue_iron_anchor119.json"
            ),
        ]
    report = build_phase3b_direct_equality_core_exchange(
        project_root,
        core_paths=core_paths,
        group_id=str(args.group_id),
        candidate=str(args.candidate),
        anchor_idx=int(args.anchor_index),
        field_variant=str(args.field_variant),
        subset_size=int(args.subset_size),
        max_subsets=int(args.max_subsets),
        time_limit_seconds=float(args.time_limit_seconds),
        worker_count=int(args.worker_count),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = str(args.output_prefix)
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_direct_equality_core_exchange_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_direct_equality_core_exchange_text(report),
        )
        print(f"direct_equality_core_exchange_json={_display_path(project_root, json_path)}")
        print(f"direct_equality_core_exchange_md={_display_path(project_root, md_path)}")
        print(f"direct_equality_core_exchange_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: dict) -> None:
    summary = report.get("summary", {})
    status = report.get("status", {})
    print("phase3b direct-equality core exchange")
    print("- diagnostic semantics: bounded_core_exchange_not_proof_source")
    print("- proof source: false")
    print("- solver invoked: true")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- union key count: {summary.get('union_key_count')}")
    print(f"- evaluated subsets: {summary.get('evaluated_subset_count')}")
    print(f"- status counts: {summary.get('status_counts')}")
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


if __name__ == "__main__":
    raise SystemExit(main())
