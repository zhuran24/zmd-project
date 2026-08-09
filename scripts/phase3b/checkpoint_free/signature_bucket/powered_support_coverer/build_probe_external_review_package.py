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
S127_DIR = ARTIFACT_ROOT / "127_signature_bucket_powered_support_coverer_probe_external_review_package"
DEFAULT_RUN_ID = "s125_s126_powered_support_coverer_probe_review_001"

PACKAGE_INPUTS = {
    "s120_probe_execution": ARTIFACT_ROOT
    / "120_signature_bucket_port_profile_cache_probe_execution"
    / "signature_bucket_port_profile_cache_probe_execution.json",
    "s118_probe_review": ARTIFACT_ROOT
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
    "s125_readiness": ARTIFACT_ROOT
    / "125_signature_bucket_powered_support_coverer_probe_readiness"
    / "signature_bucket_powered_support_coverer_probe_readiness.json",
    "s125_future_command": ARTIFACT_ROOT
    / "125_signature_bucket_powered_support_coverer_probe_readiness"
    / "future_command_template.json",
    "agents_gate": WORKSPACE_ROOT / "AGENTS.md",
    "master_model_source": PROJECT_ROOT / "src" / "models" / "master_model.py",
    "exact_coordinate_master_source": PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py",
    "test_master": PROJECT_ROOT / "src" / "tests" / "test_master.py",
    "exact_contract_tests": PROJECT_ROOT / "src" / "tests" / "test_exact_contract.py",
    "s125_readiness_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "powered_support_coverer" / "build_probe_readiness.py",
    "s126_review_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "powered_support_coverer" / "build_probe_review.py",
    "s127_package_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "powered_support_coverer" / "build_probe_external_review_package.py",
    "s125_readiness_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_probe_readiness.py",
    "s126_review_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_probe_review.py",
    "s127_package_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_probe_external_review_package.py",
}

REVIEW_WORDING_REQUIREMENTS = (
    "needs review first",
    "review is not authorization",
    "if review passes request user/project-owner authorization",
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    package = build_powered_support_coverer_probe_external_review_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket powered support-coverer probe review package")
    print(f"package_status={package['status']}")
    print(f"zip_path={_display_path(PROJECT_ROOT, Path(package['zip_path']))}")
    print(f"zip_sha256={package.get('zip_sha256')}")
    print(f"expanded_bundle={_display_path(PROJECT_ROOT, Path(package['expanded_review_bundle_path']))}")
    print(f"expanded_bundle_sha256={package.get('expanded_review_bundle_sha256')}")
    print(f"clean_extraction_validated={package['clean_extraction_validation']['validated']}")
    return 0 if package["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build S127 external review package for S125/S126 one-shot powered "
            "support-coverer no-solve probe readiness and review tooling."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=S127_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_powered_support_coverer_probe_external_review_package(
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
        "schema": "phase3b-signature-bucket-powered-support-coverer-probe-external-review-package/v0",
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
        "package_kind": "review_only_probe_readiness_and_review_tooling",
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
                "do_not_execute_enabled_probe_before_review_pass",
                "do_not_run_runtime_solve",
                "do_not_run_67x20_or_full_wave",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
                "do_not_patch_source",
            ],
        },
    }
    if not no_write:
        atomic_write_json(run_dir / "external_review_package_summary.json", payload)
        (run_dir / "external_review_package_summary.md").write_text(
            _summary_markdown(payload),
            encoding="utf-8",
        )
    return payload


def _review_request_text(package_filename: str, package_sha256: str) -> str:
    return "\n".join(
        [
            "# Review Request: Phase3B S125/S126 Powered Support-Coverer Probe Readiness",
            "",
            f"Uploaded package to review: `{package_filename}`",
            f"SHA256: `{package_sha256}`",
            "",
            "If this request is sent with an expanded Markdown text source, please inspect that text source as the primary readable package and use the zip filename/SHA above only as package identity/reference.",
            "",
            "This needs review first. review is not authorization. if review passes request user/project-owner authorization before executing the future probe.",
            "",
            "Context: S124 implemented default-off, stats-only powered support-coverer detail instrumentation under `EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION`. S125 is a plan-only readiness artifact for exactly one future enabled `42x32` no-solve probe, and S126 is fail-closed review tooling for the future probe output.",
            "",
            "Future command under review:",
            "",
            "`python scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py --execute-no-solve --candidate-key 42x32 --run-id local_hotspot_42x32_signature_bucket_powered_support_coverer_inst_no_solve_001`",
            "",
            "Future environment gates under review:",
            "",
            "- `EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION=1`",
            "- `EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING=1`",
            "- `EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION=1`",
            "- `EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT=1`",
            "- `EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION=1`",
            "- `EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT=1`",
            "- `EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION=1`",
            "- `EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION=1`",
            "- `EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION=1`",
            "- `EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION=1`",
            "",
            "Please answer these gate questions:",
            "",
            "1. Is S125 sufficiently narrow and fail-closed for a single future `42x32 --execute-no-solve` powered support-coverer probe?",
            "2. Does S125 correctly keep `probe_execution_enabled=false` and require review/authorization before execution?",
            "3. Is S126 strict enough on sensitive-path schema, hard-boundary flags, run id, candidate key, no-solve status, and missing powered support-coverer fields?",
            "4. Are the S126 classifications useful for deciding the next review-first `_index_pools()` hotspot strategy?",
            "5. Are there any checkpoint, proof, scheduler, production-default, runtime, or source-mutation risks in this plan-only package?",
            "6. If safe, state only that the single future no-solve probe is safe to request user/project-owner authorization; do not grant authorization.",
            "",
            "Boundaries: do not authorize runtime solve, `67x20`, full-wave/final `168h`, canonical checkpoint write/import/backfill, proof/preflight/release/viewer/frontdoor mutation, production default changes, or source patches.",
            "",
        ]
    )


def _summary_markdown(payload: Mapping[str, Any]) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    return "\n".join(
        [
            "# Phase3B S127 Powered Support-Coverer Probe External Review Package",
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
        "# Expanded Review Bundle: Phase3B S125/S126 Powered Support-Coverer Probe",
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


def _assert_package_namespace(output_dir: Path) -> None:
    normalized = str(output_dir).replace("\\", "/")
    if "127_signature_bucket_powered_support_coverer_probe_external_review_package" not in normalized:
        raise ValueError("S127 package namespace required")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


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
