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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.sensitive_path_audit import (  # noqa: E402
    build_sensitive_path_fingerprint,
    compare_sensitive_path_fingerprints,
)
from src.search.exact_campaign import atomic_write_json  # noqa: E402

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
S100_DIR = ARTIFACT_ROOT / "100_signature_bucket_outer_exact_core_overlay_residual_strategy"
S101_DIR = (
    ARTIFACT_ROOT
    / "101_signature_bucket_outer_exact_core_overlay_residual_external_review_package"
)
DEFAULT_RUN_ID = "s100_s101_outer_overlay_residual_review_001"

S98_REVIEW_SUMMARY = (
    ARTIFACT_ROOT
    / "98_signature_bucket_residual_overlay_probe_external_review_package"
    / "s96_s97_residual_overlay_probe_review_001"
    / "external_review_reply_summary.json"
)
S99_PROBE = (
    ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_signature_bucket_residual_overlay_inst_no_solve_001"
    / "overlay_timing_probe.json"
)
S97_REVIEW = (
    ARTIFACT_ROOT
    / "97_signature_bucket_residual_overlay_probe_review"
    / "signature_bucket_residual_overlay_probe_review.json"
)
S99_SUMMARY = (
    ARTIFACT_ROOT
    / "99_signature_bucket_residual_overlay_probe_execution"
    / "signature_bucket_residual_overlay_probe_execution.json"
)
S95_IMPLEMENTATION = (
    ARTIFACT_ROOT
    / "95_signature_bucket_residual_overlay_instrumentation_implementation"
    / "signature_bucket_residual_overlay_instrumentation_implementation.json"
)

PACKAGE_INPUTS = {
    "s98_review_summary": S98_REVIEW_SUMMARY,
    "s99_probe": S99_PROBE,
    "s97_probe_review": S97_REVIEW,
    "s99_execution_summary": S99_SUMMARY,
    "s95_implementation": S95_IMPLEMENTATION,
    "agents_gate": WORKSPACE_ROOT / "AGENTS.md",
    "master_model_source": PROJECT_ROOT / "src" / "models" / "master_model.py",
    "exact_coordinate_master_source": PROJECT_ROOT
    / "src"
    / "models"
    / "exact_coordinate_master.py",
    "test_master": PROJECT_ROOT / "src" / "tests" / "test_master.py",
    "exact_contract_tests": PROJECT_ROOT / "src" / "tests" / "test_exact_contract.py",
    "s96_readiness_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_residual_overlay_probe_readiness.py",
    "s97_review_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_residual_overlay_probe_review.py",
    "s100_s101_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_outer_overlay_residual_external_review_package.py",
    "s100_s101_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_outer_overlay_residual_external_review_package.py",
}

REVIEW_WORDING_REQUIREMENTS = (
    "needs review first",
    "review is not authorization",
    "if review passes request user/project-owner authorization",
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_outer_overlay_residual_strategy(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.strategy_output_dir),
        no_write=bool(args.no_write),
    )
    package = build_outer_overlay_residual_external_review_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.package_output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket outer exact-core overlay residual strategy/package")
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
            "Build S100 outer exact-core overlay residual strategy and S101 external review package."
        )
    )
    parser.add_argument("--strategy-output-dir", type=Path, default=S100_DIR)
    parser.add_argument("--package-output-dir", type=Path, default=S101_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_outer_overlay_residual_strategy(
    *,
    project_root: Path,
    output_dir: Path,
    no_write: bool = False,
    s97_review_path: Path = S97_REVIEW,
    s99_probe_path: Path = S99_PROBE,
    s99_summary_path: Path = S99_SUMMARY,
    s98_review_summary_path: Path = S98_REVIEW_SUMMARY,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = _resolve_path(project_root, output_dir)
    _assert_strategy_namespace(output_dir)
    s97 = _load_json(_resolve_path(project_root, s97_review_path))
    probe = _load_json(_resolve_path(project_root, s99_probe_path))
    s99 = _load_json(_resolve_path(project_root, s99_summary_path))
    s98 = _load_json(_resolve_path(project_root, s98_review_summary_path))
    classification = _classify_strategy(s97=s97, probe=probe, s99=s99, s98=s98)
    residual = _mapping(s97.get("residual_overlay_summary"))
    interpretation = _mapping(s97.get("interpretation"))
    phase_seconds = _mapping(residual.get("phase_seconds"))
    exact_core_reuse = _mapping(
        _mapping(_mapping(probe.get("inventory")).get("build_stats_summary")).get(
            "exact_core_reuse"
        )
    )
    payload = {
        "schema": "phase3b-signature-bucket-outer-exact-core-overlay-residual-strategy/v0",
        "generated_at": _now(),
        "status": "completed" if classification != "manual_review_required" else "manual_review_required",
        "classification": classification,
        "project_root": str(project_root),
        "inputs": {
            "s97_review": str(_resolve_path(project_root, s97_review_path)),
            "s99_probe": str(_resolve_path(project_root, s99_probe_path)),
            "s99_execution_summary": str(_resolve_path(project_root, s99_summary_path)),
            "s98_review_summary": str(_resolve_path(project_root, s98_review_summary_path)),
        },
        "evidence": {
            "s98_review_verdict": s98.get("review_verdict"),
            "s97_status": s97.get("status"),
            "s97_classification": interpretation.get("classification"),
            "s99_status": probe.get("status"),
            "s99_summary_status": s99.get("status"),
            "model_build_seconds": _float(s97.get("model_build_seconds")),
            "overlay_build_seconds": _float(exact_core_reuse.get("overlay_build_seconds")),
            "ghost_constraint_seconds": _float(exact_core_reuse.get("ghost_constraint_seconds")),
            "outer_exact_core_overlay_residual_seconds": _float(
                phase_seconds.get("outer_exact_core_overlay_residual_seconds")
            ),
            "payload_footprint_cohort_build_seconds": _float(
                phase_seconds.get("payload_footprint_cohort_build_seconds")
            ),
            "residual_signature_scan_seconds": _float(
                phase_seconds.get("residual_signature_scan_seconds")
            ),
            "search_guidance_rebuilt_after_ghost_overlay": exact_core_reuse.get(
                "search_guidance_rebuilt_after_ghost_overlay"
            ),
            "cleared_existing_search_strategy_count": exact_core_reuse.get(
                "cleared_existing_search_strategy_count"
            ),
            "rebuilt_search_strategy_count": exact_core_reuse.get(
                "rebuilt_search_strategy_count"
            ),
        },
        "future_patch_spec_for_review": {
            "implementation_allowed_now": False,
            "review_required_before_authorization": True,
            "source_mutation_performed": False,
            "proposed_scope": "default_off_stats_only_subphase_instrumentation_inside_MasterPlacementModel.from_exact_core",
            "env_gate": "EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION",
            "output_path": "build_stats.exact_core_reuse.residual_overlay_instrumentation.outer_exact_core_overlay_subphase_seconds",
            "subphases_to_measure": [
                "profile_validation",
                "model_shell_construction",
                "model_proto_clone_bind",
                "build_stats_deepcopy",
                "mandatory_group_and_candidate_cache_copy",
                "pre_ghost_stats_publish",
                "coordinate_delegate_bind_from_core",
                "ghost_constraint_add",
                "search_guidance_rebuild",
                "coordinate_delegate_finalize_build_stats",
                "signature_var_sync",
                "exact_core_reuse_stats_publish",
            ],
            "must_not_change": [
                "ModelProto",
                "variables",
                "constraints",
                "hints",
                "search_strategy",
                "scheduler_inputs",
                "proof_inputs",
                "checkpoint_files",
                "production_defaults",
            ],
            "rejected_actions": [
                "do_not_optimize_or_refactor_from_exact_core_in_this_slice",
                "do_not_call_CpSolver_Solve",
                "do_not_run_runtime_or_67x20",
                "do_not_write_checkpoints_or_proof_artifacts",
            ],
        },
        "safety": {
            "execute_no_solve": probe.get("execute_no_solve"),
            "cp_solver_solve_called": probe.get("cp_solver_solve_called"),
            "runtime_execution_performed": probe.get("runtime_execution_performed"),
            "main_py_executed": probe.get("main_py_executed"),
            "exact_campaign_used": probe.get("exact_campaign_used"),
            "checkpoint_written": probe.get("checkpoint_written"),
            "proof_source": probe.get("proof_source"),
            "source_model_mutation": probe.get("source_model_mutation"),
            "source_mutation_performed": probe.get("source_mutation_performed"),
            "sensitive_path_changed": _mapping(probe.get("sensitive_path_comparison")).get(
                "changed"
            ),
        },
        "next_gate": {
            "status": "hold_for_outer_overlay_residual_external_review",
            "next_engineering_step": "external_review_s100_before_any_source_patch_or_probe",
            "blocked_actions": [
                "do_not_patch_source_until_review_passes_and_authorized",
                "do_not_run_another_enabled_42x32_probe",
                "do_not_run_runtime_solve",
                "do_not_run_67x20",
                "do_not_run_full_wave_or_168h",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
            ],
        },
    }
    if not no_write:
        output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            output_dir / "signature_bucket_outer_exact_core_overlay_residual_strategy.json",
            payload,
        )
        (output_dir / "signature_bucket_outer_exact_core_overlay_residual_strategy.md").write_text(
            render_strategy_markdown(payload),
            encoding="utf-8",
        )
    return payload


def build_outer_overlay_residual_external_review_package(
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
    input_paths["s100_strategy"] = (
        S100_DIR / "signature_bucket_outer_exact_core_overlay_residual_strategy.json"
    )
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
        "schema": "phase3b-signature-bucket-outer-exact-core-overlay-residual-external-review-package/v0",
        "generated_at": _now(),
        "status": status,
        "package_kind": "external_review_outer_exact_core_overlay_residual_strategy_package",
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
            "# Phase3B S100 Outer Exact-Core Overlay Residual Strategy",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Classification: `{payload.get('classification')}`",
            f"- Model build seconds: `{evidence.get('model_build_seconds')}`",
            f"- Overlay build seconds: `{evidence.get('overlay_build_seconds')}`",
            f"- Ghost constraint seconds: `{evidence.get('ghost_constraint_seconds')}`",
            f"- Outer exact-core overlay residual seconds: `{evidence.get('outer_exact_core_overlay_residual_seconds')}`",
            f"- Payload footprint cohort build seconds: `{evidence.get('payload_footprint_cohort_build_seconds')}`",
            f"- Residual signature scan seconds: `{evidence.get('residual_signature_scan_seconds')}`",
            "",
            "S99 shows the remaining dominant no-solve hotspot is the pre-ghost outer exact-core overlay residual. The next safe step is review-first default-off subphase instrumentation in `MasterPlacementModel.from_exact_core`, not an optimization patch or another probe.",
            "",
        ]
    )


def render_package_markdown(payload: Mapping[str, Any]) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    return "\n".join(
        [
            "# Phase3B S101 Outer Exact-Core Overlay Residual External Review Package",
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
            "This package asks external review to validate the S100 strategy and future default-off stats-only subphase instrumentation scope before any source patch or further probe.",
            "",
        ]
    )


def _review_request_text(package_filename: str, package_sha256: str) -> str:
    return "\n".join(
        [
            "# Review Request: Phase3B S100 Outer Exact-Core Overlay Residual Strategy",
            "",
            f"Uploaded package to review: `{package_filename}`",
            f"SHA256: `{package_sha256}`",
            "",
            "Status: needs review first. This review is not authorization. If review passes request user/project-owner authorization before any source patch, enabled probe, runtime, checkpoint, proof, or production-default action. Gate marker: if review passes request user/project-owner authorization.",
            "",
            "Context: S99 executed exactly one reviewed and authorized `42x32` enabled no-solve residual-overlay probe. S97 classifies the result as `outer_exact_core_overlay_residual_hotspot`: model build is about 12.87s, with `outer_exact_core_overlay_residual_seconds` about 6.82s, `payload_footprint_cohort_build_seconds` about 2.60s, and `residual_signature_scan_seconds` about 2.16s. Safety stayed clean: no solver runtime, no CP-SAT Solve, no `main.py`, no `ExactCampaign`, no checkpoint write, no proof source, no source/model mutation, and sensitive paths stayed unchanged.",
            "",
            "S100 proposes a future default-off stats-only source patch, not implemented in this slice. The proposed scope is to extend the existing `EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION` enabled output in `src/models/master_model.py::MasterPlacementModel.from_exact_core` with `outer_exact_core_overlay_subphase_seconds`, splitting the current outer residual into profile validation, model shell construction, proto clone/bind, build_stats deepcopy, mandatory group/candidate cache copy, pre-ghost stats publication, coordinate delegate bind, search guidance rebuild, finalize build stats, signature var sync, and final exact_core_reuse stats publication. Disabled/unset behavior must remain byte-for-byte output-compatible.",
            "",
            "Please review the package contents and answer these gate questions:",
            "",
            "1. Does S99/S97 evidence support the classification `outer_exact_core_overlay_residual_hotspot`?",
            "2. Is the proposed future patch scope narrow enough: default-off, stats-only, limited to `MasterPlacementModel.from_exact_core` subphase timing and existing residual overlay instrumentation output?",
            "3. Should the future patch reuse `EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION`, or is a separate env gate required for safety/review clarity?",
            "4. Are the proposed subphase fields sufficient to separate proto clone/bind, build_stats deepcopy, candidate/cache copy, search-guidance rebuild, finalize/publish, and variable-sync costs?",
            "5. Does anything in S100/S101 risk ModelProto, variables, constraints, hints, scheduler/proof/checkpoint integration, runtime execution, or production defaults?",
            "",
            "Please answer with explicit machine-readable fields:",
            "",
            "review_verdict: pass|fail",
            "review_is_authorization: false",
            "authorization_required_next: true|false",
            "blockers: [] or a list",
            "",
            "If review passes, the verdict should only be: safe to request user/project-owner authorization for a future default-off stats-only outer exact-core overlay residual subphase instrumentation patch. The review must not be treated as authorization itself.",
            "",
        ]
    )


def _classify_strategy(
    *, s97: Mapping[str, Any], probe: Mapping[str, Any], s99: Mapping[str, Any], s98: Mapping[str, Any]
) -> str:
    interpretation = _mapping(s97.get("interpretation"))
    safety = _mapping(s97.get("probe_safety"))
    clean = (
        s98.get("review_verdict") == "pass"
        and s97.get("status") == "completed"
        and interpretation.get("classification") == "outer_exact_core_overlay_residual_hotspot"
        and probe.get("status") == "completed"
        and s99.get("status") == "completed"
        and safety.get("sensitive_path_clean") is True
        and probe.get("cp_solver_solve_called") is False
        and probe.get("runtime_execution_performed") is False
        and probe.get("checkpoint_written") is False
        and probe.get("proof_source") is False
        and probe.get("source_mutation_performed") is False
    )
    return (
        "outer_exact_core_overlay_residual_subphase_strategy_required"
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
    return {
        "validated": bool(package_hash_matches and manifest_path.exists() and request_ok),
        "package_hash_matches": package_hash_matches,
        "manifest_exists": manifest_path.exists(),
        "manifest_entry_count": len(_sequence(manifest.get("entries"))),
        "request_text_contains_required_wording": request_ok,
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    return value if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []


def _float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else project_root / path


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def _assert_strategy_namespace(output_dir: Path) -> None:
    normalized = output_dir.as_posix()
    if "/100_signature_bucket_outer_exact_core_overlay_residual_strategy" not in normalized:
        raise ValueError(f"S100 strategy namespace violation: {output_dir}")


def _assert_package_namespace(output_dir: Path) -> None:
    normalized = output_dir.as_posix()
    if "/101_signature_bucket_outer_exact_core_overlay_residual_external_review_package" not in normalized:
        raise ValueError(f"S101 package namespace violation: {output_dir}")


if __name__ == "__main__":
    raise SystemExit(main())
