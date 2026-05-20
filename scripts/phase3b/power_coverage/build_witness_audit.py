from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.power_coverage.witness_audit import (
    DEFAULT_POWER_COVERAGE_CORE_BLOCKER_PATH,
    DEFAULT_POWER_COVERAGE_RELAX_SLICE_PATH,
    build_phase3b_power_coverage_witness_audit,
    render_phase3b_power_coverage_witness_audit_markdown,
    render_phase3b_power_coverage_witness_audit_text,
)
from src.search.phase3b.power_protocol.interaction import (
    DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B power-coverage witness/domain audit from current diagnostic artifacts."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--residual-optional-encoding",
        type=Path,
        default=DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
    )
    parser.add_argument(
        "--power-coverage-core-blocker",
        type=Path,
        default=DEFAULT_POWER_COVERAGE_CORE_BLOCKER_PATH,
    )
    parser.add_argument(
        "--power-coverage-relax-slice",
        type=Path,
        default=DEFAULT_POWER_COVERAGE_RELAX_SLICE_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_power_coverage_witness_audit"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_power_coverage_witness_audit(
        project_root,
        residual_optional_encoding_path=args.residual_optional_encoding,
        power_coverage_core_blocker_path=args.power_coverage_core_blocker,
        power_coverage_relax_slice_path=args.power_coverage_relax_slice,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "power_coverage_witness_audit.json"
        md_path = output_dir / "power_coverage_witness_audit.md"
        txt_path = output_dir / "power_coverage_witness_audit.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_power_coverage_witness_audit_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_power_coverage_witness_audit_text(report))
        print(f"power_coverage_witness_audit_json={_display_path(project_root, json_path)}")
        print(f"power_coverage_witness_audit_md={_display_path(project_root, md_path)}")
        print(f"power_coverage_witness_audit_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    witness = _mapping(report.get("witness_encoding"))
    pressure = _mapping(report.get("domain_pressure"))
    print("phase3b power-coverage witness audit")
    print(f"- classification: {report.get('classification')}")
    print(f"- encoding: {witness.get('encoding')}")
    print(f"- powered slots: {witness.get('powered_slots')}")
    print(f"- pole slots: {witness.get('pole_slots')}")
    print(f"- witness indices: {witness.get('witness_indices')}")
    print(f"- element constraints: {witness.get('element_constraints')}")
    print(f"- core blocker: {pressure.get('core_blocker_classification')}")
    print(f"- recommendation: {report.get('recommendation')}")


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
