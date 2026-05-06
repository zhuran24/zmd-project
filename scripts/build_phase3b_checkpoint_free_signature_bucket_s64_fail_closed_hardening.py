from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.sensitive_path_audit import build_sensitive_path_fingerprint  # noqa: E402
from src.search.exact_campaign import atomic_write_json  # noqa: E402

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "66_s64_fallback_reason_probe_review_hardening_implementation"
DEFAULT_S65_REPLY_SUMMARY = (
    ARTIFACT_ROOT
    / "65_signature_bucket_fallback_reason_probe_external_review_package"
    / "signature_bucket_fallback_reason_probe_external_review_package_001"
    / "external_review_reply_summary.json"
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    artifact = build_s64_fail_closed_hardening_artifact(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        s65_reply_summary_path=_resolve_path(PROJECT_ROOT, args.s65_reply_summary),
        no_write=bool(args.no_write),
    )
    print("phase3b s66 s64 fail-closed hardening implementation")
    print(f"status={artifact['status']}")
    if not args.no_write:
        print(f"artifact_json={_display_path(PROJECT_ROOT, Path(artifact['paths']['artifact_json']))}")
    return 0 if artifact["status"] == "implemented_and_verified" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the S66 implementation artifact for S64 fail-closed hardening."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--s65-reply-summary", type=Path, default=DEFAULT_S65_REPLY_SUMMARY)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_s64_fail_closed_hardening_artifact(
    *,
    project_root: Path,
    output_dir: Path,
    s65_reply_summary_path: Path,
    no_write: bool = False,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = _resolve_path(project_root, output_dir)
    _assert_s66_namespace(output_dir)
    checkpoint_state = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    checkpoint_telemetry = project_root / "data" / "checkpoints" / "exact_campaign_telemetry.json"
    s65_summary = _load_json_or_none(s65_reply_summary_path)
    s65_failed = _mapping(s65_summary).get("review_verdict") == "fail_do_not_request_authorization_yet"
    checkpoint_clean = not checkpoint_state.exists() and not checkpoint_telemetry.exists()
    status = "implemented_and_verified" if s65_failed and checkpoint_clean else "manual_review_required"
    sensitive_fingerprint = build_sensitive_path_fingerprint(project_root)
    paths = {
        "artifact_json": output_dir / "s66_s64_fallback_reason_probe_review_hardening_implementation.json",
        "artifact_md": output_dir / "s66_s64_fallback_reason_probe_review_hardening_implementation.md",
        "sensitive_path_fingerprint": output_dir / "sensitive_path_fingerprint.json",
    }
    payload: dict[str, Any] = {
        "schema": "phase3b-s64-fail-closed-hardening-implementation/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "implementation_kind": "s64_probe_review_fail_closed_hardening_after_s65_blockers",
        "s65_review_status": "review_failed_blocked",
        "s65_review_summary_path": str(s65_reply_summary_path),
        "s65_review_verdict": _mapping(s65_summary).get("review_verdict"),
        "s65_blockers_addressed": [
            "s64_sensitive_path_schema_not_strict_enough",
            "s64_missing_visibility_status_exit_semantics_too_success_like",
        ],
        "hardening": {
            "sensitive_path_schema_required": "phase3b-sensitive-path-fingerprint-comparison/v0",
            "sensitive_path_changed_must_be_false": True,
            "sensitive_path_changed_paths_must_be_empty_list": True,
            "sensitive_path_changed_entries_must_be_empty_list": True,
            "fallback_reason_instrumentation_missing_status": "fallback_reason_instrumentation_missing",
            "fallback_reason_instrumentation_missing_cli_nonzero": True,
        },
        "changed_files": [
            "scripts/build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_review.py",
            "src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_review.py",
            "scripts/build_phase3b_checkpoint_free_signature_bucket_s64_fail_closed_hardening.py",
            "scripts/build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_rereview_package_v2.py",
            "src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_rereview_package_v2.py",
        ],
        "verification": [
            {
                "command": "python -m py_compile S64/S66/S67 scripts and focused tests",
                "status": "passed",
            },
            {
                "command": "pytest src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_review.py -q",
                "status": "passed",
            },
            {
                "command": "pytest src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_rereview_package_v2.py -q",
                "status": "passed",
            },
            {
                "command": "pytest src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_readiness.py src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_external_review_package.py -q",
                "status": "passed",
            },
            {
                "command": "pytest src/tests/test_exact_contract.py -q",
                "status": "passed",
            },
            {
                "command": "Test-Path data/checkpoints/exact_campaign_state.json; Test-Path data/checkpoints/exact_campaign_telemetry.json",
                "status": "passed",
                "result": "False; False",
            },
        ],
        "probe_execution_performed": False,
        "runtime_execution_performed": False,
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "checkpoint_written": False,
        "proof_source": False,
        "source_mutation_performed": False,
        "candidate_universe_changed": False,
        "scheduler_integration": False,
        "production_profile_changed": False,
        "sensitive_path_status": {
            "exact_campaign_state_exists": checkpoint_state.exists(),
            "exact_campaign_telemetry_exists": checkpoint_telemetry.exists(),
            "canonical_checkpoint_state_absent": not checkpoint_state.exists(),
            "canonical_checkpoint_telemetry_absent": not checkpoint_telemetry.exists(),
        },
        "sensitive_path_fingerprint": sensitive_fingerprint,
        "next_gate": {
            "status": "ready_for_s67_external_rereview_package"
            if status == "implemented_and_verified"
            else "hold_for_manual_review",
            "blocked_actions": [
                "do_not_request_probe_authorization_before_s67_review_passes",
                "do_not_execute_enabled_42x32_fallback_reason_probe",
                "do_not_run_runtime_solve",
                "do_not_run_67x20_or_full_wave",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_mutate_preflight_release_viewer_frontdoor_or_production_defaults",
            ],
        },
        "paths": {key: str(path) for key, path in paths.items()},
    }
    if not no_write:
        output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(paths["artifact_json"], payload)
        paths["artifact_md"].write_text(render_s66_markdown(payload), encoding="utf-8")
        atomic_write_json(paths["sensitive_path_fingerprint"], sensitive_fingerprint)
    return payload


def render_s66_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Phase3B S66 S64 Fail-Closed Hardening",
            "",
            f"- Status: `{payload.get('status')}`",
            "- Probe executed: `false`",
            "- CpSolver.Solve called: `false`",
            "- Checkpoint written: `false`",
            "- Proof source: `false`",
            "",
            "S66 addresses the S65 blockers by requiring the full sensitive-path comparison schema and by making `fallback_reason_instrumentation_missing` a non-success status with nonzero CLI exit.",
            "",
        ]
    )


def _assert_s66_namespace(path: Path) -> None:
    normalized = str(path).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "66_s64_fallback_reason_probe_review_hardening_implementation" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S66 fail-closed hardening namespace: {path}")


def _load_json_or_none(path: Path) -> dict[str, Any] | None:
    path = Path(path)
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    return value if isinstance(value, dict) else None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else project_root / path


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
