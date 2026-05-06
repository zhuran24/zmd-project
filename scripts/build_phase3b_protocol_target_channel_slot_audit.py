from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_protocol_target_channel_slot_audit import (
    DEFAULT_ANCHOR_DIFFERENTIAL_PATH,
    DEFAULT_ANCHOR_INDICES,
    DEFAULT_CANDIDATE,
    DEFAULT_FAMILY_NAMES,
    DEFAULT_POWERED_TEMPLATE,
    DEFAULT_PROTO_REDUCTION_PATH,
    DEFAULT_TARGET_TOKENS,
    build_phase3b_protocol_target_channel_slot_audit,
    render_phase3b_protocol_target_channel_slot_audit_markdown,
    render_phase3b_protocol_target_channel_slot_audit_text,
)


DEFAULT_OUTPUT_DIR = Path(".artifacts/phase3b_protocol_target_channel_slot_audit")


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_protocol_target_channel_slot_audit(
        project_root,
        campaign_state_path=args.campaign_state,
        proto_reduction_path=args.proto_reduction,
        anchor_differential_path=args.anchor_differential,
        candidate=str(args.candidate),
        anchor_indices=_parse_int_csv(args.anchor_indices),
        powered_template=str(args.powered_template),
        target_tokens=_parse_csv(args.target_tokens),
        family_names=_parse_csv(args.family_names),
        master_search_profile=str(args.master_search_profile),
        power_family_lookup_encoding=args.power_family_lookup_encoding,
        power_pole_shell_distance_encoding=args.power_pole_shell_distance_encoding,
        power_coverage_witness_encoding=args.power_coverage_witness_encoding,
        power_coverage_witness_block_geometry=args.power_coverage_witness_block_geometry,
        power_coverage_witness_block_size=args.power_coverage_witness_block_size,
        power_coverage_witness_block_templates=args.power_coverage_witness_block_templates,
        power_coverage_selected_interval_encoding=args.power_coverage_selected_interval_encoding,
        sample_limit=int(args.sample_limit),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "protocol_target_channel_slot_audit.json"
        md_path = output_dir / "protocol_target_channel_slot_audit.md"
        txt_path = output_dir / "protocol_target_channel_slot_audit.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_protocol_target_channel_slot_audit_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_protocol_target_channel_slot_audit_text(report),
        )
        print(f"protocol_target_channel_slot_audit_json={_display_path(project_root, json_path)}")
        print(f"protocol_target_channel_slot_audit_md={_display_path(project_root, md_path)}")
        print(f"protocol_target_channel_slot_audit_txt={_display_path(project_root, txt_path)}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a no-solve Phase 3B protocol target-channel slot audit."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--campaign-state", type=Path, default=None)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument(
        "--anchor-indices",
        default=",".join(str(idx) for idx in DEFAULT_ANCHOR_INDICES),
    )
    parser.add_argument("--powered-template", default=DEFAULT_POWERED_TEMPLATE)
    parser.add_argument("--target-tokens", default=",".join(DEFAULT_TARGET_TOKENS))
    parser.add_argument("--family-names", default=",".join(DEFAULT_FAMILY_NAMES))
    parser.add_argument(
        "--proto-reduction",
        type=Path,
        default=DEFAULT_PROTO_REDUCTION_PATH,
    )
    parser.add_argument(
        "--anchor-differential",
        type=Path,
        default=DEFAULT_ANCHOR_DIFFERENTIAL_PATH,
    )
    parser.add_argument(
        "--master-search-profile",
        default="exact_coordinate_guided_branching_v4",
    )
    parser.add_argument("--power-family-lookup-encoding", default="linear_shell_guards")
    parser.add_argument("--power-pole-shell-distance-encoding", default="linear_minmax")
    parser.add_argument("--power-coverage-witness-encoding", default="block_element")
    parser.add_argument("--power-coverage-witness-block-geometry", default="final_target")
    parser.add_argument("--power-coverage-witness-block-size", type=int, default=64)
    parser.add_argument(
        "--power-coverage-witness-block-templates",
        default="",
        help="Empty string means all powered templates, matching the all-template block64 diagnostic artifacts.",
    )
    parser.add_argument("--power-coverage-selected-interval-encoding", default="delta")
    parser.add_argument("--sample-limit", type=int, default=12)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def _print_summary(report: dict[str, Any]) -> None:
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    comparison = _mapping(report.get("comparison"))
    print("phase3b protocol target-channel slot audit")
    print(f"- candidate: {_mapping(report.get('candidate')).get('key')}")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}")
    print(f"- diagnostic signal: {summary.get('diagnostic_signal')}")
    print(f"- divergent targets: {comparison.get('divergent_targets', [])}")
    print(f"- next probe hint: {summary.get('next_probe_hint')}")


def _parse_csv(raw_value: str | Sequence[str]) -> list[str]:
    if isinstance(raw_value, str):
        return [token.strip() for token in raw_value.split(",") if token.strip()]
    return [str(token).strip() for token in raw_value if str(token).strip()]


def _parse_int_csv(raw_value: str | Sequence[int]) -> list[int]:
    if isinstance(raw_value, str):
        return [int(token.strip()) for token in raw_value.split(",") if token.strip()]
    return [int(token) for token in raw_value]


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


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
