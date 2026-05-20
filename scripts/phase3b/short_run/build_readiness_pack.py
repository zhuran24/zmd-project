from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_phase3b_local_tuning_profile import ARTIFACT_ROOT, LOG_ROOT
from src.runtime.sensitive_path_audit import build_sensitive_path_fingerprint, fingerprint_path
from src.search.exact_campaign import atomic_write_json, now_iso

LOCAL_TUNING_NAMESPACE = "phase3b_local_13900ks_tuning_20260430"
LOCAL_TUNING_LOG_NAMESPACE = "local_13900ks_tuning_20260430"
READINESS_SUBDIR = "07_short_run_readiness"
BLOCKED_UNTIL = "checkpoint_free_evaluator_or_explicit_isolated_checkpoint_authorization"
ALLOWED_DURATIONS_SECONDS = (300, 600)

DEFAULT_INTEGRATED_PLAN = Path("docs/phase3b_repair5_acceleration_tuning_ai_plan.md")
DEFAULT_CONFIG_MATRIX_MANIFEST = ARTIFACT_ROOT / "04_config_matrix" / "matrix_manifest.json"
DEFAULT_STAGE_WORKER_MANIFEST = ARTIFACT_ROOT / "05_stage_workers" / "stage_worker_manifest.json"
DEFAULT_PRIORITY_AFFINITY_MANIFEST = (
    ARTIFACT_ROOT / "06_priority_affinity" / "affinity_priority_manifest.json"
)
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / READINESS_SUBDIR
DEFAULT_LOG_DIR = LOG_ROOT / READINESS_SUBDIR

STOP_RULES = (
    "peak_rss_gib_gt_42",
    "commit_charge_gib_gt_44",
    "pagefile_sustained_growth",
    "thermal_throttling_sustained",
    "canonical_path_mutation_detected",
    "system_or_codex_ui_unusable",
    "unexpected_checkpoint_or_proof_path_mutation",
)

SELECTED_CANDIDATES: tuple[dict[str, str], ...] = (
    {
        "candidate_id": "B0_prod_4x4",
        "source_kind": "s5_config_manifest",
        "source_profile_id": "B0_prod_4x4",
    },
    {
        "candidate_id": "experimental_13900ks_htoff_3x8_global_normal",
        "source_kind": "s5_config_manifest",
        "source_profile_id": "experimental_13900ks_htoff_3x8_global_normal",
    },
    {
        "candidate_id": "experimental_13900ks_htoff_4x5_global_normal",
        "source_kind": "s5_config_manifest",
        "source_profile_id": "experimental_13900ks_htoff_4x5_global_normal",
    },
    {
        "candidate_id": "experimental_13900ks_htoff_2x10_global_normal",
        "source_kind": "s5_config_manifest",
        "source_profile_id": "experimental_13900ks_htoff_2x10_global_normal",
    },
    {
        "candidate_id": "W1_prod_4x4_stage_6_4_2_4",
        "source_kind": "s6_stage_worker_manifest",
        "source_profile_id": "W1_stage_4x_master6_local4_binding2_routing4",
    },
    {
        "candidate_id": "W3_prod_4x4_stage_6_6_2_6",
        "source_kind": "s6_stage_worker_manifest",
        "source_profile_id": "W3_stage_4x_master6_local6_binding2_routing6",
    },
    {
        "candidate_id": "W6_prod_3x_stage_8_6_2_6",
        "source_kind": "s6_stage_worker_manifest",
        "source_profile_id": "W6_stage_3x_master8_local6_binding2_routing6",
    },
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Phase3B short-run efficiency readiness pack without executing runs."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--integrated-plan", type=Path, default=DEFAULT_INTEGRATED_PLAN)
    parser.add_argument("--config-matrix-manifest", type=Path, default=DEFAULT_CONFIG_MATRIX_MANIFEST)
    parser.add_argument("--stage-worker-manifest", type=Path, default=DEFAULT_STAGE_WORKER_MANIFEST)
    parser.add_argument(
        "--priority-affinity-manifest",
        type=Path,
        default=DEFAULT_PRIORITY_AFFINITY_MANIFEST,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(args.project_root).resolve()
    output_dir = _resolve_path(project_root, Path(args.output_dir))
    log_dir = _resolve_path(project_root, Path(args.log_dir))
    packet, command_matrix, fingerprint = build_short_run_readiness_pack(
        project_root=project_root,
        integrated_plan_path=_resolve_path(project_root, Path(args.integrated_plan)),
        config_matrix_manifest_path=_resolve_path(project_root, Path(args.config_matrix_manifest)),
        stage_worker_manifest_path=_resolve_path(project_root, Path(args.stage_worker_manifest)),
        priority_affinity_manifest_path=_resolve_path(
            project_root,
            Path(args.priority_affinity_manifest),
        ),
    )
    print("phase3b short-run readiness pack")
    print(f"candidate_count={len(packet['candidates'])}")
    print(f"execution_enabled={packet['safety']['execution_enabled']}")
    print(f"blocked_until={packet['readiness']['real_short_run_blocked_until']}")
    print(f"proof_source={packet['safety']['proof_source']}")
    if not args.no_write:
        paths = write_short_run_readiness_pack(
            packet=packet,
            command_matrix=command_matrix,
            sensitive_path_fingerprint=fingerprint,
            output_dir=output_dir,
            log_dir=log_dir,
        )
        print(f"readiness_packet_json={_display_path(project_root, Path(paths['packet_json']))}")
        print(f"dry_run_command_matrix_json={_display_path(project_root, Path(paths['command_matrix_json']))}")
        print(f"sensitive_path_fingerprint_json={_display_path(project_root, Path(paths['fingerprint_json']))}")
    return 0


def build_short_run_readiness_pack(
    *,
    project_root: Path,
    integrated_plan_path: Path,
    config_matrix_manifest_path: Path,
    stage_worker_manifest_path: Path,
    priority_affinity_manifest_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    project_root = Path(project_root).resolve()
    config_manifest = _load_json(config_matrix_manifest_path)
    stage_manifest = _load_json(stage_worker_manifest_path)
    priority_manifest = _load_optional_json(priority_affinity_manifest_path)
    source_profiles = {
        "s5_config_manifest": _profiles_by_id(config_manifest),
        "s6_stage_worker_manifest": _profiles_by_id(stage_manifest),
    }
    candidates = [
        _candidate_entry(selection, source_profiles)
        for selection in SELECTED_CANDIDATES
    ]
    command_entries = [
        command
        for candidate in candidates
        for command in candidate["planned_future_commands"]
    ]
    fingerprint = build_sensitive_path_fingerprint(project_root)
    source_artifacts = {
        "integrated_plan": _source_summary(integrated_plan_path),
        "config_matrix_manifest": _source_summary(config_matrix_manifest_path),
        "stage_worker_manifest": _source_summary(stage_worker_manifest_path),
        "priority_affinity_manifest": _source_summary(priority_affinity_manifest_path),
    }
    safety = _safety_payload()
    packet = {
        "schema": "phase3b-short-run-readiness-packet/v0",
        "generated_at": now_iso(),
        "packet_kind": "short_run_efficiency_test_readiness_only",
        "execution_enabled": False,
        "real_short_run_blocked_until": BLOCKED_UNTIL,
        "proof_source": False,
        "checkpoint_written": False,
        "source_artifacts": source_artifacts,
        "selected_candidate_ids": [selection["candidate_id"] for selection in SELECTED_CANDIDATES],
        "allowed_durations_seconds": list(ALLOWED_DURATIONS_SECONDS),
        "stop_rules": list(STOP_RULES),
        "candidates": candidates,
        "readiness": {
            "status": "blocked_pre_execution_readiness_only",
            "real_short_run_blocked_until": BLOCKED_UNTIL,
            "checkpoint_free_evaluator_available": False,
            "isolated_checkpoint_authorization_present": False,
            "dry_run_command_matrix_ready": True,
            "candidate_count": len(candidates),
            "command_template_count": len(command_entries),
        },
        "sensitive_path_fingerprint": fingerprint,
        "priority_affinity_context": _priority_affinity_context(priority_manifest),
        "safety": safety,
    }
    command_matrix = {
        "schema": "phase3b-short-run-dry-run-command-matrix/v0",
        "generated_at": packet["generated_at"],
        "matrix_kind": "blocked_future_short_run_command_templates",
        "execution_enabled": False,
        "real_short_run_blocked_until": BLOCKED_UNTIL,
        "allowed_durations_seconds": list(ALLOWED_DURATIONS_SECONDS),
        "commands": command_entries,
        "safety": safety,
    }
    return packet, command_matrix, fingerprint


def write_short_run_readiness_pack(
    *,
    packet: Mapping[str, Any],
    command_matrix: Mapping[str, Any],
    sensitive_path_fingerprint: Mapping[str, Any],
    output_dir: Path,
    log_dir: Path,
) -> dict[str, str]:
    output_dir = Path(output_dir)
    log_dir = Path(log_dir)
    _assert_local_tuning_namespace(output_dir, required_namespace=LOCAL_TUNING_NAMESPACE)
    _assert_local_tuning_namespace(log_dir, required_namespace=LOCAL_TUNING_LOG_NAMESPACE)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    packet_json = output_dir / "short_run_readiness_packet.json"
    packet_md = output_dir / "short_run_readiness_packet.md"
    command_matrix_json = output_dir / "dry_run_command_matrix.json"
    fingerprint_json = output_dir / "sensitive_path_fingerprint.json"
    build_log_json = log_dir / "readiness_build_log.json"
    atomic_write_json(packet_json, dict(packet))
    _atomic_write_text(packet_md, render_short_run_readiness_markdown(packet))
    atomic_write_json(command_matrix_json, dict(command_matrix))
    atomic_write_json(fingerprint_json, dict(sensitive_path_fingerprint))
    atomic_write_json(
        build_log_json,
        {
            "schema": "phase3b-short-run-readiness-build-log/v0",
            "packet_json": str(packet_json),
            "packet_md": str(packet_md),
            "command_matrix_json": str(command_matrix_json),
            "fingerprint_json": str(fingerprint_json),
            "execution_enabled": False,
            "proof_source": False,
            "checkpoint_written": False,
        },
    )
    return {
        "packet_json": str(packet_json),
        "packet_md": str(packet_md),
        "command_matrix_json": str(command_matrix_json),
        "fingerprint_json": str(fingerprint_json),
        "build_log_json": str(build_log_json),
    }


def render_short_run_readiness_markdown(packet: Mapping[str, Any]) -> str:
    readiness = _mapping(packet.get("readiness"))
    safety = _mapping(packet.get("safety"))
    lines = [
        "# Phase3B Short-Run Efficiency Readiness",
        "",
        f"- Status: `{readiness.get('status')}`",
        f"- Execution enabled: `{safety.get('execution_enabled')}`",
        f"- Blocked until: `{readiness.get('real_short_run_blocked_until')}`",
        f"- Proof source: `{safety.get('proof_source')}`",
        f"- Checkpoint written: `{safety.get('checkpoint_written')}`",
        "",
        "| Candidate | Source | Proc | Workers | Risk | Commands |",
        "| --- | --- | ---: | --- | --- | ---: |",
    ]
    for candidate in packet.get("candidates", []):
        if not isinstance(candidate, Mapping):
            continue
        risk = _mapping(candidate.get("risk"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(candidate.get("candidate_id")),
                    _markdown_cell(candidate.get("source_kind")),
                    _markdown_cell(candidate.get("process_count")),
                    _markdown_cell(_worker_summary(candidate)),
                    _markdown_cell(risk.get("level")),
                    _markdown_cell(len(list(candidate.get("planned_future_commands", []) or []))),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Stop Rules", ""])
    lines.extend(f"- `{rule}`" for rule in packet.get("stop_rules", []) or [])
    return "\n".join(lines) + "\n"


def _candidate_entry(
    selection: Mapping[str, str],
    source_profiles: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    candidate_id = str(selection["candidate_id"])
    source_kind = str(selection["source_kind"])
    source_profile_id = str(selection["source_profile_id"])
    profile = source_profiles.get(source_kind, {}).get(source_profile_id)
    if profile is None:
        raise ValueError(f"Missing source profile for {candidate_id}: {source_kind}/{source_profile_id}")
    process_count = _int_or_none(profile.get("process_count")) or 1
    env = dict(_mapping(profile.get("env")))
    if not env:
        raise ValueError(f"Selected profile has no env mapping: {source_profile_id}")
    entry = {
        "candidate_id": candidate_id,
        "source_kind": source_kind,
        "source_profile_id": source_profile_id,
        "process_count": process_count,
        "env": env,
        "risk": dict(_mapping(profile.get("risk"))),
        "process_priority": str(profile.get("process_priority") or "normal"),
        "frontier_probe_mode": str(profile.get("frontier_probe_mode") or "auto"),
        "execution_enabled": False,
        "real_short_run_blocked_until": BLOCKED_UNTIL,
        "proof_source": False,
        "checkpoint_written": False,
        "stop_rules": list(STOP_RULES),
    }
    if "global_workers" in profile:
        entry["worker_profile_kind"] = "global"
        entry["global_workers"] = _int_or_none(profile.get("global_workers"))
        entry["total_worker_slots"] = _int_or_none(profile.get("total_worker_slots"))
    else:
        entry["worker_profile_kind"] = "stage_specific"
        entry["stage_workers"] = dict(_mapping(profile.get("stage_workers")))
        entry["max_stage_worker_slots"] = _int_or_none(profile.get("max_stage_worker_slots"))
    entry["planned_future_commands"] = [
        _command_template(entry, duration_seconds=duration_seconds)
        for duration_seconds in ALLOWED_DURATIONS_SECONDS
    ]
    return entry


def _command_template(candidate: Mapping[str, Any], *, duration_seconds: int) -> dict[str, Any]:
    if duration_seconds not in ALLOWED_DURATIONS_SECONDS:
        raise ValueError(f"Unsupported short-run duration: {duration_seconds}")
    campaign_hours = round(float(duration_seconds) / 3600.0, 6)
    command = [
        "python",
        "main.py",
        "--mode",
        "certified_exact",
        "--campaign-hours",
        f"{campaign_hours:.6f}",
        "--parallel-processes",
        str(candidate.get("process_count")),
        "--process-priority",
        str(candidate.get("process_priority") or "normal"),
        "--frontier-probe-mode",
        str(candidate.get("frontier_probe_mode") or "auto"),
    ]
    return {
        "candidate_id": str(candidate.get("candidate_id")),
        "duration_seconds": int(duration_seconds),
        "campaign_hours": f"{campaign_hours:.6f}",
        "command_kind": "blocked_future_template",
        "command": command,
        "env": dict(_mapping(candidate.get("env"))),
        "is_executable_now": False,
        "execution_enabled": False,
        "real_short_run_blocked_until": BLOCKED_UNTIL,
        "would_create_canonical_checkpoint_with_current_exact_campaign": True,
        "contains_resume_campaign": False,
        "contains_checkpoint_flag": False,
        "contains_final_168h": False,
        "proof_source": False,
        "checkpoint_written": False,
    }


def _safety_payload() -> dict[str, Any]:
    return {
        "execution_enabled": False,
        "real_short_run_blocked_until": BLOCKED_UNTIL,
        "fresh_solver_run": False,
        "main_py_executed": False,
        "proof_source": False,
        "final_168h_started": False,
        "final_168h_authorized": False,
        "production_long_run_started": False,
        "checkpoint_written": False,
        "checkpoint_imported_back": False,
        "checkpoint_write_or_import_back_authorized": False,
        "runtime_elimination_enabled": False,
        "proof_source_mutated": False,
        "preflight_mutated": False,
        "release_viewer_frontdoor_promoted": False,
        "prod_4x4_normal_default_changed": False,
    }


def _priority_affinity_context(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"available": False}
    topology = _mapping(payload.get("topology"))
    pe_mapping = _mapping(topology.get("pe_mapping"))
    return {
        "available": True,
        "variant_count": len(list(payload.get("variants", []) or [])),
        "pe_mapping_confidence": pe_mapping.get("confidence"),
        "affinity_variants_medium_confirmation_blocked_if_unverified": True,
    }


def _profiles_by_id(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for profile in manifest.get("profiles", []) or []:
        if isinstance(profile, Mapping) and profile.get("profile_id"):
            result[str(profile.get("profile_id"))] = profile
    return result


def _source_summary(path: Path) -> dict[str, Any]:
    return fingerprint_path(Path(path), relative_path=str(path))


def _load_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_optional_json(path: Path) -> Mapping[str, Any] | None:
    if not Path(path).exists():
        return None
    return _load_json(path)


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _assert_local_tuning_namespace(path: Path, *, required_namespace: str) -> None:
    normalized = str(Path(path).resolve()).replace("\\", "/")
    if required_namespace not in normalized or READINESS_SUBDIR not in normalized:
        raise ValueError(f"Refusing to write outside short-run readiness namespace: {path}")


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


def _worker_summary(candidate: Mapping[str, Any]) -> str:
    if candidate.get("worker_profile_kind") == "global":
        return f"global={candidate.get('global_workers')}"
    workers = _mapping(candidate.get("stage_workers"))
    return (
        f"m={workers.get('master')} "
        f"l={workers.get('local_capacity')} "
        f"b={workers.get('binding')} "
        f"r={workers.get('routing')}"
    )


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


if __name__ == "__main__":
    raise SystemExit(main())
