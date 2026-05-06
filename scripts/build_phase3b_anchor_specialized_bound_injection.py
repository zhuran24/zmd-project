from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_anchor_specialized_bound_injection import (
    DEFAULT_FAMILY_BOUND_FORMULATION_PROBE_PATH,
    DEFAULT_POWER_PROTOCOL_INTERACTION_PATH,
    build_phase3b_anchor_specialized_bound_injection_spec,
    render_phase3b_anchor_specialized_bound_injection_markdown,
    render_phase3b_anchor_specialized_bound_injection_text,
)
from src.search.phase3b_family_bound_formulation_probe import (
    DEFAULT_DIRECT_BOUND_SLICE_PATH,
    DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a guarded Phase 3B target-family anchor-specialized direct-bound injection spec."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--direct-bound-slice",
        type=Path,
        default=DEFAULT_DIRECT_BOUND_SLICE_PATH,
    )
    parser.add_argument(
        "--family-bound-semantic-audit",
        type=Path,
        default=DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH,
    )
    parser.add_argument(
        "--family-bound-formulation-probe",
        type=Path,
        default=DEFAULT_FAMILY_BOUND_FORMULATION_PROBE_PATH,
    )
    parser.add_argument(
        "--power-protocol-interaction",
        type=Path,
        default=DEFAULT_POWER_PROTOCOL_INTERACTION_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_anchor_specialized_bound_injection"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_anchor_specialized_bound_injection_spec(
        project_root,
        direct_bound_slice_path=args.direct_bound_slice,
        family_bound_semantic_audit_path=args.family_bound_semantic_audit,
        family_bound_formulation_probe_path=args.family_bound_formulation_probe,
        power_protocol_interaction_path=args.power_protocol_interaction,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "anchor_specialized_bound_injection.json"
        md_path = output_dir / "anchor_specialized_bound_injection.md"
        txt_path = output_dir / "anchor_specialized_bound_injection.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_anchor_specialized_bound_injection_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_anchor_specialized_bound_injection_text(report),
        )
        print(f"anchor_specialized_bound_injection_json={_display_path(project_root, json_path)}")
        print(f"anchor_specialized_bound_injection_md={_display_path(project_root, md_path)}")
        print(f"anchor_specialized_bound_injection_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    gate = _mapping(report.get("gate"))
    spec = _mapping(report.get("injection_spec"))
    target = _mapping(spec.get("target"))
    print("phase3b anchor-specialized bound injection")
    print(f"- diagnostic spec ready: {gate.get('diagnostic_spec_ready')}")
    print(f"- workspace diagnostic rerun allowed: {gate.get('workspace_diagnostic_rerun_allowed')}")
    print(f"- runtime promotion ready: {gate.get('runtime_promotion_ready')}")
    print(f"- final long-run ready: {gate.get('final_long_run_ready')}")
    print(f"- target anchor: {target.get('anchor_idx')}")
    print(f"- target family: {target.get('target_power_family')}")
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
