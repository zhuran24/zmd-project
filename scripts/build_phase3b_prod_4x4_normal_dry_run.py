from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.exact_campaign import atomic_write_json, now_iso


DRY_RUN_SOURCE = "phase3b_prod_4x4_normal_cross_platform_dry_run_v1"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a cross-platform Phase3B prod_4x4_normal dry-run validation "
            "artifact without launching the final 168h run."
        )
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".artifacts/phase3b_prod_4x4_normal_dry_run_20260426"),
    )
    parser.add_argument("--output-prefix", default="prod_4x4_normal_dry_run")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument(
        "--allow-failed-exit-zero",
        action="store_true",
        help="Return exit code 0 even when the dry-run validation is not ready.",
    )
    return parser.parse_args()


def build_phase3b_prod_4x4_normal_dry_run(project_root: Path) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    script_path = project_root / "scripts" / "run_prod_4x4_normal.ps1"
    script_text = ""
    load_error = None
    try:
        script_text = script_path.read_text(encoding="utf-8-sig")
    except Exception as exc:
        load_error = f"{type(exc).__name__}: {exc}"
    checks = [
        _check(
            "runner_script_present",
            load_error is None,
            "scripts/run_prod_4x4_normal.ps1 loaded"
            if load_error is None
            else str(load_error),
        ),
        _check(
            "runner_supports_dry_run",
            "[switch]$DryRun" in script_text and "-DryRun:$DryRun" in script_text,
            "runner exposes and forwards DryRun",
        ),
        _check(
            "runner_locks_parallel_processes_4",
            '"--parallel-processes", "4"' in script_text,
            "runner locks --parallel-processes 4",
        ),
        _check(
            "runner_locks_sat_workers_4",
            '"EXACT_CP_SAT_WORKERS" = "4"' in script_text,
            "runner locks EXACT_CP_SAT_WORKERS=4",
        ),
        _check(
            "runner_uses_certified_exact_mode",
            '"--mode", "certified_exact"' in script_text,
            "runner locks certified_exact mode",
        ),
        _check(
            "dry_run_does_not_authorize_final_launch",
            True,
            "this Python artifact is validation-only and never invokes the runner",
        ),
    ]
    ready = all(check["status"] == "pass" for check in checks)
    return {
        "metadata": {
            "source": DRY_RUN_SOURCE,
            "generated_at": now_iso(),
            "project_root": str(project_root),
            "cross_platform": True,
            "validation_only": True,
        },
        "paths": {
            "runner_script": _display_path(project_root, script_path),
        },
        "status": {
            "dry_run_validation_ready": bool(ready),
            "final_168h_authorized": False,
            "runtime_elimination_authorized": False,
            "checkpoint_written": False,
            "checkpoint_write_or_import_back_authorized": False,
            "release_viewer_frontdoor_status_promoted": False,
            "would_start_final_168h": False,
            "recommended_next_step": (
                "include_this_artifact_in_pre_production_full_audit_package"
                if ready
                else "repair_prod_4x4_normal_runner_before_full_audit_package"
            ),
        },
        "dry_run": {
            "validated_command": (
                "powershell -ExecutionPolicy Bypass -File "
                "scripts/run_prod_4x4_normal.ps1 -ResumeCampaign -DryRun"
            ),
            "real_launch_command_not_authorized": (
                "powershell -ExecutionPolicy Bypass -File "
                "scripts/run_prod_4x4_normal.ps1 -ResumeCampaign"
            ),
            "python_script_invoked_runner": False,
        },
        "checks": checks,
    }


def write_phase3b_prod_4x4_normal_dry_run(
    report: Mapping[str, Any],
    output_dir: Path,
    *,
    output_prefix: str = "prod_4x4_normal_dry_run",
) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{output_prefix}.json"
    md_path = output_dir / f"{output_prefix}.md"
    txt_path = output_dir / f"{output_prefix}.txt"
    atomic_write_json(json_path, dict(report))
    _atomic_write_text(md_path, render_markdown(report))
    _atomic_write_text(txt_path, render_text(report))
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def render_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "# Phase3B prod_4x4_normal Cross-Platform Dry-Run",
        "",
        f"- Dry-run validation ready: `{status.get('dry_run_validation_ready')}`",
        f"- Would start final 168h: `{status.get('would_start_final_168h')}`",
        f"- Final 168h authorized: `{status.get('final_168h_authorized')}`",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(check.get("check_id")),
                        _markdown_cell(check.get("status")),
                        _markdown_cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    lines = [
        "Phase3B prod_4x4_normal cross-platform dry-run",
        "dry_run_validation_ready="
        + str(bool(status.get("dry_run_validation_ready", False))),
        "would_start_final_168h="
        + str(bool(status.get("would_start_final_168h", False))),
        "final_168h_authorized="
        + str(bool(status.get("final_168h_authorized", False))),
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check="
                + str(check.get("check_id"))
                + " status="
                + str(check.get("status"))
                + " detail="
                + str(check.get("detail"))
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    report = build_phase3b_prod_4x4_normal_dry_run(project_root)
    print("phase3b prod_4x4_normal cross-platform dry-run")
    print(
        "dry_run_validation_ready="
        + str(bool(_mapping(report.get("status")).get("dry_run_validation_ready", False)))
    )
    print(
        "would_start_final_168h="
        + str(bool(_mapping(report.get("status")).get("would_start_final_168h", False)))
    )
    if not args.no_write:
        output_dir = _resolve_output_dir(project_root, args.output_dir)
        paths = write_phase3b_prod_4x4_normal_dry_run(
            report,
            output_dir,
            output_prefix=str(args.output_prefix),
        )
        print("prod_4x4_normal_dry_run_json=" + _display_path(project_root, Path(paths["json"])))
        print("prod_4x4_normal_dry_run_md=" + _display_path(project_root, Path(paths["md"])))
        print("prod_4x4_normal_dry_run_txt=" + _display_path(project_root, Path(paths["txt"])))
    ready = bool(_mapping(report.get("status")).get("dry_run_validation_ready", False))
    if ready:
        return 0
    return 0 if args.allow_failed_exit_zero else 2


def _check(check_id: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "check_id": str(check_id),
        "status": "pass" if passed else "fail",
        "detail": str(detail),
    }


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


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())
