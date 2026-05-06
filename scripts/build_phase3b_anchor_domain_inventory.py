from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_anchor_domain_inventory import (
    build_phase3b_anchor_domain_inventory,
    render_phase3b_anchor_domain_inventory_markdown,
    render_phase3b_anchor_domain_inventory_text,
)
from src.search.phase3b_forced_anchor_master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B anchor domain/slot inventory for selected forced anchors."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--campaign-state", type=Path, default=DEFAULT_CAMPAIGN_STATE_PATH)
    parser.add_argument("--candidate", default=DEFAULT_CANDIDATE)
    parser.add_argument("--sample-limit", type=int, default=3)
    parser.add_argument(
        "--anchor-indices",
        default=None,
        help="Optional comma-separated anchor indices to inspect instead of the first sampled anchors.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_anchor_domain_inventory"),
    )
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_anchor_domain_inventory(
        project_root,
        campaign_state_path=args.campaign_state,
        candidate=str(args.candidate),
        sample_limit=int(args.sample_limit),
        anchor_indices=_parse_anchor_indices(args.anchor_indices),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = args.output_prefix or f"anchor_domain_inventory_{str(args.candidate)}"
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_anchor_domain_inventory_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_anchor_domain_inventory_text(report))
        print(f"anchor_domain_inventory_json={_display_path(project_root, json_path)}")
        print(f"anchor_domain_inventory_md={_display_path(project_root, md_path)}")
        print(f"anchor_domain_inventory_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    print("phase3b anchor domain inventory")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- evaluated: {bool(status.get('evaluated', False))}")
    print(f"- outcome: {status.get('outcome')}")
    for entry in list(report.get("anchors", [])):
        if not isinstance(entry, Mapping):
            continue
        summary = _mapping(entry.get("summary"))
        tightest = _mapping(entry.get("tightest_mandatory_group"))
        print(
            "- anchor "
            f"{entry.get('anchor_idx')}: "
            f"mandatory_survivors={summary.get('mandatory_surviving_total')} "
            f"optional_survivors={summary.get('optional_surviving_total')} "
            f"tightest={tightest.get('group_id')}:{tightest.get('surviving_count')}"
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
