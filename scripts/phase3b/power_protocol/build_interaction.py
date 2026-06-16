from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.power_protocol.interaction import (
    DEFAULT_FAMILY_BOUND_AUDIT_PATH,
    DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH,
    DEFAULT_FAMILY_BOUND_SOLVER_PROFILE_PATH,
    DEFAULT_FAMILY_BOUND_PARAMETER_PROBE_PATH,
    DEFAULT_FAMILY_BOUND_FORMULATION_PROBE_PATH,
    DEFAULT_FAMILY_LOOKUP_ASSIGNMENT_AUDIT_PATH,
    DEFAULT_FORCED_ANCHOR_PROTO_REDUCTION_PATH,
    DEFAULT_POWER_COVERAGE_WITNESS_AUDIT_PATH,
    DEFAULT_POWER_COVERAGE_WITNESS_DOMAIN_PATH,
    DEFAULT_POWER_CAPACITY_GVI_AUDIT_PATH,
    DEFAULT_POWER_COVERAGE_ANCHOR_DELTA_PATH,
    DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
    DEFAULT_ZERO_BRANCH_UNKNOWN_TRIAGE_PATH,
    build_phase3b_power_protocol_interaction_diagnostic,
    render_phase3b_power_protocol_interaction_markdown,
    render_phase3b_power_protocol_interaction_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B power/protocol interaction diagnostic from existing artifacts."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--power-coverage-anchor-delta",
        type=Path,
        default=DEFAULT_POWER_COVERAGE_ANCHOR_DELTA_PATH,
    )
    parser.add_argument(
        "--residual-optional-encoding",
        type=Path,
        default=DEFAULT_RESIDUAL_OPTIONAL_ENCODING_PATH,
    )
    parser.add_argument(
        "--zero-branch-unknown-triage",
        type=Path,
        default=DEFAULT_ZERO_BRANCH_UNKNOWN_TRIAGE_PATH,
    )
    parser.add_argument(
        "--model-slice-dir",
        type=Path,
        default=None,
        help="Optional single model-slice directory. Omit to use the built-in Phase 3B diagnostic directories.",
    )
    parser.add_argument(
        "--family-bound-audit",
        type=Path,
        default=DEFAULT_FAMILY_BOUND_AUDIT_PATH,
    )
    parser.add_argument(
        "--family-bound-semantic-audit",
        type=Path,
        default=DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH,
    )
    parser.add_argument(
        "--family-bound-solver-profile",
        type=Path,
        default=DEFAULT_FAMILY_BOUND_SOLVER_PROFILE_PATH,
    )
    parser.add_argument(
        "--family-bound-parameter-probe",
        type=Path,
        default=DEFAULT_FAMILY_BOUND_PARAMETER_PROBE_PATH,
    )
    parser.add_argument(
        "--family-bound-formulation-probe",
        type=Path,
        default=DEFAULT_FAMILY_BOUND_FORMULATION_PROBE_PATH,
    )
    parser.add_argument(
        "--power-coverage-witness-audit",
        type=Path,
        default=DEFAULT_POWER_COVERAGE_WITNESS_AUDIT_PATH,
    )
    parser.add_argument(
        "--power-coverage-witness-domain",
        type=Path,
        default=DEFAULT_POWER_COVERAGE_WITNESS_DOMAIN_PATH,
    )
    parser.add_argument(
        "--family-lookup-assignment-audit",
        type=Path,
        default=DEFAULT_FAMILY_LOOKUP_ASSIGNMENT_AUDIT_PATH,
    )
    parser.add_argument(
        "--forced-anchor-proto-reduction",
        type=Path,
        default=DEFAULT_FORCED_ANCHOR_PROTO_REDUCTION_PATH,
    )
    parser.add_argument(
        "--power-capacity-gvi-audit",
        type=Path,
        default=DEFAULT_POWER_CAPACITY_GVI_AUDIT_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_power_protocol_interaction"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_power_protocol_interaction_diagnostic(
        project_root,
        power_coverage_anchor_delta_path=args.power_coverage_anchor_delta,
        residual_optional_encoding_path=args.residual_optional_encoding,
        zero_branch_unknown_triage_path=args.zero_branch_unknown_triage,
        model_slice_dir=args.model_slice_dir,
        family_bound_audit_path=args.family_bound_audit,
        family_bound_semantic_audit_path=args.family_bound_semantic_audit,
        family_bound_solver_profile_path=args.family_bound_solver_profile,
        family_bound_parameter_probe_path=args.family_bound_parameter_probe,
        family_bound_formulation_probe_path=args.family_bound_formulation_probe,
        power_coverage_witness_audit_path=args.power_coverage_witness_audit,
        power_coverage_witness_domain_path=args.power_coverage_witness_domain,
        family_lookup_assignment_audit_path=args.family_lookup_assignment_audit,
        forced_anchor_proto_reduction_path=args.forced_anchor_proto_reduction,
        power_capacity_gvi_audit_path=args.power_capacity_gvi_audit,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "power_protocol_interaction.json"
        md_path = output_dir / "power_protocol_interaction.md"
        txt_path = output_dir / "power_protocol_interaction.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_power_protocol_interaction_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_power_protocol_interaction_text(report))
        print(f"power_protocol_interaction_json={_display_path(project_root, json_path)}")
        print(f"power_protocol_interaction_md={_display_path(project_root, md_path)}")
        print(f"power_protocol_interaction_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    analysis = _mapping(report.get("analysis"))
    power_delta = _mapping(report.get("power_coverage_anchor_delta"))
    zero_branch = _mapping(report.get("zero_branch_unknown_triage"))
    print("phase3b power/protocol interaction diagnostic")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- primary hypothesis: {analysis.get('primary_hypothesis')}")
    print(f"- next probe family: {analysis.get('next_probe_family')}")
    print(f"- next probe template: {analysis.get('next_probe_template')}")
    print(f"- zero-branch UNKNOWN: {zero_branch.get('zero_branch_unknown_count', 0)}")
    print(f"- power family changed count: {power_delta.get('power_family_changed_count', 0)}")
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
