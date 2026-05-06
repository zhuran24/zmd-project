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
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "125_signature_bucket_powered_support_coverer_probe_readiness"
DEFAULT_INPUTS = {
    "s120_execution": ARTIFACT_ROOT
    / "120_signature_bucket_port_profile_cache_probe_execution"
    / "signature_bucket_port_profile_cache_probe_execution.json",
    "s118_review": ARTIFACT_ROOT
    / "118_signature_bucket_port_profile_cache_probe_review"
    / "signature_bucket_port_profile_cache_probe_review.json",
    "s122_strategy": ARTIFACT_ROOT
    / "122_signature_bucket_powered_support_coverer_strategy"
    / "signature_bucket_powered_support_coverer_strategy.json",
    "s123_review_summary": ARTIFACT_ROOT
    / "123_signature_bucket_powered_support_coverer_external_review_package"
    / "s122_powered_support_coverer_review_001"
    / "external_review_reply_summary.json",
    "s124_implementation": ARTIFACT_ROOT
    / "124_signature_bucket_powered_support_coverer_instrumentation_implementation"
    / "signature_bucket_powered_support_coverer_instrumentation_implementation.json",
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
MODEL_SHELL_INSTRUMENTATION_ENV_VAR = (
    "EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION"
)
PORT_PROFILE_CACHE_INSTRUMENTATION_ENV_VAR = (
    "EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION"
)
POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV_VAR = (
    "EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION"
)

FUTURE_RUN_ID = "local_hotspot_42x32_signature_bucket_powered_support_coverer_inst_no_solve_001"
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
REQUIRED_ENVIRONMENT = {
    SIGNATURE_INSTRUMENTATION_ENV_VAR: "1",
    MANDATORY_REGION_COUNTING_ENV_VAR: "1",
    FALLBACK_INSTRUMENTATION_ENV_VAR: "1",
    TEMPLATE_FOOTPRINT_SUPPORT_ENV_VAR: "1",
    SUPPORT_GAP_INSTRUMENTATION_ENV_VAR: "1",
    PAYLOAD_FOOTPRINT_STABILITY_ENV_VAR: "1",
    RESIDUAL_OVERLAY_INSTRUMENTATION_ENV_VAR: "1",
    MODEL_SHELL_INSTRUMENTATION_ENV_VAR: "1",
    PORT_PROFILE_CACHE_INSTRUMENTATION_ENV_VAR: "1",
    POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV_VAR: "1",
}
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
    readiness = build_signature_bucket_powered_support_coverer_probe_readiness(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket powered support-coverer probe readiness")
    print(f"status={readiness['status']}")
    print(f"readiness={readiness['readiness']['classification']}")
    print(f"probe_execution_enabled={readiness['probe_execution_enabled']}")
    if not args.no_write:
        print(f"readiness_json={_display_path(PROJECT_ROOT, Path(readiness['paths']['readiness_json']))}")
    return 0 if readiness["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build S125 readiness artifacts for one future enabled 42x32 no-solve "
            "powered support-coverer instrumentation probe without executing it."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_powered_support_coverer_probe_readiness(
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
        if readiness["classification"] == "ready_for_powered_support_coverer_probe_review"
        else "manual_review_required"
    )
    paths = _paths(output_dir)
    payload = {
        "schema": "phase3b-signature-bucket-powered-support-coverer-probe-readiness/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "readiness_kind": "future_enabled_signature_bucket_powered_support_coverer_no_solve_probe_plan_only",
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
            "status": "hold_for_readiness_review_before_powered_support_coverer_probe",
            "candidate_step": (
                "execute exactly one enabled 42x32 no-solve powered support-coverer "
                "probe only after S125 readiness review accepts this plan"
            ),
            "blocked_actions": [
                "do_not_execute_enabled_probe_in_s117",
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
    return {
        "schema": "phase3b-signature-bucket-powered-support-coverer-future-command/v0",
        "command": command,
        "command_display": " ".join(command),
        "environment": dict(REQUIRED_ENVIRONMENT),
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
    for forbidden in sorted(FORBIDDEN_COMMAND_TOKENS):
        if forbidden in command:
            failures.append(f"forbidden_tokens:{forbidden}")
    if "--write-checkpoint" in command or "--checkpoint" in command:
        failures.append("checkpoint_flag_forbidden")
    if template.get("candidate_key") != "42x32":
        failures.append("unexpected_candidate_key")
    if template.get("execute_no_solve") is not True:
        failures.append("execute_no_solve_must_be_true")
    if template.get("run_id") != FUTURE_RUN_ID:
        failures.append("unexpected_run_id")
    if template.get("probe_execution_enabled") is not False:
        failures.append("probe_execution_must_remain_disabled")
    for env_var, expected in REQUIRED_ENVIRONMENT.items():
        if environment.get(env_var) != expected:
            failures.append(f"{env_var}_must_be_{expected}")
    return {"valid": not failures, "failures": failures, "expected_command": EXPECTED_FUTURE_COMMAND}


def render_readiness_markdown(payload: Mapping[str, Any]) -> str:
    readiness = _mapping(payload.get("readiness"))
    lines = [
        "# Phase3B S125 Powered Support-Coverer Probe Readiness",
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
        _check(
            "s120_probe_completed",
            str(_input_value(loaded_inputs, "s120_execution", "status")).startswith("completed"),
        ),
        _check(
            "s120_post_repair_powered_support_coverer_hotspot",
            _nested_value(
                loaded_inputs,
                "s120_execution",
                "post_s121_s118_review",
                "classification",
            )
            == "powered_support_coverer_hotspot",
        ),
        _check(
            "s118_powered_support_coverer_hotspot",
            _nested_value(loaded_inputs, "s118_review", "interpretation", "classification")
            == "powered_support_coverer_hotspot",
        ),
        _check(
            "s122_strategy_ready",
            _input_value(loaded_inputs, "s122_strategy", "classification")
            == "powered_support_coverer_detail_instrumentation_strategy_required",
        ),
        _check(
            "s123_review_passed",
            _input_value(loaded_inputs, "s123_review_summary", "review_verdict") == "pass",
        ),
        _check(
            "s124_patch_implemented_and_verified",
            _input_value(loaded_inputs, "s124_implementation", "status")
            == "implemented_and_verified",
        ),
        _check(
            "s124_powered_support_coverer_env_matches",
            _input_value(loaded_inputs, "s124_implementation", "env_var")
            == POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV_VAR,
        ),
        _check("future_command_exact_and_bounded", bool(command_validation.get("valid"))),
        _check(
            "canonical_checkpoint_state_files_absent",
            _checkpoint_files_absent(sensitive_path_fingerprint),
        ),
    ]
    classification = (
        "ready_for_powered_support_coverer_probe_review"
        if all(check["status"] == "passed" for check in checks)
        else "manual_review_required"
    )
    return {
        "classification": classification,
        "checks": checks,
        "s118_classification": _nested_value(
            loaded_inputs,
            "s118_review",
            "interpretation",
            "classification",
        ),
        "s122_classification": _input_value(loaded_inputs, "s122_strategy", "classification"),
        "s124_env_var": _input_value(loaded_inputs, "s124_implementation", "env_var"),
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
        entry = _mapping(entries.get(rel_path))
        if entry.get("exists") is True:
            return False
    return True


def _paths(output_dir: Path) -> dict[str, Path]:
    return {
        "readiness_json": output_dir / "signature_bucket_powered_support_coverer_probe_readiness.json",
        "readiness_md": output_dir / "signature_bucket_powered_support_coverer_probe_readiness.md",
        "future_command_template": output_dir / "future_command_template.json",
        "sensitive_path_fingerprint": output_dir / "sensitive_path_fingerprint.json",
    }


def _assert_readiness_namespace(output_dir: Path) -> None:
    normalized = str(output_dir).replace("\\", "/")
    if "125_signature_bucket_powered_support_coverer_probe_readiness" not in normalized:
        raise ValueError("S125 readiness namespace required")


def _load_input(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"exists": path.exists(), "loaded": False, "data": None}
    if not path.exists():
        result["error"] = "missing"
        return result
    try:
        text = path.read_text(encoding="utf-8-sig")
        if path.suffix.lower() in {".md", ".txt"}:
            result["data"] = {"text_length": len(text), "text_excerpt": text[:4000]}
        else:
            result["data"] = json.loads(text)
        result["loaded"] = True
    except Exception as exc:  # pragma: no cover - defensive diagnostics
        result["error"] = str(exc)
    return result


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
