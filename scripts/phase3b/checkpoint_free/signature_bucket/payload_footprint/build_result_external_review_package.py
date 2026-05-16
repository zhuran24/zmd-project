from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[5]
WORKSPACE_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.sensitive_path_audit import (  # noqa: E402
    build_sensitive_path_fingerprint,
    compare_sensitive_path_fingerprints,
)
from src.search.exact_campaign import atomic_write_json  # noqa: E402

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
S91_DIR = ARTIFACT_ROOT / "91_signature_bucket_payload_footprint_result_strategy"
S92_DIR = ARTIFACT_ROOT / "92_signature_bucket_payload_footprint_result_external_review_package"
DEFAULT_RUN_ID = "s89_payload_footprint_result_review_001"

S89_PROBE = (
    ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_signature_bucket_payload_footprint_inst_no_solve_001"
    / "overlay_timing_probe.json"
)
S87_REVIEW = (
    ARTIFACT_ROOT
    / "87_signature_bucket_payload_footprint_probe_review"
    / "signature_bucket_payload_footprint_probe_review.json"
)
S88_SUMMARY = (
    ARTIFACT_ROOT
    / "88_signature_bucket_payload_footprint_probe_external_review_package"
    / "s86_s87_payload_footprint_probe_review_001"
    / "external_review_reply_summary.json"
)
S89_SUMMARY = (
    ARTIFACT_ROOT
    / "89_signature_bucket_payload_footprint_probe_execution"
    / "signature_bucket_payload_footprint_probe_execution.json"
)
S90_SUMMARY = (
    ARTIFACT_ROOT
    / "90_s87_payload_footprint_zero_fallback_review_hardening_implementation"
    / "s87_payload_footprint_zero_fallback_review_hardening.json"
)

PACKAGE_INPUTS = {
    "s88_review_summary": S88_SUMMARY,
    "s89_probe": S89_PROBE,
    "s89_execution_summary": S89_SUMMARY,
    "s87_probe_review": S87_REVIEW,
    "s90_review_hardening": S90_SUMMARY,
    "agents_gate": WORKSPACE_ROOT / "AGENTS.md",
    "exact_coordinate_master_source": PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py",
    "test_master": PROJECT_ROOT / "src" / "tests" / "test_master.py",
    "exact_contract_tests": PROJECT_ROOT / "src" / "tests" / "test_exact_contract.py",
    "s87_review_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "payload_footprint" / "build_probe_review.py",
    "s87_review_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_payload_footprint_probe_review.py",
    "s91_s92_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "payload_footprint" / "build_result_external_review_package.py",
    "s91_s92_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_payload_footprint_result_external_review_package.py",
}

REVIEW_WORDING_REQUIREMENTS = (
    "needs review first",
    "review is not authorization",
    "if review passes request user/project-owner authorization",
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_payload_footprint_result_strategy(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.strategy_output_dir),
        no_write=bool(args.no_write),
    )
    package = build_payload_footprint_result_external_review_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.package_output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket payload-footprint result strategy/package")
    print(f"strategy_status={strategy['status']}")
    print(f"strategy_classification={strategy['classification']}")
    print(f"package_status={package['status']}")
    print(f"zip_path={_display_path(PROJECT_ROOT, Path(package['zip_path']))}")
    print(f"zip_sha256={package.get('zip_sha256')}")
    print(f"clean_extraction_validated={package['clean_extraction_validation']['validated']}")
    return 0 if strategy["status"] == "completed" and package["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build S91 payload-footprint result strategy and S92 external review package."
        )
    )
    parser.add_argument("--strategy-output-dir", type=Path, default=S91_DIR)
    parser.add_argument("--package-output-dir", type=Path, default=S92_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_payload_footprint_result_strategy(
    *,
    project_root: Path,
    output_dir: Path,
    no_write: bool = False,
    s87_review_path: Path = S87_REVIEW,
    s89_probe_path: Path = S89_PROBE,
    s90_summary_path: Path = S90_SUMMARY,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = _resolve_path(project_root, output_dir)
    _assert_strategy_namespace(output_dir)
    s87 = _load_json(_resolve_path(project_root, s87_review_path))
    probe = _load_json(_resolve_path(project_root, s89_probe_path))
    s90 = _load_json(_resolve_path(project_root, s90_summary_path))
    interpretation = _mapping(s87.get("interpretation"))
    safety = _mapping(s87.get("probe_safety"))
    signature = _mapping(s87.get("signature_instrumentation"))
    phases = {
        str(item.get("phase")): float(item.get("total_seconds"))
        for item in _sequence(_mapping(probe.get("timing")).get("phases"))
        if isinstance(item, Mapping) and isinstance(item.get("total_seconds"), (int, float))
    }
    phase_seconds = _mapping(signature.get("phase_seconds"))
    classification = _classify_strategy(s87=s87, probe=probe, s90=s90)
    payload = {
        "schema": "phase3b-signature-bucket-payload-footprint-result-strategy/v0",
        "generated_at": _now(),
        "status": "completed" if classification != "manual_review_required" else "manual_review_required",
        "classification": classification,
        "project_root": str(project_root),
        "inputs": {
            "s87_review": str(_resolve_path(project_root, s87_review_path)),
            "s89_probe": str(_resolve_path(project_root, s89_probe_path)),
            "s90_review_hardening": str(_resolve_path(project_root, s90_summary_path)),
        },
        "evidence": {
            "s87_status": s87.get("status"),
            "s87_classification": interpretation.get("classification"),
            "s89_status": probe.get("status"),
            "s90_status": s90.get("status"),
            "model_build_seconds": _float(probe.get("inventory", {}).get("model_build_seconds")),
            "from_exact_core_total_seconds": _float(_mapping(probe.get("timing")).get("from_exact_core_total_seconds")),
            "ghost_constraint_seconds": _float(
                _mapping(_mapping(_mapping(probe.get("inventory")).get("build_stats_summary")).get("exact_core_reuse")).get(
                    "ghost_constraint_seconds"
                )
            ),
            "signature_bucket_tightening_seconds": phases.get(
                "CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening"
            ),
            "signature_residual_tightening_seconds": phases.get(
                "CoordinateExactMasterDelegate._apply_ghost_anchor_residual_signature_bucket_tightening"
            ),
            "via_pole_screen_seconds": phases.get(
                "CoordinateExactMasterDelegate._apply_ghost_anchor_power_capacity_screen"
            ),
            "mandatory_payload_build_seconds": _float(phase_seconds.get("mandatory_payload_build")),
            "mandatory_scan_seconds": interpretation.get("current_mandatory_scan_seconds"),
            "mandatory_scan_reduction_ratio": interpretation.get("mandatory_scan_reduction_ratio"),
            "baseline_unstable_footprint_bounds_fallbacks": interpretation.get(
                "baseline_unstable_footprint_bounds_fallbacks"
            ),
            "current_unstable_footprint_bounds_fallbacks": interpretation.get(
                "current_unstable_footprint_bounds_fallbacks"
            ),
            "payload_footprint_stability_used": interpretation.get("payload_footprint_stability_used"),
            "payload_footprint_stability_fallbacks": interpretation.get(
                "payload_footprint_stability_fallbacks"
            ),
        },
        "safety": {
            "status_completed": safety.get("status_completed"),
            "execute_no_solve": safety.get("execute_no_solve"),
            "cp_solver_solve_called": probe.get("cp_solver_solve_called"),
            "runtime_execution_performed": probe.get("runtime_execution_performed"),
            "main_py_executed": probe.get("main_py_executed"),
            "exact_campaign_used": probe.get("exact_campaign_used"),
            "checkpoint_written": probe.get("checkpoint_written"),
            "proof_source": probe.get("proof_source"),
            "sensitive_path_changed": _mapping(probe.get("sensitive_path_comparison")).get("changed"),
        },
        "conclusion": {
            "payload_footprint_stability_effective": classification
            == "payload_footprint_effective_residual_overlay_strategy_required",
            "mandatory_scan_no_longer_primary_hotspot": True,
            "residual_work_is_strategy_review_first": True,
            "runtime_or_source_patch_allowed_now": False,
        },
        "next_gate": {
            "status": "hold_for_payload_footprint_result_external_review",
            "next_engineering_step": "external_review_s91_result_before_runtime_or_source_patch",
            "blocked_actions": [
                "do_not_run_another_enabled_42x32_probe",
                "do_not_run_runtime_solve",
                "do_not_run_67x20",
                "do_not_run_full_wave",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
                "do_not_patch_solver_model_without_new_review_and_authorization",
            ],
        },
    }
    if not no_write:
        output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(output_dir / "signature_bucket_payload_footprint_result_strategy.json", payload)
        (output_dir / "signature_bucket_payload_footprint_result_strategy.md").write_text(
            render_strategy_markdown(payload),
            encoding="utf-8",
        )
    return payload


def build_payload_footprint_result_external_review_package(
    *,
    project_root: Path,
    output_dir: Path,
    run_id: str = DEFAULT_RUN_ID,
    no_write: bool = False,
    inputs: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = _resolve_path(project_root, output_dir)
    _assert_package_namespace(output_dir)
    input_paths = {
        key: _resolve_path(project_root, value)
        for key, value in dict(inputs or PACKAGE_INPUTS).items()
    }
    input_paths["s91_strategy"] = S91_DIR / "signature_bucket_payload_footprint_result_strategy.json"
    before = build_sensitive_path_fingerprint(project_root)
    run_dir = output_dir / str(run_id)
    staging_dir = run_dir / "staging"
    clean_extract_dir = run_dir / "clean_extract"
    zip_path = run_dir / f"{run_id}.zip"
    manifest = _manifest(project_root=project_root, run_id=run_id, zip_path=zip_path, inputs=input_paths)
    validation: dict[str, Any] = {"validated": False, "reason": "no_write"}
    zip_sha256: str | None = None
    request_text = _review_request_text(zip_path.name, "not built in no-write mode")
    if not no_write:
        if run_dir.exists():
            shutil.rmtree(run_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)
        _write_staging_files(staging_dir=staging_dir, manifest=manifest, inputs=input_paths)
        _write_zip(staging_dir, zip_path)
        zip_sha256 = _sha256(zip_path)
        manifest["zip_sha256"] = zip_sha256
        request_text = _review_request_text(zip_path.name, zip_sha256)
        atomic_write_json(run_dir / "manifest.json", manifest)
        (run_dir / "review_request.md").write_text(request_text, encoding="utf-8")
        (run_dir / "zip_sha256.txt").write_text(f"{zip_sha256}  {zip_path.name}\n", encoding="utf-8")
        validation = _validate_clean_extraction(
            zip_path=zip_path,
            extract_dir=clean_extract_dir,
            expected_zip_sha256=zip_sha256,
            request_text=request_text,
        )
        atomic_write_json(run_dir / "clean_extraction_validation.json", validation)
    after = build_sensitive_path_fingerprint(project_root)
    sensitive_comparison = compare_sensitive_path_fingerprints(before, after)
    status = (
        "completed"
        if (no_write or validation.get("validated")) and not sensitive_comparison.get("changed")
        else "failed"
    )
    payload = {
        "schema": "phase3b-signature-bucket-payload-footprint-result-external-review-package/v0",
        "generated_at": _now(),
        "status": status,
        "package_kind": "external_review_payload_footprint_effective_result_strategy_package",
        "project_root": str(project_root),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "zip_path": str(zip_path),
        "zip_sha256": zip_sha256,
        "probe_execution_enabled": False,
        "review_required_before_authorization": True,
        "external_review_is_authorization": False,
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "proof_source": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
        "candidate_universe_changed": False,
        "scheduler_integration": False,
        "runtime_execution_performed": False,
        "production_profile_changed": False,
        "inputs": {key: str(path) for key, path in input_paths.items()},
        "manifest": manifest,
        "clean_extraction_validation": validation,
        "sensitive_path_comparison": sensitive_comparison,
    }
    if not no_write:
        atomic_write_json(run_dir / "external_review_package_summary.json", payload)
        (run_dir / "external_review_package_summary.md").write_text(
            render_package_markdown(payload),
            encoding="utf-8",
        )
        atomic_write_json(run_dir / "sensitive_path_before.json", before)
        atomic_write_json(run_dir / "sensitive_path_after.json", after)
        atomic_write_json(run_dir / "sensitive_path_comparison.json", sensitive_comparison)
    return payload


def render_strategy_markdown(payload: Mapping[str, Any]) -> str:
    evidence = _mapping(payload.get("evidence"))
    return "\n".join(
        [
            "# Phase3B S91 Payload-Footprint Result Strategy",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Classification: `{payload.get('classification')}`",
            f"- Model build seconds: `{evidence.get('model_build_seconds')}`",
            f"- Signature bucket tightening seconds: `{evidence.get('signature_bucket_tightening_seconds')}`",
            f"- Mandatory payload build seconds: `{evidence.get('mandatory_payload_build_seconds')}`",
            f"- Mandatory scan seconds: `{evidence.get('mandatory_scan_seconds')}`",
            f"- Mandatory scan reduction ratio: `{evidence.get('mandatory_scan_reduction_ratio')}`",
            f"- Current unstable footprint fallbacks: `{evidence.get('current_unstable_footprint_bounds_fallbacks')}`",
            "",
            "S89 shows payload-footprint stability support is effective and removes the previous mandatory scan fallback wall-clock hotspot. The next step is review-first residual strategy, not another probe, runtime solve, or source patch.",
            "",
        ]
    )


def render_package_markdown(payload: Mapping[str, Any]) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    return "\n".join(
        [
            "# Phase3B S92 Payload-Footprint Result External Review Package",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Zip: `{payload.get('zip_path')}`",
            f"- SHA256: `{payload.get('zip_sha256')}`",
            f"- Clean extraction validated: `{validation.get('validated')}`",
            "- Probe execution enabled: `false`",
            "- Source mutation performed: `false`",
            "- Runtime execution performed: `false`",
            "- Checkpoint written: `false`",
            "- Proof source: `false`",
            "- Review required before authorization: `true`",
            "",
            "This package asks external review to validate the S89/S90 interpretation before any runtime, source patch, or further probe.",
            "",
        ]
    )


def _review_request_text(package_filename: str, package_sha256: str) -> str:
    return "\n".join(
        [
            "# Review Request: Phase3B S91 Payload-Footprint Result Strategy",
            "",
            f"Uploaded package to review: `{package_filename}`",
            f"SHA256: `{package_sha256}`",
            "",
            "Status: needs review first. This review is not authorization. If review passes request user/project-owner authorization before any next runtime, source patch, or further enabled probe. Gate marker: if review passes request user/project-owner authorization.",
            "",
            "Context: S89 executed exactly one reviewed and authorized `42x32` enabled no-solve payload-footprint probe. S87 now classifies the result as `payload_footprint_stability_effective`: mandatory scan dropped from about 26.631s to about 0.124s, unstable footprint fallbacks dropped from 6786 to 0, and no solve/runtime/checkpoint/proof path was touched. S90 fixed only the S87 review-builder zero-current-fallback edge case: empty support-gap reasons are valid when current fallbacks are zero; positive fallbacks with empty reasons remain inconclusive.",
            "",
            "Please review the package contents and answer these gate questions:",
            "",
            "1. Does the S89 evidence support the conclusion that payload-footprint stability support was effective and safety-clean?",
            "2. Is the S90 zero-fallback review-tooling hardening conservative enough?",
            "3. Is S91 correct that mandatory scan is no longer the primary hotspot and the next step should be residual strategy/review instead of another enabled probe?",
            "4. Are there any proof/checkpoint/runtime/production-default risks in treating S89 as local diagnostic evidence only?",
            "5. If the review passes, is it safe to request user/project-owner authorization for the next residual strategy step, while still not authorizing runtime, source patches, checkpoints, or proof changes?",
            "",
            "Please answer with one of:",
            "",
            "- `review_verdict=pass`: S91/S92 are safe to use as the next gate input; review is not authorization.",
            "- `review_verdict=fail`: list concrete blockers that must be fixed before authorization or next-step planning.",
            "",
        ]
    )


def _classify_strategy(*, s87: Mapping[str, Any], probe: Mapping[str, Any], s90: Mapping[str, Any]) -> str:
    interpretation = _mapping(s87.get("interpretation"))
    safety = _mapping(s87.get("probe_safety"))
    clean = (
        s87.get("status") == "completed"
        and interpretation.get("classification") == "payload_footprint_stability_effective"
        and probe.get("status") == "completed"
        and s90.get("status") == "implemented_and_verified"
        and safety.get("sensitive_path_clean") is True
        and probe.get("cp_solver_solve_called") is False
        and probe.get("runtime_execution_performed") is False
        and probe.get("checkpoint_written") is False
        and probe.get("proof_source") is False
    )
    return (
        "payload_footprint_effective_residual_overlay_strategy_required"
        if clean
        else "manual_review_required"
    )


def _manifest(*, project_root: Path, run_id: str, zip_path: Path, inputs: Mapping[str, Path]) -> dict[str, Any]:
    entries = []
    for key, path in sorted(inputs.items()):
        exists = path.exists()
        entries.append(
            {
                "key": key,
                "path": str(path),
                "package_path": f"evidence/{key}/{path.name}" if exists else None,
                "exists": exists,
                "size_bytes": path.stat().st_size if exists and path.is_file() else None,
                "sha256": _sha256(path) if exists and path.is_file() else None,
            }
        )
    return {
        "schema": "phase3b-review-package-manifest/v0",
        "generated_at": _now(),
        "run_id": run_id,
        "project_root": str(project_root),
        "zip_filename": zip_path.name,
        "zip_sha256": None,
        "entries": entries,
    }


def _write_staging_files(*, staging_dir: Path, manifest: Mapping[str, Any], inputs: Mapping[str, Path]) -> None:
    atomic_write_json(staging_dir / "manifest.json", dict(manifest))
    for key, path in inputs.items():
        if not path.exists() or not path.is_file():
            continue
        target = staging_dir / "evidence" / key / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _write_zip(staging_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(staging_dir).as_posix())


def _validate_clean_extraction(
    *, zip_path: Path, extract_dir: Path, expected_zip_sha256: str, request_text: str
) -> dict[str, Any]:
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    manifest_path = extract_dir / "manifest.json"
    package_hash_matches = _sha256(zip_path) == expected_zip_sha256
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    request_ok = all(needle in request_text for needle in REVIEW_WORDING_REQUIREMENTS)
    evidence_entries = _sequence(manifest.get("entries"))
    missing_entries = [
        entry.get("key")
        for entry in evidence_entries
        if isinstance(entry, Mapping)
        and entry.get("exists") is True
        and not (extract_dir / str(entry.get("package_path"))).exists()
    ]
    return {
        "schema": "phase3b-clean-extraction-validation/v0",
        "validated": bool(package_hash_matches and manifest_path.exists() and request_ok and not missing_entries),
        "zip_path": str(zip_path),
        "extract_dir": str(extract_dir),
        "package_hash_matches": package_hash_matches,
        "manifest_exists": manifest_path.exists(),
        "request_wording_ok": request_ok,
        "missing_entries": missing_entries,
    }


def _assert_strategy_namespace(output_dir: Path) -> None:
    normalized = str(output_dir).replace("\\", "/")
    if "/91_signature_bucket_payload_footprint_result_strategy" not in normalized:
        raise ValueError(f"S91 strategy namespace violation: {output_dir}")


def _assert_package_namespace(output_dir: Path) -> None:
    normalized = str(output_dir).replace("\\", "/")
    if "/92_signature_bucket_payload_footprint_result_external_review_package" not in normalized:
        raise ValueError(f"S92 package namespace violation: {output_dir}")


def _load_json(path: Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8-sig") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_path(project_root: Path, value: Path) -> Path:
    value = Path(value)
    if value.is_absolute():
        return value.resolve()
    return (project_root / value).resolve()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
