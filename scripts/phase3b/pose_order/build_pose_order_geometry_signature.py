from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b.pose_order.pose_order_geometry_signature import (
    build_phase3b_pose_order_geometry_signature,
    render_phase3b_pose_order_geometry_signature_markdown,
    render_phase3b_pose_order_geometry_signature_text,
)
from src.search.phase3b.pose_order.residual_pose_order_taxonomy import DEFAULT_RESIDUAL_ANCHORS


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a report-only Phase 3B pose-order geometry signature."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--anchors",
        default=",".join(str(anchor) for anchor in DEFAULT_RESIDUAL_ANCHORS),
    )
    parser.add_argument("--artifact-root", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_pose_order_geometry_signature"),
    )
    parser.add_argument("--output-prefix", default="pose_order_geometry_signature")
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_pose_order_geometry_signature(
        project_root,
        anchors=_parse_anchor_list(args.anchors),
        artifact_root=args.artifact_root,
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
            render_phase3b_pose_order_geometry_signature_markdown(report),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_pose_order_geometry_signature_text(report),
        )
        print(f"pose_order_geometry_signature_json={_display_path(project_root, json_path)}")
        print(f"pose_order_geometry_signature_md={_display_path(project_root, md_path)}")
        print(f"pose_order_geometry_signature_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    print("phase3b pose-order geometry signature")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- summarized anchors: {status.get('summarized_anchor_count')}")
    print(f"- missing greedy artifacts: {status.get('missing_greedy_artifact_count')}")
    print(f"- runtime promotion ready: {status.get('runtime_promotion_ready')}")
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_anchor_list(raw: str) -> list[int]:
    return [int(part.strip()) for part in str(raw).split(",") if part.strip()]


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
