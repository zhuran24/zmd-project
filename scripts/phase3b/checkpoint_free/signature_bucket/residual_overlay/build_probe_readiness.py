from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[5]
WORKSPACE_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.sensitive_path_audit import build_sensitive_path_fingerprint  # noqa: E402
from src.search.exact_campaign import atomic_write_json  # noqa: E402

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "96_signature_bucket_residual_overlay_probe_readiness"
DEFAULT_INPUTS = {
    "s89_execution": ARTIFACT_ROOT
    / "89_signature_bucket_payload_footprint_probe_execution"
    / "signature_bucket_payload_footprint_probe_execution.json",
    "s87_review": ARTIFACT_ROOT
    / "87_signature_bucket_payload_footprint_probe_review"
    / "signature_bucket_payload_footprint_probe_review.json",
    "s91_strategy": ARTIFACT_ROOT
    / "91_signature_bucket_payload_footprint_result_strategy"
    / "signature_bucket_payload_footprint_result_strategy.json",
    "s92_review_summary": ARTIFACT_ROOT
    / "92_signature_bucket_payload_footprint_result_external_review_package"
    / "s89_payload_footprint_result_review_001"
    / "external_review_reply_summary.json",
    "s94_review_summary": ARTIFACT_ROOT
    / "94_signature_bucket_residual_overlay_external_review_package"
    / "signature_bucket_residual_overlay_review_001"
    / "external_review_reply_summary.json",
    "s95_implementation": ARTIFACT_ROOT
    / "95_signature_bucket_residual_overlay_instrumentation_implementation"
    / "signature_bucket_residual_overlay_instrumentation_implementation.json",
    "agents": WORKSPACE_ROOT / "AGENTS.md",
}

SIGNATURE_INSTRUMENTATION_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION"
MANDATORY_REGION_COUNTING_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING"
FALLBACK_INSTRUMENTATION_ENV_VAR = (
    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION"
)
TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR = "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT"
SUPPORT_GAP_INSTRUMENTATION_ENV_VAR = (
    "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION"
)
PAYLOAD_FOOTPRINT_STABILITY_ENV_VAR = (
    "EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT"
)
RESIDUAL_OVERLAY_INSTRUMENTATION_ENV_VAR = (
    "EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION"
)
FUTURE_RUN_ID = "local_hotspot_42x32_signature_bucket_residual_overlay_inst_no_solve_001"
FUTURE_PROBE_SCRIPT = "scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py"
EXPECTED_FUTURE_COMMAND = [
    "python",
    FUTURE_PROBE_SCRIPT,
    "--execute-no-solve",
    "--candidate-key",
    "42x32",
    "--run-id",
    FUTURE_RUN_ID,
]
FORBIDDEN_COMMAND_TOKENS = {
    "168h",
    "--resume-campaign",
    "--checkpoint",
    "--checkpoint-path",
    "--checkpoint-dir",
    "--checkpoint-output",
    "--import-checkpoint",
    "--write-checkpoint",
    "--proof",
    "--proof-source",
    "--release",
    "--viewer",
    "--frontdoor",
    "--preflight",
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    readiness = build_signature_bucket_residual_overlay_probe_readiness(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket residual-overlay probe readiness")
    print(f"status={readiness['status']}")
    print(f"readiness={readiness['readiness']['classification']}")
    print(f"probe_execution_enabled={readiness['probe_execution_enabled']}")
    if not args.no_write:
        print(f"readiness_json={_display_path(PROJECT_ROOT, Path(readiness['paths']['readiness_json']))}")
    return 0 if readiness["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build S96 readiness artifacts for one future enabled 42x32 no-solve "
            "residual-overlay instrumentation probe without executing it."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_residual_overlay_probe_readiness(
    *,
    project_root: Path,
    output_dir: Path,
    no_write: bool = False,
    inputs: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = _resolve_path(project_root, output_dir)
    _assert_readiness_namespace(output_dir)
    input_paths = {
        key: _resolve_path(project_root, value)
        for key, value in dict(inputs or DEFAULT_INPUTS).items()
    }
    loaded_inputs = {key: _load_input(path) for key, path in input_paths.items()}
    sensitive_path_fingerprint = build_sensitive_path_fingerprint(project_root)
    future_command = build_future_command_template()
    command_validation = validate_future_command_template(future_command)
    readiness = _evaluate_readiness(
        loaded_inputs=loaded_inputs,
        sensitive_path_fingerprint=sensitive_path_fingerprint,
        command_validation=command_validation,
    )
    status = (
        "completed"
        if readiness["classification"] == "ready_for_residual_overlay_probe_review"
        else "manual_review_required"
    )
    paths = _paths(output_dir)
    payload = {
        "schema": "phase3b-signature-bucket-residual-overlay-probe-readiness/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "readiness_kind": "future_enabled_signature_bucket_residual_overlay_no_solve_probe_plan_only",
        "project_root": str(project_root),
        "output_dir": str(output_dir),
        "inputs": {key: str(path) for key, path in input_paths.items()},
        "input_status": {
            key: {
                "exists": bool(value["exists"]),
                "loaded": bool(value["loaded"]),
                "error": value.get("error"),
            }
            for key, value in loaded_inputs.items()
        },
        "readiness": readiness,
        "future_command_template": future_command,
        "future_command_validation": command_validation,
        "sensitive_path_fingerprint": sensitive_path_fingerprint,
        "probe_execution_enabled": False,
        "next_probe_allowed_only_after_readiness_review": True,
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "checkpoint_written": False,
        "proof_source": False,
        "source_model_mutation": False,
        "source_mutation_performed": False,
        "production_profile_changed": False,
        "candidate_universe_changed": False,
        "scheduler_integration": False,
        "runtime_execution_performed": False,
        "paths": {key: str(path) for key, path in paths.items()},
        "next_gate": {
            "status": "hold_for_readiness_review_before_residual_overlay_probe",
            "candidate_step": (
                "execute exactly one enabled 42x32 no-solve residual-overlay probe "
                "only after S96 readiness review accepts this plan"
            ),
            "blocked_actions": [
                "do_not_execute_enabled_probe_in_s96",
                "do_not_call_CpSolver_Solve",
                "do_not_run_main_py",
                "do_not_use_ExactCampaign",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
                "do_not_run_67x20_or_full_wave",
            ],
        },
    }
    if not no_write:
        output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(paths["readiness_json"], payload)
        paths["readiness_md"].write_text(render_readiness_markdown(payload), encoding="utf-8")
        atomic_write_json(paths["future_command_template"], future_command)
        atomic_write_json(paths["sensitive_path_fingerprint"], sensitive_path_fingerprint)
    return payload


def build_future_command_template() -> dict[str, Any]:
    command = list(EXPECTED_FUTURE_COMMAND)
    environment = {
        SIGNATURE_INSTRUMENTATION_ENV_VAR: "1",
        MANDATORY_REGION_COUNTING_ENV_VAR: "1",
        FALLBACK_INSTRUMENTATION_ENV_VAR: "1",
        TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR: "1",
        SUPPORT_GAP_INSTRUMENTATION_ENV_VAR: "1",
        PAYLOAD_FOOTPRINT_STABILITY_ENV_VAR: "1",
        RESIDUAL_OVERLAY_INSTRUMENTATION_ENV_VAR: "1",
    }
    return {
        "schema": "phase3b-signature-bucket-residual-overlay-future-command/v0",
        "command": command,
        "command_display": " ".join(command),
        "environment": environment,
        "candidate_key": "42x32",
        "execute_no_solve": True,
        "run_id": FUTURE_RUN_ID,
        "probe_execution_enabled": False,
        "next_probe_allowed_only_after_readiness_review": True,
        "expected_artifact_namespace": ".artifacts/phase3b_local_13900ks_tuning_20260430/35_overlay_timing_strategy",
    }


def validate_future_command_template(template: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    command = list(template.get("command") or [])
    environment = _mapping(template.get("environment"))
    if command != EXPECTED_FUTURE_COMMAND:
        failures.append("command_vector_mismatch")
    if command.count("--execute-no-solve") != 1:
        failures.append("duplicate_flags:--execute-no-solve")
    if command.count("--candidate-key") != 1:
        failures.append("duplicate_flags:--candidate-key")
    if command.count("--run-id") != 1:
        failures.append("duplicate_flags:--run-id")
    if template.get("candidate_key") != "42x32":
        failures.append("candidate_key_must_be_42x32")
    if template.get("run_id") != FUTURE_RUN_ID:
        failures.append("unexpected_run_id")
    if template.get("execute_no_solve") is not True:
        failures.append("execute_no_solve_required")
    if template.get("probe_execution_enabled") is not False:
        failures.append("probe_execution_enabled_must_be_false")
    for token in sorted(FORBIDDEN_COMMAND_TOKENS):
        if token in command:
            failures.append(f"forbidden_tokens:{token}")
    if any(
        "checkpoint" in str(token).lower()
        for token in command
        if str(token).startswith("--")
    ):
        failures.append("checkpoint_flag_forbidden")
    required_env = build_future_command_template()["environment"]
    for key, value in required_env.items():
        if environment.get(key) != value:
            failures.append(f"{key}_must_be_{value}")
    extra_env = sorted(set(environment) - set(required_env))
    if extra_env:
        failures.append("unexpected_env:" + ",".join(extra_env))
    return {"valid": not failures, "failures": failures}


def render_readiness_markdown(payload: Mapping[str, Any]) -> str:
    readiness = _mapping(payload.get("readiness"))
    lines = [
        "# Phase3B S96 Residual Overlay Probe Readiness",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{readiness.get('classification')}`",
        "- Probe execution enabled: `false`",
        "- CpSolver.Solve called: `false`",
        "- Checkpoint written: `false`",
        "- Proof source: `false`",
        "",
        "## Future Command",
        "",
        f"`{_mapping(payload.get('future_command_template')).get('command_display')}`",
        "",
        "## Checks",
        "",
    ]
    for check in readiness.get("checks", []):
        lines.append(f"- `{check['name']}`: `{check['status']}`")
    return "\n".join(lines) + "\n"


def _evaluate_readiness(
    *,
    loaded_inputs: Mapping[str, Mapping[str, Any]],
    sensitive_path_fingerprint: Mapping[str, Any],
    command_validation: Mapping[str, Any],
) -> dict[str, Any]:
    checks = [
        _check("s89_probe_completed", _input_value(loaded_inputs, "s89_execution", "status") == "completed"),
        _check(
            "s87_payload_footprint_effective",
            _nested_value(loaded_inputs, "s87_review", "interpretation", "classification")
            == "payload_footprint_stability_effective",
        ),
        _check(
            "s91_residual_strategy_ready",
            _input_value(loaded_inputs, "s91_strategy", "classification")
            == "payload_footprint_effective_residual_overlay_strategy_required",
        ),
        _check(
            "s92_review_passed",
            _input_value(loaded_inputs, "s92_review_summary", "review_verdict") == "pass",
        ),
        _check(
            "s94_review_passed",
            _input_value(loaded_inputs, "s94_review_summary", "review_verdict") == "pass",
        ),
        _check(
            "s95_patch_implemented_and_verified",
            _input_value(loaded_inputs, "s95_implementation", "status")
            == "implemented_and_verified",
        ),
        _check("future_command_exact_and_bounded", bool(command_validation.get("valid"))),
        _check(
            "canonical_checkpoint_state_files_absent",
            _checkpoint_files_absent(sensitive_path_fingerprint),
        ),
    ]
    classification = (
        "ready_for_residual_overlay_probe_review"
        if all(check["status"] == "passed" for check in checks)
        else "manual_review_required"
    )
    return {
        "classification": classification,
        "checks": checks,
        "baseline_model_build_seconds": _nested_value(
            loaded_inputs,
            "s91_strategy",
            "evidence",
            "model_build_seconds",
        ),
        "baseline_mandatory_scan_seconds": _nested_value(
            loaded_inputs,
            "s91_strategy",
            "evidence",
            "mandatory_scan_seconds",
        ),
        "baseline_signature_tightening_seconds": _nested_value(
            loaded_inputs,
            "s91_strategy",
            "evidence",
            "signature_bucket_tightening_seconds",
        ),
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "passed" if passed else "failed"}


def _checkpoint_files_absent(fingerprint: Mapping[str, Any]) -> bool:
    raw_entries = fingerprint.get("entries")
    if isinstance(raw_entries, list):
        entries = {
            str(_mapping(entry).get("relative_path")): _mapping(entry)
            for entry in raw_entries
        }
    else:
        entries = _mapping(raw_entries)
    for rel_path in (
        "data/checkpoints/exact_campaign_state.json",
        "data/checkpoints/exact_campaign_telemetry.json",
    ):
        if _mapping(entries.get(rel_path)).get("exists") is not False:
            return False
    return True


def _paths(output_dir: Path) -> dict[str, Path]:
    return {
        "readiness_json": output_dir / "signature_bucket_residual_overlay_probe_readiness.json",
        "readiness_md": output_dir / "signature_bucket_residual_overlay_probe_readiness.md",
        "future_command_template": output_dir / "future_command_template.json",
        "sensitive_path_fingerprint": output_dir / "sensitive_path_fingerprint.json",
    }


def _assert_readiness_namespace(output_dir: Path) -> None:
    normalized = str(output_dir).replace("\\", "/")
    if "96_signature_bucket_residual_overlay_probe_readiness" not in normalized:
        raise ValueError("S96 readiness namespace required")


def _load_input(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"exists": path.exists(), "loaded": False, "data": None}
    if not path.exists():
        result["error"] = "missing"
        return result
    try:
        result["data"] = json.loads(path.read_text(encoding="utf-8-sig"))
        result["loaded"] = True
    except Exception as exc:  # pragma: no cover - defensive diagnostics
        result["error"] = str(exc)
    return result


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _input_value(
    loaded_inputs: Mapping[str, Mapping[str, Any]],
    key: str,
    field: str,
) -> Any:
    return _mapping(_mapping(loaded_inputs.get(key)).get("data")).get(field)


def _nested_value(
    loaded_inputs: Mapping[str, Mapping[str, Any]],
    key: str,
    *fields: str,
) -> Any:
    current: Any = _mapping(loaded_inputs.get(key)).get("data", {})
    for field in fields:
        current = _mapping(current).get(field)
    return current


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _resolve_path(project_root: Path, value: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
