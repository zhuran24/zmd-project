from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.group_packing.proof_promotion import (
    DEFAULT_B5A_SUMMARY_PATH,
    DEFAULT_GHOST_ONLY_VERIFIER_PATH,
    DEFAULT_PRE_MASTER_PROFILE_PATH,
    DEFAULT_PROMOTION_SPEC_PATH,
    DEFAULT_RUNTIME_DIAGNOSTIC_PATH,
    DEFAULT_SOUNDNESS_GATE_PATH,
    build_phase3b_group_packing_proof_promotion_blockers,
    render_phase3b_group_packing_proof_promotion_markdown,
    render_phase3b_group_packing_proof_promotion_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B group-packing proof-promotion blocker report."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--promotion-spec", type=Path, default=DEFAULT_PROMOTION_SPEC_PATH)
    parser.add_argument(
        "--runtime-diagnostic",
        type=Path,
        default=DEFAULT_RUNTIME_DIAGNOSTIC_PATH,
    )
    parser.add_argument(
        "--soundness-gate",
        type=Path,
        default=DEFAULT_SOUNDNESS_GATE_PATH,
    )
    parser.add_argument(
        "--ghost-only-verifier",
        type=Path,
        default=DEFAULT_GHOST_ONLY_VERIFIER_PATH,
    )
    parser.add_argument(
        "--pre-master-profile",
        type=Path,
        default=DEFAULT_PRE_MASTER_PROFILE_PATH,
    )
    parser.add_argument("--b5a-summary", type=Path, default=DEFAULT_B5A_SUMMARY_PATH)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_group_packing_proof_promotion"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_group_packing_proof_promotion_blockers(
        project_root,
        promotion_spec_path=args.promotion_spec,
        runtime_diagnostic_path=args.runtime_diagnostic,
        soundness_gate_path=args.soundness_gate,
        ghost_only_verifier_path=args.ghost_only_verifier,
        pre_master_profile_path=args.pre_master_profile,
        b5a_summary_path=args.b5a_summary,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "proof_promotion_blockers.json"
        md_path = output_dir / "proof_promotion_blockers.md"
        txt_path = output_dir / "proof_promotion_blockers.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_group_packing_proof_promotion_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_group_packing_proof_promotion_text(report))
        print(f"proof_promotion_blockers_json={_display_path(project_root, json_path)}")
        print(f"proof_promotion_blockers_md={_display_path(project_root, md_path)}")
        print(f"proof_promotion_blockers_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    readiness = _mapping(report.get("promotion_readiness"))
    print("phase3b group-packing proof-promotion blockers")
    print(f"- candidate: {candidate.get('key')}")
    print(
        "- diagnostic evidence ready: "
        f"{bool(readiness.get('diagnostic_evidence_ready', False))}"
    )
    print(
        "- proof promotion ready: "
        f"{bool(readiness.get('proof_promotion_ready', False))}"
    )
    print(f"- blocked by: {list(readiness.get('blocked_by', []))}")
    print(f"- recommendation: {readiness.get('recommendation')}")


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
