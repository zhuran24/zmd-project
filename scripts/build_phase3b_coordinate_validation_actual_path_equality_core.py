from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import atomic_write_json
from src.search.phase3b_coordinate_validation_actual_path_equality_core import (
    DEFAULT_ACTUAL_PATH_EQUALITY_FIELD_VARIANT,
    build_phase3b_coordinate_validation_actual_path_equality_core,
    render_phase3b_coordinate_validation_actual_path_equality_core_markdown,
    render_phase3b_coordinate_validation_actual_path_equality_core_text,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Phase 3B actual-path coordinate validation equality-core diagnostic."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--candidate", default="67x13")
    parser.add_argument("--anchor-index", type=int, default=133)
    parser.add_argument("--field-variant", default=DEFAULT_ACTUAL_PATH_EQUALITY_FIELD_VARIANT)
    parser.add_argument(
        "--master-search-profile",
        default=DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    )
    parser.add_argument("--time-limit-seconds", type=float, default=10.0)
    parser.add_argument("--worker-count", type=int, default=1)
    parser.add_argument("--max-delete-tests", type=int, default=64)
    parser.add_argument(
        "--skip-single-delete",
        action="store_true",
        help="Spend the deletion budget directly on greedy shrink instead of the initial single-delete scan.",
    )
    parser.add_argument(
        "--solver-profile-json",
        default=None,
        help="Optional JSON object merged into the validation solver profile.",
    )
    parser.add_argument(
        "--initial-keys-file",
        type=Path,
        default=None,
        help=(
            "Optional JSON file containing a key list, or an existing equality-core "
            "report with actual_path.final_keys, used to continue shrinking."
        ),
    )
    parser.add_argument(
        "--no-validate-initial-keys",
        action="store_true",
        help="Do not run the one-shot validation of supplied initial keys before continuing.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_coordinate_validation_actual_path_equality_core"),
    )
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_coordinate_validation_actual_path_equality_core(
        project_root,
        candidate=str(args.candidate),
        anchor_idx=int(args.anchor_index),
        field_variant=str(args.field_variant),
        master_search_profile=str(args.master_search_profile),
        time_limit_seconds=float(args.time_limit_seconds),
        worker_count=int(args.worker_count),
        max_delete_tests=int(args.max_delete_tests),
        skip_single_delete=bool(args.skip_single_delete),
        initial_keys=_load_initial_keys(args.initial_keys_file),
        validate_initial_keys=not bool(args.no_validate_initial_keys),
        solver_parameter_profile=_parse_solver_profile(args.solver_profile_json),
    )
    _print_summary(report)
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        prefix = args.output_prefix or "coordinate_validation_actual_path_equality_core"
        json_path = output_dir / f"{prefix}.json"
        md_path = output_dir / f"{prefix}.md"
        txt_path = output_dir / f"{prefix}.txt"
        atomic_write_json(json_path, report)
        _atomic_write_text(
            md_path,
            render_phase3b_coordinate_validation_actual_path_equality_core_markdown(
                report
            ),
        )
        _atomic_write_text(
            txt_path,
            render_phase3b_coordinate_validation_actual_path_equality_core_text(report),
        )
        print(f"actual_path_equality_core_json={_display_path(project_root, json_path)}")
        print(f"actual_path_equality_core_md={_display_path(project_root, md_path)}")
        print(f"actual_path_equality_core_txt={_display_path(project_root, txt_path)}")
    return 0


def _print_summary(report: Mapping[str, Any]) -> None:
    status = _mapping(report.get("status"))
    actual = _mapping(report.get("actual_path"))
    full = _mapping(actual.get("full_validation"))
    print("phase3b actual-path coordinate validation equality core")
    print(f"- outcome: {status.get('outcome')}")
    print(f"- full status: {full.get('status')}")
    print(f"- equality labels: {actual.get('equality_label_count')}")
    print(f"- deletion tests: {actual.get('deletion_test_count')}")
    print(f"- final key count: {actual.get('final_key_count')}")
    print(f"- recommendation: {status.get('recommendation')}")


def _parse_solver_profile(raw_value: str | None) -> dict[str, Any] | None:
    if raw_value is None or not str(raw_value).strip():
        return None
    text = str(raw_value).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = json.loads(text.replace("'", '"'))
    if not isinstance(parsed, Mapping):
        raise ValueError("--solver-profile-json must be a JSON object")
    return dict(parsed)


def _load_initial_keys(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    source = Path(path).resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [str(item) for item in payload]
    if isinstance(payload, Mapping):
        if isinstance(payload.get("final_keys"), list):
            return [str(item) for item in payload["final_keys"]]
        actual_path = payload.get("actual_path")
        if isinstance(actual_path, Mapping) and isinstance(
            actual_path.get("final_keys"),
            list,
        ):
            return [str(item) for item in actual_path["final_keys"]]
        if isinstance(payload.get("keys"), list):
            return [str(item) for item in payload["keys"]]
    raise ValueError(
        "--initial-keys-file must contain a JSON list, final_keys, keys, "
        "or actual_path.final_keys."
    )


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
