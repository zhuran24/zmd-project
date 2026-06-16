from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.anchor119.guarded_precheck_spec import (
    DEFAULT_DP_CROSSCHECK_PATH,
    DEFAULT_ROW_DOMAIN_GUARD_SPEC_PATH,
    DEFAULT_SYNTHESIS_PATH,
    DEFAULT_TILING_REPORT_PATH,
    build_phase3b_anchor119_guarded_precheck_spec,
    write_phase3b_anchor119_guarded_precheck_spec,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B anchor119 guarded/default-off precheck spec."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--synthesis", type=Path, default=DEFAULT_SYNTHESIS_PATH)
    parser.add_argument("--tiling-report", type=Path, default=DEFAULT_TILING_REPORT_PATH)
    parser.add_argument("--dp-crosscheck", type=Path, default=DEFAULT_DP_CROSSCHECK_PATH)
    parser.add_argument(
        "--row-domain-guard-spec", type=Path, default=DEFAULT_ROW_DOMAIN_GUARD_SPEC_PATH
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_anchor119_guarded_precheck_spec_20260424"),
    )
    parser.add_argument("--output-prefix", default="guarded_precheck_spec")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_anchor119_guarded_precheck_spec(
        project_root,
        synthesis_path=Path(args.synthesis),
        tiling_report_path=Path(args.tiling_report),
        dp_crosscheck_path=Path(args.dp_crosscheck),
        row_domain_guard_spec_path=Path(args.row_domain_guard_spec),
    )
    _print_summary(report)
    if not bool(args.no_write):
        output_dir = _resolve_output_dir(project_root, Path(args.output_dir))
        paths = write_phase3b_anchor119_guarded_precheck_spec(
            report,
            output_dir,
            output_prefix=str(args.output_prefix),
        )
        for key, value in paths.items():
            print(f"guarded_precheck_spec_{key}={_display_path(project_root, Path(value))}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    evidence = _mapping(report.get("evidence"))
    print("phase3b anchor119 guarded precheck spec")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- all_gates_pass: {status.get('all_gates_pass')}")
    print("- runtime_precheck_enabled: false")
    print("- runtime_semantics_changed: false")
    print("- proof_source: false")
    print(f"- tiling_outcome: {evidence.get('tiling_outcome')}")
    print(f"- dp_outcome: {evidence.get('dp_outcome')}")
    print(f"- domain_hash_match: {evidence.get('domain_hash_match')}")
    print(f"- payload_id: {evidence.get('payload_id')}")
    print(
        "- non_trigger_max_slot_count: "
        + str(evidence.get("non_trigger_max_slot_count"))
    )


def _resolve_output_dir(project_root: Path, output_dir: Path) -> Path:
    if Path(output_dir).is_absolute():
        return Path(output_dir).resolve()
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
