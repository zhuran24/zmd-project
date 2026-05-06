from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.sensitive_path_audit import build_sensitive_path_fingerprint  # noqa: E402
from src.search.exact_campaign import atomic_write_json  # noqa: E402

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "79_signature_bucket_template_footprint_support_gap_probe_readiness"
DEFAULT_INPUTS = {
    "s75_execution": ARTIFACT_ROOT
    / "75_signature_bucket_template_footprint_probe_execution"
    / "signature_bucket_template_footprint_probe_execution.json",
    "s73_review": ARTIFACT_ROOT
    / "73_signature_bucket_template_footprint_probe_review"
    / "signature_bucket_template_footprint_probe_review.json",
    "s76_strategy": ARTIFACT_ROOT
    / "76_signature_bucket_template_footprint_support_gap_strategy"
    / "signature_bucket_template_footprint_support_gap_strategy.json",
    "s77_review_summary": ARTIFACT_ROOT
    / "77_signature_bucket_template_footprint_support_gap_external_review_package"
    / "s76_template_footprint_support_gap_review_001"
    / "external_review_reply_summary.json",
    "s78_implementation": ARTIFACT_ROOT
    / "78_signature_bucket_template_footprint_support_gap_instrumentation_implementation"
    / "s78_signature_bucket_template_footprint_support_gap_instrumentation_implementation.json",
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
FUTURE_RUN_ID = "local_hotspot_42x32_signature_bucket_template_footprint_support_gap_inst_no_solve_001"
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
    readiness = build_signature_bucket_template_footprint_support_gap_probe_readiness(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket template-footprint support-gap probe readiness")
    print(f"status={readiness['status']}")
    print(f"readiness={readiness['readiness']['classification']}")
    print(f"probe_execution_enabled={readiness['probe_execution_enabled']}")
    if not args.no_write:
        print(f"readiness_json={_display_path(PROJECT_ROOT, Path(readiness['paths']['readiness_json']))}")
    return 0 if readiness["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build S79 readiness artifacts for one future enabled 42x32 no-solve "
            "template-footprint support-gap probe without executing it."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_template_footprint_support_gap_probe_readiness(
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
        if readiness["classification"] == "ready_for_support_gap_probe_review"
        else "manual_review_required"
    )
    paths = _paths(output_dir)
    payload = {
        "schema": "phase3b-signature-bucket-template-footprint-support-gap-probe-readiness/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "readiness_kind": "future_enabled_signature_bucket_template_footprint_support_gap_no_solve_probe_plan_only",
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
            "status": "hold_for_readiness_review_before_support_gap_probe",
            "candidate_step": (
                "execute exactly one enabled 42x32 no-solve support-gap probe "
                "only after S79 readiness review accepts this plan"
            ),
            "blocked_actions": [
                "do_not_execute_enabled_probe_in_s79",
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
    }
    return {
        "schema": "phase3b-signature-bucket-template-footprint-support-gap-future-command/v0",
        "command": command,
        "command_display": " ".join(command),
        "environment": environment,
        "candidate_key": "42x32",
        "execute_no_solve": True,
        "run_id": FUTURE_RUN_ID,
        "probe_execution_enabled": False,
        "next_probe_allowed_only_after_readiness_review": True,
        "expected_artifact_namespace": ".artifacts/phase3b_local_13900ks_tuning_20260430/35_overlay_timing_strategy",
        "diagnostic_only": True,
        "proof_source": False,
        "checkpoint_written": False,
    }


def validate_future_command_template(template: Mapping[str, Any]) -> dict[str, Any]:
    command = [str(token) for token in list(template.get("command", []) or [])]
    env = _mapping(template.get("environment"))
    failures: list[str] = []
    if command != EXPECTED_FUTURE_COMMAND:
        failures.append("command_vector_mismatch")
    duplicate_flags = sorted(
        flag
        for flag in {token for token in command if token.startswith("--")}
        if command.count(flag) > 1
    )
    if duplicate_flags:
        failures.append("duplicate_flags:" + ",".join(duplicate_flags))
    if template.get("candidate_key") != "42x32" or "42x32" not in command:
        failures.append("candidate_key_must_be_42x32")
    if "--execute-no-solve" not in command or template.get("execute_no_solve") is not True:
        failures.append("execute_no_solve_required")
    if template.get("run_id") != FUTURE_RUN_ID or FUTURE_RUN_ID not in command:
        failures.append("unexpected_run_id")
    required_env = {
        SIGNATURE_INSTRUMENTATION_ENV_VAR: "signature_bucket_instrumentation_env_gate_must_be_1",
        MANDATORY_REGION_COUNTING_ENV_VAR: "mandatory_region_counting_env_gate_must_be_1",
        FALLBACK_INSTRUMENTATION_ENV_VAR: "fallback_reason_instrumentation_env_gate_must_be_1",
        TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR: "template_footprint_support_env_gate_must_be_1",
        SUPPORT_GAP_INSTRUMENTATION_ENV_VAR: "support_gap_instrumentation_env_gate_must_be_1",
    }
    for env_var, failure in required_env.items():
        if env.get(env_var) != "1":
            failures.append(failure)
    lower_tokens = {token.lower() for token in command}
    forbidden_seen = sorted(token for token in FORBIDDEN_COMMAND_TOKENS if token.lower() in lower_tokens)
    if forbidden_seen:
        failures.append("forbidden_tokens:" + ",".join(forbidden_seen))
    if any(str(token).startswith("--") and "checkpoint" in str(token).lower() for token in command):
        failures.append("checkpoint_flag_forbidden")
    return {
        "valid": not failures,
        "failures": failures,
        "expected_command": list(EXPECTED_FUTURE_COMMAND),
        "forbidden_tokens_checked": sorted(FORBIDDEN_COMMAND_TOKENS),
    }


def render_readiness_markdown(payload: Mapping[str, Any]) -> str:
    readiness = _mapping(payload.get("readiness"))
    future_command = _mapping(payload.get("future_command_template"))
    environment = _mapping(future_command.get("environment"))
    lines = [
        "# Phase3B S79 Signature Bucket Template-Footprint Support-Gap Probe Readiness",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{readiness.get('classification')}`",
        "- Probe execution enabled: `false`",
        "- CpSolver.Solve called: `false`",
        "- Checkpoint written: `false`",
        "- Proof source: `false`",
        "- Runtime execution performed: `false`",
        "",
        "## Future Command Template",
        "",
        f"- Command: `{future_command.get('command_display')}`",
        f"- Env: `{SIGNATURE_INSTRUMENTATION_ENV_VAR}={environment.get(SIGNATURE_INSTRUMENTATION_ENV_VAR)}`",
        f"- Env: `{MANDATORY_REGION_COUNTING_ENV_VAR}={environment.get(MANDATORY_REGION_COUNTING_ENV_VAR)}`",
        f"- Env: `{FALLBACK_INSTRUMENTATION_ENV_VAR}={environment.get(FALLBACK_INSTRUMENTATION_ENV_VAR)}`",
        f"- Env: `{TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR}={environment.get(TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR)}`",
        f"- Env: `{SUPPORT_GAP_INSTRUMENTATION_ENV_VAR}={environment.get(SUPPORT_GAP_INSTRUMENTATION_ENV_VAR)}`",
        f"- Run id: `{future_command.get('run_id')}`",
        "",
        "## Baseline",
        "",
        f"- S75 support attempts: `{readiness.get('baseline_support_attempts')}`",
        f"- S75 support used: `{readiness.get('baseline_support_used')}`",
        f"- S75 unsupported footprint fallbacks: `{readiness.get('baseline_unsupported_footprint_fallbacks')}`",
        "",
        "## Readiness Checks",
        "",
    ]
    for check in list(readiness.get("checks", []) or []):
        check_map = _mapping(check)
        lines.append(f"- `{check_map.get('name')}`: `{check_map.get('status')}`")
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "S79 does not execute the enabled probe. A later step may run exactly one `42x32` no-solve support-gap probe only after this readiness artifact is reviewed and accepted.",
        ]
    )
    return "\n".join(lines) + "\n"


def _evaluate_readiness(
    *,
    loaded_inputs: Mapping[str, Mapping[str, Any]],
    sensitive_path_fingerprint: Mapping[str, Any],
    command_validation: Mapping[str, Any],
) -> dict[str, Any]:
    s75 = _payload(loaded_inputs, "s75_execution")
    s73 = _payload(loaded_inputs, "s73_review")
    s76 = _payload(loaded_inputs, "s76_strategy")
    s77 = _payload(loaded_inputs, "s77_review_summary")
    s78 = _payload(loaded_inputs, "s78_implementation")
    agents_text = str(_mapping(loaded_inputs.get("agents")).get("text") or "")
    s73_interp = _mapping(s73.get("interpretation"))
    s75_interp = _mapping(s75.get("interpretation"))
    s75_safety = _mapping(s75.get("safety"))
    s78_impl = _mapping(s78.get("implementation"))
    s78_safety = _mapping(s78.get("safety"))
    checks = [
        _check(
            "s75_probe_completed_support_not_used",
            s75.get("status") == "completed"
            and s75.get("s73_classification") == "template_footprint_support_not_used"
            and s75_interp.get("template_footprint_support_attempts", 0) > 0
            and s75_interp.get("template_footprint_support_used") == 0,
        ),
        _check(
            "s75_safety_clean",
            s75_safety.get("execute_no_solve") is True
            and all(
                s75_safety.get(key) is False
                for key in (
                    "cp_solver_solve_called",
                    "main_py_executed",
                    "exact_campaign_used",
                    "runtime_execution_performed",
                    "checkpoint_written",
                    "proof_source",
                    "source_model_mutation",
                    "source_mutation_performed",
                    "candidate_universe_changed",
                    "scheduler_integration",
                    "production_profile_changed",
                    "sensitive_path_changed",
                    "canonical_checkpoint_state_exists",
                    "canonical_checkpoint_telemetry_exists",
                )
            ),
        ),
        _check(
            "s73_review_completed_support_not_used",
            s73.get("status") == "completed"
            and s73_interp.get("classification") == "template_footprint_support_not_used",
        ),
        _check(
            "s76_strategy_completed_review_first",
            s76.get("status") == "completed"
            and _mapping(s76.get("interpretation")).get("classification")
            == "template_footprint_support_not_used_strategy_required"
            and s76.get("source_mutation_performed") is False
            and s76.get("review_required_before_authorization") is True,
        ),
        _check(
            "s77_review_passed_not_authorization",
            s77.get("review_verdict") == "pass"
            and s77.get("safe_to_request_authorization") is True
            and s77.get("review_is_authorization") is False
            and s77.get("authorization_required_next") is True,
        ),
        _check(
            "s78_patch_implemented_and_verified",
            s78.get("status") == "implemented_and_verified"
            and s78_impl.get("env_var") == SUPPORT_GAP_INSTRUMENTATION_ENV_VAR
            and s78_safety.get("probe_executed") is False
            and s78_safety.get("runtime_solve_executed") is False
            and s78_safety.get("cp_solver_solve_called") is False
            and s78_safety.get("checkpoint_written") is False
            and s78_safety.get("proof_source") is False
            and s78_safety.get("production_default_changed") is False,
        ),
        _check(
            "s78_checkpoint_state_absent",
            _mapping(s78.get("verification")).get("canonical_checkpoint_state_exists_after") is False
            and _mapping(s78.get("verification")).get("canonical_checkpoint_telemetry_exists_after") is False,
        ),
        _check(
            "agents_gate_mentions_s78",
            "Current S77 external review result and S78" in agents_text
            and SUPPORT_GAP_INSTRUMENTATION_ENV_VAR in agents_text,
        ),
        _check(
            "canonical_checkpoint_state_files_absent",
            _sensitive_entry_missing(
                sensitive_path_fingerprint,
                "data/checkpoints/exact_campaign_state.json",
            )
            and _sensitive_entry_missing(
                sensitive_path_fingerprint,
                "data/checkpoints/exact_campaign_telemetry.json",
            ),
        ),
        _check("future_command_template_valid", bool(command_validation.get("valid"))),
    ]
    ready = all(check["status"] == "passed" for check in checks)
    return {
        "classification": "ready_for_support_gap_probe_review" if ready else "manual_review_required",
        "checks": checks,
        "ready_for_future_probe_review": bool(ready),
        "future_probe_executable_now": False,
        "baseline_run_id": s75.get("run_id") or s73.get("run_id"),
        "baseline_model_build_seconds": _float(s75.get("model_build_seconds"))
        or _float(s73.get("model_build_seconds")),
        "baseline_mandatory_scan_seconds": _float(
            s75_interp.get("current_mandatory_scan_seconds")
        )
        or _float(s73_interp.get("current_mandatory_scan_seconds")),
        "baseline_support_attempts": _int_or_none(
            s75_interp.get("template_footprint_support_attempts")
        )
        or _int_or_none(s73_interp.get("template_footprint_support_attempts")),
        "baseline_support_used": _int_or_none(s75_interp.get("template_footprint_support_used"))
        or _int_or_none(s73_interp.get("template_footprint_support_used")),
        "baseline_support_fallbacks": _int_or_none(
            s75_interp.get("template_footprint_support_fallbacks")
        )
        or _int_or_none(s73_interp.get("template_footprint_support_fallbacks")),
        "baseline_unsupported_footprint_fallbacks": _int_or_none(
            _mapping(s75_interp.get("fallback_reasons")).get(
                "unsupported_or_missing_template_footprint"
            )
        )
        or _int_or_none(s73_interp.get("current_unsupported_footprint_fallbacks")),
        "reason": (
            "S78 is verified and the single future 42x32 no-solve support-gap probe plan is bounded."
            if ready
            else "One or more S75-S78 inputs or command/sensitive-path guards are not ready."
        ),
    }


def _check(name: str, passed: bool) -> dict[str, Any]:
    return {"name": name, "status": "passed" if passed else "failed"}


def _load_input(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return {"exists": False, "loaded": False, "payload": {}, "text": "", "error": "missing"}
    try:
        if path.suffix.lower() == ".json":
            with path.open("r", encoding="utf-8-sig") as fh:
                payload = json.load(fh)
            if not isinstance(payload, dict):
                raise ValueError("expected JSON object")
            return {"exists": True, "loaded": True, "payload": payload, "text": "", "error": None}
        text = path.read_text(encoding="utf-8")
        return {"exists": True, "loaded": True, "payload": {}, "text": text, "error": None}
    except Exception as exc:  # pragma: no cover
        return {"exists": True, "loaded": False, "payload": {}, "text": "", "error": str(exc)}


def _payload(loaded_inputs: Mapping[str, Mapping[str, Any]], key: str) -> Mapping[str, Any]:
    return _mapping(_mapping(loaded_inputs.get(key)).get("payload"))


def _sensitive_entry_missing(fingerprint: Mapping[str, Any], relative_path: str) -> bool:
    for entry in list(fingerprint.get("entries", []) or []):
        entry_map = _mapping(entry)
        if str(entry_map.get("relative_path")) == relative_path:
            return entry_map.get("exists") is False
    return False


def _paths(output_dir: Path) -> dict[str, Path]:
    return {
        "readiness_json": output_dir
        / "signature_bucket_template_footprint_support_gap_probe_readiness.json",
        "readiness_md": output_dir
        / "signature_bucket_template_footprint_support_gap_probe_readiness.md",
        "future_command_template": output_dir / "future_command_template.json",
        "sensitive_path_fingerprint": output_dir / "sensitive_path_fingerprint.json",
    }


def _assert_readiness_namespace(path: Path) -> None:
    normalized = str(Path(path)).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "79_signature_bucket_template_footprint_support_gap_probe_readiness"
        not in normalized
    ):
        raise ValueError(f"Refusing to write outside S79 readiness namespace: {path}")


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else (project_root / path)


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _int_or_none(value: Any) -> int | None:
    return int(value) if isinstance(value, int) else None


if __name__ == "__main__":
    raise SystemExit(main())
