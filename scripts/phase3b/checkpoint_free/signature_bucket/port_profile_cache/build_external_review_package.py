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
S114_DIR = ARTIFACT_ROOT / "114_signature_bucket_port_profile_cache_strategy"
S115_DIR = ARTIFACT_ROOT / "115_signature_bucket_port_profile_cache_external_review_package"
DEFAULT_RUN_ID = "s114_port_profile_cache_review_001"

S111_REVIEW = (
    ARTIFACT_ROOT
    / "111_signature_bucket_model_shell_subphase_probe_review"
    / "signature_bucket_model_shell_subphase_probe_review.json"
)
S112_REVIEW_SUMMARY = (
    ARTIFACT_ROOT
    / "112_signature_bucket_model_shell_subphase_probe_external_review_package"
    / "s110_s111_model_shell_subphase_probe_review_001"
    / "external_review_reply_summary.json"
)
S113_EXECUTION = (
    ARTIFACT_ROOT
    / "113_signature_bucket_model_shell_subphase_probe_execution"
    / "signature_bucket_model_shell_subphase_probe_execution.json"
)
S109_IMPLEMENTATION = (
    ARTIFACT_ROOT
    / "109_signature_bucket_model_shell_subphase_instrumentation_implementation"
    / "signature_bucket_model_shell_subphase_instrumentation_implementation.json"
)

PACKAGE_INPUTS = {
    "s109_implementation": S109_IMPLEMENTATION,
    "s111_probe_review": S111_REVIEW,
    "s112_review_summary": S112_REVIEW_SUMMARY,
    "s113_probe_execution": S113_EXECUTION,
    "s114_strategy": S114_DIR / "signature_bucket_port_profile_cache_strategy.json",
    "agents_gate": WORKSPACE_ROOT / "AGENTS.md",
    "master_model_source": PROJECT_ROOT / "src" / "models" / "master_model.py",
    "exact_coordinate_master_source": PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py",
    "test_master": PROJECT_ROOT / "src" / "tests" / "test_master.py",
    "exact_contract_tests": PROJECT_ROOT / "src" / "tests" / "test_exact_contract.py",
    "s110_readiness_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "model_shell" / "build_subphase_probe_readiness.py",
    "s111_review_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "model_shell" / "build_subphase_probe_review.py",
    "s114_s115_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "port_profile_cache" / "build_external_review_package.py",
    "s110_readiness_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_model_shell_subphase_probe_readiness.py",
    "s111_review_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_model_shell_subphase_probe_review.py",
    "s114_s115_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_port_profile_cache_external_review_package.py",
}

REVIEW_WORDING_REQUIREMENTS = (
    "needs review first",
    "review is not authorization",
    "if review passes request user/project-owner authorization",
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_port_profile_cache_strategy(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.strategy_output_dir),
        no_write=bool(args.no_write),
    )
    package = build_port_profile_cache_external_review_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.package_output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket port/profile cache strategy/package")
    print(f"strategy_status={strategy['status']}")
    print(f"strategy_classification={strategy['classification']}")
    print(f"package_status={package['status']}")
    print(f"zip_path={_display_path(PROJECT_ROOT, Path(package['zip_path']))}")
    print(f"zip_sha256={package.get('zip_sha256')}")
    print(f"expanded_bundle={_display_path(PROJECT_ROOT, Path(package['expanded_review_bundle_path']))}")
    print(f"expanded_bundle_sha256={package.get('expanded_review_bundle_sha256')}")
    print(f"clean_extraction_validated={package['clean_extraction_validation']['validated']}")
    return 0 if strategy["status"] == "completed" and package["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build S114 port/profile boundary-cache hotspot strategy and S115 "
            "external review package."
        )
    )
    parser.add_argument("--strategy-output-dir", type=Path, default=S114_DIR)
    parser.add_argument("--package-output-dir", type=Path, default=S115_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_port_profile_cache_strategy(
    *,
    project_root: Path,
    output_dir: Path,
    no_write: bool = False,
    s111_review_path: Path = S111_REVIEW,
    s112_review_summary_path: Path = S112_REVIEW_SUMMARY,
    s113_execution_path: Path = S113_EXECUTION,
    s109_implementation_path: Path = S109_IMPLEMENTATION,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = _resolve_path(project_root, output_dir)
    _assert_strategy_namespace(output_dir)
    s111 = _load_json(_resolve_path(project_root, s111_review_path))
    s112 = _load_json(_resolve_path(project_root, s112_review_summary_path))
    s113 = _load_json(_resolve_path(project_root, s113_execution_path))
    s109 = _load_json(_resolve_path(project_root, s109_implementation_path))
    classification = _classify_strategy(s111=s111, s112=s112, s113=s113, s109=s109)
    phase_seconds = _mapping(_mapping(s111.get("interpretation")).get("phase_seconds"))
    payload = {
        "schema": "phase3b-signature-bucket-port-profile-cache-strategy/v0",
        "generated_at": _now(),
        "status": "completed" if classification != "manual_review_required" else "manual_review_required",
        "classification": classification,
        "project_root": str(project_root),
        "inputs": {
            "s109_implementation": str(_resolve_path(project_root, s109_implementation_path)),
            "s111_probe_review": str(_resolve_path(project_root, s111_review_path)),
            "s112_review_summary": str(_resolve_path(project_root, s112_review_summary_path)),
            "s113_probe_execution": str(_resolve_path(project_root, s113_execution_path)),
        },
        "evidence": {
            "s109_status": s109.get("status"),
            "s112_review_verdict": s112.get("review_verdict"),
            "s111_status": s111.get("status"),
            "s111_classification": _mapping(s111.get("interpretation")).get("classification"),
            "s113_status": s113.get("status"),
            "s113_classification": s113.get("classification"),
            "model_build_seconds": _float(s111.get("model_build_seconds")),
            "dominant_phase": _mapping(s111.get("interpretation")).get("dominant_phase"),
            "dominant_seconds": _float(_mapping(s111.get("interpretation")).get("dominant_seconds")),
            "port_profile_and_boundary_cache_seconds": _float(
                phase_seconds.get("port_profile_and_boundary_cache_initialization")
            ),
            "constructor_finalize_seconds": _float(phase_seconds.get("constructor_finalize")),
            "signature_bucket_seed_build_seconds": _float(phase_seconds.get("signature_bucket_seed_build")),
            "sensitive_path_clean": _mapping(s111.get("probe_safety")).get("sensitive_path_clean"),
            "checkpoint_written": s111.get("checkpoint_written"),
            "proof_source": s111.get("proof_source"),
        },
        "source_context_observation": {
            "target_method": "MasterPlacementModel._index_pools",
            "wrapping_phase": "port_profile_and_boundary_cache_initialization",
            "observed_call_site": (
                "MasterPlacementModel.__init__ records port_profile_and_boundary_cache_initialization "
                "around self._index_pools(); _build_signature_buckets() is recorded separately."
            ),
            "likely_internal_work": [
                "power pole cell and anchor index construction",
                "per-template/per-pose cell, port, front, local signature, and greedy blocking cache construction",
                "powered non-pole anchor/shape grouping",
                "power coverer/support bucket computation over candidate poles",
                "compact capacity signature storage",
                "exact precompute profile update",
            ],
        },
        "future_patch_spec_for_review": {
            "implementation_allowed_now": False,
            "review_required_before_authorization": True,
            "source_mutation_performed": False,
            "proposed_scope": (
                "default-off stats-only instrumentation to split MasterPlacementModel._index_pools "
                "inside the already-hot port_profile_and_boundary_cache_initialization phase"
            ),
            "proposed_env_gate": "EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION",
            "target_method": "MasterPlacementModel._index_pools",
            "publication_path": (
                "build_stats.exact_core_reuse.residual_overlay_instrumentation."
                "port_profile_cache_instrumentation"
            ),
            "candidate_subphases_to_measure": [
                "index_container_initialization",
                "power_pole_index_build",
                "per_template_pose_cache_build",
                "port_front_extraction",
                "local_signature_build",
                "powered_anchor_shape_grouping",
                "powered_support_coverer_build",
                "compact_capacity_signature_store",
                "exact_precompute_profile_update",
                "index_pools_unattributed_seconds",
            ],
            "candidate_totals_to_record": [
                "template_count",
                "pose_count",
                "powered_template_count",
                "power_pole_count",
                "pose_cells_scanned",
                "port_cells_scanned",
                "front_cells_scanned",
                "local_signature_cells_scanned",
                "anchor_shape_group_count",
                "support_coverer_scan_count",
                "compact_capacity_signature_item_count",
                "top_slow_templates_or_groups",
            ],
            "must_preserve": [
                "default_off_no_new_keys",
                "ModelProto_variables_constraints_and_text",
                "cache_contents_and_iteration_order",
                "search_strategy_and_hints",
                "scheduler_inputs",
                "proof_inputs",
                "checkpoint_files",
                "production_defaults",
                "from_exact_core_existing_semantics",
            ],
            "rejected_in_this_slice": [
                "do_not_optimize_index_pools_yet",
                "do_not_cache_reuse_or_skip_index_pools_yet",
                "do_not_execute_another_enabled_probe",
                "do_not_run_runtime_solve",
                "do_not_write_checkpoints_or_proof_artifacts",
            ],
        },
        "next_gate": {
            "status": "hold_for_port_profile_cache_external_review",
            "next_engineering_step": (
                "external_review_s114_before_requesting_authorization_for_any "
                "default_off_port_profile_cache_instrumentation_patch"
            ),
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
        atomic_write_json(output_dir / "signature_bucket_port_profile_cache_strategy.json", payload)
        (output_dir / "signature_bucket_port_profile_cache_strategy.md").write_text(
            _strategy_markdown(payload),
            encoding="utf-8",
        )
    return payload


def build_port_profile_cache_external_review_package(
    *,
    project_root: Path,
    output_dir: Path,
    run_id: str = DEFAULT_RUN_ID,
    inputs: Mapping[str, Path] | None = None,
    no_write: bool = False,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = _resolve_path(project_root, output_dir)
    _assert_package_namespace(output_dir)
    input_paths = {
        key: _resolve_path(project_root, value)
        for key, value in dict(inputs or PACKAGE_INPUTS).items()
    }
    before = build_sensitive_path_fingerprint(project_root)
    run_dir = output_dir / run_id
    staging_dir = run_dir / "staging"
    clean_extract_dir = run_dir / "clean_extract"
    zip_path = run_dir / f"{run_id}.zip"
    expanded_bundle_path = run_dir / f"{run_id}_expanded_review_bundle.md"
    manifest = _manifest(project_root=project_root, run_id=run_id, zip_path=zip_path, inputs=input_paths)
    validation: dict[str, Any] = {"validated": False, "reason": "no_write"}
    zip_sha256: str | None = None
    expanded_bundle_sha256: str | None = None
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
        expanded_bundle = _expanded_review_bundle_text(
            package_filename=zip_path.name,
            package_sha256=zip_sha256,
            request_text=request_text,
            manifest=manifest,
            inputs=input_paths,
        )
        expanded_bundle_path.write_text(expanded_bundle, encoding="utf-8")
        expanded_bundle_sha256 = _sha256(expanded_bundle_path)
        (run_dir / "expanded_review_bundle_sha256.txt").write_text(
            f"{expanded_bundle_sha256}  {expanded_bundle_path.name}\n",
            encoding="utf-8",
        )
    after = build_sensitive_path_fingerprint(project_root)
    sensitive_comparison = compare_sensitive_path_fingerprints(before, after)
    status = (
        "completed"
        if (no_write or validation.get("validated")) and not sensitive_comparison.get("changed")
        else "manual_review_required"
    )
    payload = {
        "schema": "phase3b-signature-bucket-port-profile-cache-external-review-package/v0",
        "generated_at": _now(),
        "status": status,
        "run_id": run_id,
        "project_root": str(project_root),
        "output_dir": str(output_dir),
        "run_dir": str(run_dir),
        "zip_path": str(zip_path),
        "zip_sha256": zip_sha256,
        "expanded_review_bundle_path": str(expanded_bundle_path),
        "expanded_review_bundle_sha256": expanded_bundle_sha256,
        "package_kind": "review_only_port_profile_cache_strategy",
        "probe_execution_enabled": False,
        "source_mutation_performed": False,
        "runtime_execution_performed": False,
        "checkpoint_written": False,
        "proof_source": False,
        "review_is_authorization": False,
        "authorization_required_next": True,
        "inputs": {key: str(path) for key, path in input_paths.items()},
        "manifest": manifest,
        "clean_extraction_validation": validation,
        "sensitive_path_comparison": sensitive_comparison,
        "next_gate": {
            "status": "upload_to_chatgpt_project_for_external_review",
            "blocked_actions": [
                "do_not_patch_source_before_review_pass_and_authorization",
                "do_not_execute_enabled_probe",
                "do_not_run_runtime_solve",
                "do_not_run_67x20_or_full_wave",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
            ],
        },
    }
    if not no_write:
        atomic_write_json(run_dir / "external_review_package_summary.json", payload)
        (run_dir / "external_review_package_summary.md").write_text(
            _package_markdown(payload),
            encoding="utf-8",
        )
    return payload


def _classify_strategy(*, s111: Mapping[str, Any], s112: Mapping[str, Any], s113: Mapping[str, Any], s109: Mapping[str, Any]) -> str:
    interpretation = _mapping(s111.get("interpretation"))
    safety = _mapping(s111.get("probe_safety"))
    clean = (
        s109.get("status") == "implemented_and_verified"
        and s112.get("review_verdict") == "pass"
        and s111.get("status") == "completed"
        and interpretation.get("classification") == "port_profile_and_boundary_cache_initialization_hotspot"
        and s113.get("status") == "completed"
        and s113.get("classification") == "port_profile_and_boundary_cache_initialization_hotspot"
        and safety.get("sensitive_path_clean") is True
        and s111.get("checkpoint_written") is False
        and s111.get("proof_source") is False
    )
    return "port_profile_boundary_cache_subphase_strategy_required" if clean else "manual_review_required"


def _review_request_text(package_filename: str, package_sha256: str) -> str:
    return "\n".join(
        [
            "# Review Request: Phase3B S114 Port/Profile Boundary-Cache Strategy",
            "",
            f"Uploaded package to review: `{package_filename}`",
            f"SHA256: `{package_sha256}`",
            "",
            "If this request is sent with an expanded Markdown text source, please inspect that text source as the primary readable package and use the zip filename/SHA above only as package identity/reference.",
            "",
            "This needs review first. review is not authorization. if review passes request user/project-owner authorization before implementing any source patch.",
            "",
            "Context: S113 executed exactly one reviewed and authorized `42x32` enabled no-solve model-shell subphase probe. S111 classified the result as `port_profile_and_boundary_cache_initialization_hotspot`: model build is about 13.07s, the dominant constructor subphase is about 5.57s, `constructor_finalize` is about 1.21s, and `signature_bucket_seed_build` is about 0.078s. Safety stayed clean: no solver runtime, no CP-SAT Solve, no `main.py`, no `ExactCampaign`, no checkpoint write, no proof source, no source/model mutation, and sensitive paths stayed unchanged.",
            "",
            "S114 observes that `MasterPlacementModel.__init__` records `port_profile_and_boundary_cache_initialization` around `self._index_pools()`, while `_build_signature_buckets()` is measured separately and is not hot. S114 therefore proposes a future default-off stats-only source patch, not implemented in this slice, to instrument only `MasterPlacementModel._index_pools()` under a new env gate such as `EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION`.",
            "",
            "The proposed future instrumentation would split `_index_pools()` into internal timing/totals such as power-pole index build, per-template/per-pose cache build, port-front extraction, local signature build, powered anchor/shape grouping, support-coverer computation, compact capacity signature storage, and exact precompute profile update. Disabled/unset behavior must create no new keys and must preserve ModelProto, variables, constraints, cache contents and iteration order, hints, search strategy, scheduler/proof/checkpoint paths, runtime behavior, and production defaults.",
            "",
            "Please answer these gate questions:",
            "",
            "1. Is S114's classification of `port_profile_boundary_cache_subphase_strategy_required` valid after S113?",
            "2. Is the proposed future default-off stats-only instrumentation scope sufficiently narrow around `MasterPlacementModel._index_pools()`?",
            "3. Is `EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION` an appropriate separate env gate, or should this be tied to existing model-shell instrumentation?",
            "4. Are the proposed `_index_pools()` internal subphases and totals sufficient to explain the 5.57s hotspot before any optimization is attempted?",
            "5. Are there any proof/checkpoint/runtime/scheduler/production-default or source-behavior risks in this strategy/package?",
            "6. If safe, state only that this default-off port/profile cache instrumentation is safe to request user/project-owner authorization; do not grant authorization.",
            "",
            "Boundaries: do not authorize runtime solve, another enabled `42x32` probe, `67x20`, full-wave/final `168h`, canonical checkpoint write/import/backfill, proof/preflight/release/viewer/frontdoor mutation, production default changes, or optimization/source behavior changes beyond the reviewed default-off stats-only instrumentation.",
            "",
        ]
    )


def _strategy_markdown(payload: Mapping[str, Any]) -> str:
    evidence = _mapping(payload.get("evidence"))
    return "\n".join(
        [
            "# Phase3B S114 Port/Profile Boundary-Cache Strategy",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Classification: `{payload.get('classification')}`",
            f"- Model build seconds: `{evidence.get('model_build_seconds')}`",
            f"- Dominant phase: `{evidence.get('dominant_phase')}`",
            f"- Dominant seconds: `{evidence.get('dominant_seconds')}`",
            f"- Port/profile boundary-cache seconds: `{evidence.get('port_profile_and_boundary_cache_seconds')}`",
            "- Source mutation performed: `false`",
            "- Probe execution enabled: `false`",
            "",
        ]
    )


def _package_markdown(payload: Mapping[str, Any]) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    return "\n".join(
        [
            "# Phase3B S115 Port/Profile Boundary-Cache External Review Package",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Zip: `{Path(str(payload.get('zip_path'))).name}`",
            f"- Zip SHA256: `{payload.get('zip_sha256')}`",
            f"- Expanded bundle SHA256: `{payload.get('expanded_review_bundle_sha256')}`",
            f"- Clean extraction validated: `{validation.get('validated')}`",
            "- Probe execution enabled: `false`",
            "- Source mutation performed: `false`",
            "- Runtime execution performed: `false`",
            "- Checkpoint written: `false`",
            "- Proof source: `false`",
            "",
        ]
    )


def _manifest(*, project_root: Path, run_id: str, zip_path: Path, inputs: Mapping[str, Path]) -> dict[str, Any]:
    entries = []
    for key, path in sorted(inputs.items()):
        exists = path.exists()
        entries.append(
            {
                "key": key,
                "source_path": str(path),
                "filename": path.name,
                "exists": exists,
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
    with zipfile.ZipFile(zip_path) as zf:
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


def _expanded_review_bundle_text(
    *,
    package_filename: str,
    package_sha256: str,
    request_text: str,
    manifest: Mapping[str, Any],
    inputs: Mapping[str, Path],
) -> str:
    parts = [
        "# Expanded Review Bundle: Phase3B S114 Port/Profile Boundary-Cache Strategy",
        "",
        f"- Original zip filename: `{package_filename}`",
        f"- Original zip SHA256: `{package_sha256}`",
        "",
        "## Review Request",
        "",
        request_text,
        "",
        "## Manifest",
        "",
        "```json",
        json.dumps(manifest, indent=2, ensure_ascii=False),
        "```",
        "",
    ]
    for key, path in sorted(inputs.items()):
        parts.extend([f"## Evidence: {key}", "", f"- Source path: `{path}`", ""])
        if path.exists() and path.is_file():
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            suffix = path.suffix.lower().lstrip(".") or "text"
            if suffix == "py":
                suffix = "python"
            elif suffix == "md":
                suffix = "markdown"
            elif suffix == "json":
                suffix = "json"
            parts.extend([f"```{suffix}", text, "```", ""])
        else:
            parts.extend(["`missing`", ""])
    return "\n".join(parts)


def _assert_strategy_namespace(output_dir: Path) -> None:
    normalized = str(output_dir).replace("\\", "/")
    if "114_signature_bucket_port_profile_cache_strategy" not in normalized:
        raise ValueError("S114 strategy namespace required")


def _assert_package_namespace(output_dir: Path) -> None:
    normalized = str(output_dir).replace("\\", "/")
    if "115_signature_bucket_port_profile_cache_external_review_package" not in normalized:
        raise ValueError("S115 package namespace required")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
