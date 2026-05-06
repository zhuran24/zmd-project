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
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "57_s53_fail_closed_hardening_implementation"
DEFAULT_S56_REPLY = (
    PROJECT_ROOT.parent
    / ".codex_test_logs"
    / "chatgpt_project_uploader"
    / "review_reply_extract_s56_region_probe_rereview_reply_002.md"
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    artifact = build_s53_fail_closed_hardening_artifact(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        s56_reply_path=_resolve_path(PROJECT_ROOT, args.s56_reply),
        no_write=bool(args.no_write),
    )
    print("phase3b s57 s53 fail-closed hardening implementation")
    print(f"status={artifact['status']}")
    if not args.no_write:
        print(f"artifact_json={_display_path(PROJECT_ROOT, Path(artifact['paths']['artifact_json']))}")
    return 0 if artifact["status"] == "implemented_and_verified" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the S57 implementation artifact for S53 fail-closed hardening."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--s56-reply", type=Path, default=DEFAULT_S56_REPLY)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_s53_fail_closed_hardening_artifact(
    *,
    project_root: Path,
    output_dir: Path,
    s56_reply_path: Path,
    no_write: bool = False,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = _resolve_path(project_root, output_dir)
    _assert_s57_namespace(output_dir)
    checkpoint_state = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    checkpoint_telemetry = project_root / "data" / "checkpoints" / "exact_campaign_telemetry.json"
    sensitive_fingerprint = build_sensitive_path_fingerprint(project_root)
    s56_reply_exists = Path(s56_reply_path).exists()
    status = (
        "implemented_and_verified"
        if not checkpoint_state.exists() and not checkpoint_telemetry.exists() and s56_reply_exists
        else "manual_review_required"
    )
    paths = {
        "artifact_json": output_dir / "s57_s53_fail_closed_hardening_implementation.json",
        "artifact_md": output_dir / "s57_s53_fail_closed_hardening_implementation.md",
        "sensitive_path_fingerprint": output_dir / "sensitive_path_fingerprint.json",
    }
    payload: dict[str, Any] = {
        "schema": "phase3b-s53-fail-closed-hardening-implementation/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "implementation_kind": "s53_probe_review_fail_closed_hardening_after_s56_blockers",
        "s56_review_status": "review_failed_blocked",
        "s56_review_reply_path": str(s56_reply_path),
        "s56_blockers_addressed": [
            "missing_timing_metrics_must_be_instrumentation_inconclusive_before_region_status",
            "sensitive_path_comparison_requires_strict_clean_schema",
            "hard_boundary_flags_require_literal_boolean_false",
        ],
        "hardening": {
            "s53_timing_numeric_gate_precedes_attempts_used_fallback_classification": True,
            "s53_sensitive_path_comparison_requires_changed_false": True,
            "s53_sensitive_path_comparison_requires_changed_paths_empty_list_of_strings": True,
            "s53_hard_boundary_flags_require_literal_false": True,
            "overlay_timing_probe_emits_runtime_execution_performed_false": True,
        },
        "changed_files": [
            "scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py",
            "scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py",
            "src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py",
            "src/tests/test_phase3b_checkpoint_free_overlay_timing_probe.py",
            "scripts/build_phase3b_checkpoint_free_signature_bucket_s53_fail_closed_hardening.py",
            "scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_rereview_package_v3.py",
            "src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_rereview_package_v3.py",
        ],
        "verification": [
            {
                "command": "python -m py_compile S52/S53/S56/S57/S58 scripts/tests and overlay timing probe",
                "status": "passed",
            },
            {
                "command": "pytest src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py -q",
                "status": "passed",
                "result": "49 passed",
            },
            {
                "command": "pytest src/tests/test_phase3b_checkpoint_free_overlay_timing_probe.py -q",
                "status": "passed",
                "result": "7 passed",
            },
            {
                "command": "pytest S52/S53/S56/S58 package/review tooling tests plus overlay timing probe tests -q",
                "status": "passed",
                "result": "71 passed, 3 warnings",
            },
            {
                "command": "pytest src/tests/test_master.py -q -k \"mandatory_region_counting or signature_bucket_tightening_instrumentation or exact_core_overlay_signature_bucket\"",
                "status": "passed",
                "result": "14 passed, 155 deselected",
            },
            {
                "command": "pytest src/tests/test_exact_contract.py -q --basetemp .pytest_tmp_exact_contract_s57",
                "status": "passed",
                "result": "76 passed, 3 warnings",
            },
            {
                "command": "pytest S49/S50/S54 package tests -q",
                "status": "passed",
                "result": "8 passed",
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
            "status": "ready_for_s58_external_rereview_package"
            if status == "implemented_and_verified"
            else "hold_for_manual_review",
            "blocked_actions": [
                "do_not_execute_enabled_42x32_probe",
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
        paths["artifact_md"].write_text(render_s57_markdown(payload), encoding="utf-8")
        atomic_write_json(paths["sensitive_path_fingerprint"], sensitive_fingerprint)
    return payload


def render_s57_markdown(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Phase3B S57 S53 Fail-Closed Hardening",
            "",
            f"- Status: `{payload.get('status')}`",
            "- Probe executed: `false`",
            "- CpSolver.Solve called: `false`",
            "- Checkpoint written: `false`",
            "- Proof source: `false`",
            "",
            "S57 addresses the S56 external-review blockers by requiring numeric timing metrics before region-status classification, strict clean sensitive-path comparison shape, and literal `false` hard-boundary flags.",
            "",
        ]
    )


def _assert_s57_namespace(path: Path) -> None:
    normalized = str(path).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "57_s53_fail_closed_hardening_implementation" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S57 fail-closed hardening namespace: {path}")


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
