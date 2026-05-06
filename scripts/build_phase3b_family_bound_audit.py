from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_family_bound_audit import (
    DEFAULT_TARGET_POWER_FAMILY,
    build_phase3b_family_bound_audit,
    render_phase3b_family_bound_audit_markdown,
    render_phase3b_family_bound_audit_text,
)
from src.search.phase3b_forced_anchor_master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Phase 3B conditioned power-family bound derivation for selected anchors."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--campaign-state", type=Path, default=DEFAULT_CAMPAIGN_STATE_PATH)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument("--sample-limit", type=int, default=1)
    parser.add_argument(
        "--anchor-indices",
        default=None,
        help="Optional comma-separated anchor indices to audit.",
    )
    parser.add_argument("--target-power-family", default=DEFAULT_TARGET_POWER_FAMILY)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_family_bound_audit"),
    )
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_family_bound_audit(
        project_root,
        campaign_state_path=args.campaign_state,
        candidate=str(args.candidate),
        sample_limit=int(args.sample_limit),
        anchor_indices=_parse_anchor_indices(args.anchor_indices),
        target_power_family=str(args.target_power_family),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = args.output_prefix or (
            f"family_bound_audit_{str(args.candidate)}_{str(args.target_power_family)}"
        )
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_family_bound_audit_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_family_bound_audit_text(report))
        print(f"family_bound_audit_json={_display_path(project_root, json_path)}")
        print(f"family_bound_audit_md={_display_path(project_root, md_path)}")
        print(f"family_bound_audit_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    summary = _mapping(report.get("summary"))
    print("phase3b family bound audit")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- all bounds consistent: {summary.get('all_bounds_consistent')}")
    for audit in list(report.get("audits", [])):
        if not isinstance(audit, Mapping):
            continue
        derivation = _mapping(audit.get("derivation"))
        proto = _mapping(audit.get("proto_constraint"))
        print(
            "- audit "
            f"anchor={audit.get('anchor_idx')} "
            f"family={audit.get('target_power_family')} "
            f"family_size={derivation.get('family_size')} "
            f"blocked={derivation.get('blocked_family_pose_count')} "
            f"global_ub={derivation.get('global_upper_bound')} "
            f"derived_ub={derivation.get('derived_conditioned_upper_bound')} "
            f"domain_ub={derivation.get('domain_conditioned_upper_bound')} "
            f"proto_ub={proto.get('implied_conditioned_upper_bound')} "
            f"consistent={audit.get('bounds_consistent')}"
        )
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_anchor_indices(raw_value: str | None) -> list[int] | None:
    if raw_value is None or not str(raw_value).strip():
        return None
    return [int(token.strip()) for token in str(raw_value).split(",") if token.strip()]


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
