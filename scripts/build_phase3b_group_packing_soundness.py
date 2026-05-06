from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_group_packing_soundness import (
    DEFAULT_RUNTIME_DIAGNOSTIC_PATH,
    build_phase3b_group_packing_soundness_gate,
    render_phase3b_group_packing_soundness_markdown,
    render_phase3b_group_packing_soundness_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Phase 3B group-packing terminal-proof soundness gate."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--runtime-diagnostic",
        type=Path,
        default=DEFAULT_RUNTIME_DIAGNOSTIC_PATH,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_group_packing_soundness"),
    )
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_group_packing_soundness_gate(
        project_root,
        runtime_diagnostic_path=args.runtime_diagnostic,
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        json_path = output_dir / "soundness_gate.json"
        md_path = output_dir / "soundness_gate.md"
        txt_path = output_dir / "soundness_gate.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(md_path, render_phase3b_group_packing_soundness_markdown(report))
        _atomic_write_text(txt_path, render_phase3b_group_packing_soundness_text(report))
        print(f"soundness_gate_json={_display_path(project_root, json_path)}")
        print(f"soundness_gate_md={_display_path(project_root, md_path)}")
        print(f"soundness_gate_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    candidate = _mapping(report.get("candidate"))
    soundness = _mapping(report.get("soundness"))
    print("phase3b group-packing soundness gate")
    print(f"- candidate: {candidate.get('key')}")
    print(f"- all samples infeasible: {bool(soundness.get('all_samples_infeasible', False))}")
    print(
        "- terminal elimination sound: "
        f"{bool(soundness.get('terminal_elimination_sound', False))}"
    )
    print(f"- blocked by: {list(soundness.get('blocked_by', []))}")
    print(f"- recommendation: {soundness.get('recommendation')}")


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
