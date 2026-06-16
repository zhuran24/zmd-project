from __future__ import annotations

import argparse
import hashlib
import json
import os
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
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "88_signature_bucket_payload_footprint_probe_external_review_package"
DEFAULT_RUN_ID = "s86_s87_payload_footprint_probe_review_001"

DEFAULT_INPUTS = {
    "s82_execution": ARTIFACT_ROOT
    / "82_signature_bucket_template_footprint_support_gap_probe_execution"
    / "signature_bucket_template_footprint_support_gap_probe_execution.json",
    "s80_review": ARTIFACT_ROOT
    / "80_signature_bucket_template_footprint_support_gap_probe_review"
    / "signature_bucket_template_footprint_support_gap_probe_review.json",
    "s83_strategy": ARTIFACT_ROOT
    / "83_signature_bucket_payload_footprint_stability_strategy"
    / "signature_bucket_payload_footprint_stability_strategy.json",
    "s84_review_summary": ARTIFACT_ROOT
    / "84_signature_bucket_payload_footprint_stability_external_review_package"
    / "s83_payload_footprint_stability_review_001"
    / "external_review_reply_summary.json",
    "s84_review_raw": ARTIFACT_ROOT
    / "84_signature_bucket_payload_footprint_stability_external_review_package"
    / "s83_payload_footprint_stability_review_001"
    / "external_review_reply_raw.md",
    "s85_implementation": ARTIFACT_ROOT
    / "85_signature_bucket_payload_footprint_stability_implementation"
    / "s85_signature_bucket_payload_footprint_stability_implementation.json",
    "s86_readiness": ARTIFACT_ROOT
    / "86_signature_bucket_payload_footprint_probe_readiness"
    / "signature_bucket_payload_footprint_probe_readiness.json",
    "s86_future_command": ARTIFACT_ROOT
    / "86_signature_bucket_payload_footprint_probe_readiness"
    / "future_command_template.json",
    "agents": WORKSPACE_ROOT / "AGENTS.md",
    "exact_coordinate_master_source": PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py",
    "test_master": PROJECT_ROOT / "src" / "tests" / "test_master.py",
    "exact_contract_tests": PROJECT_ROOT / "src" / "tests" / "test_exact_contract.py",
    "s86_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "payload_footprint" / "build_probe_readiness.py",
    "s87_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "payload_footprint" / "build_probe_review.py",
    "s88_package_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "payload_footprint" / "build_probe_external_review_package.py",
    "s86_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_payload_footprint_probe_readiness.py",
    "s87_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_payload_footprint_probe_review.py",
    "s88_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_payload_footprint_probe_external_review_package.py",
}

REVIEW_WORDING_REQUIREMENTS = [
    "needs review first",
    "review is not authorization",
    "if review passes request user/project-owner authorization",
]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    package = build_signature_bucket_payload_footprint_probe_external_review_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket payload-footprint probe external review package")
    print(f"status={package['status']}")
    print(f"zip_path={_display_path(PROJECT_ROOT, Path(package['zip_path']))}")
    print(f"zip_sha256={package.get('zip_sha256')}")
    print(f"clean_extraction_validated={package['clean_extraction_validation']['validated']}")
    return 0 if package["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a clean-extraction-validated external review package for S86/S87 "
            "payload-footprint probe readiness and review tooling."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_payload_footprint_probe_external_review_package(
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
        for key, value in dict(inputs or DEFAULT_INPUTS).items()
    }
    before = build_sensitive_path_fingerprint(project_root)
    run_dir = output_dir / str(run_id)
    staging_dir = run_dir / "staging"
    clean_extract_dir = run_dir / "clean_extract"
    zip_path = run_dir / f"{run_id}.zip"
    manifest = _manifest(
        project_root=project_root,
        run_id=run_id,
        run_dir=run_dir,
        zip_path=zip_path,
        inputs=input_paths,
    )
    validation: dict[str, Any] = {"validated": False, "reason": "no_write"}
    zip_sha256: str | None = None
    final_request_text = _review_request_text(
        input_paths,
        package_filename=zip_path.name,
        package_sha256="not built in no-write mode",
    )
    if not no_write:
        if run_dir.exists():
            shutil.rmtree(run_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)
        _write_staging_files(staging_dir=staging_dir, manifest=manifest, inputs=input_paths)
        _write_zip(staging_dir, zip_path)
        zip_sha256 = _sha256(zip_path)
        manifest["zip_sha256"] = zip_sha256
        final_request_text = _review_request_text(
            input_paths,
            package_filename=zip_path.name,
            package_sha256=zip_sha256,
        )
        atomic_write_json(run_dir / "manifest.json", manifest)
        (run_dir / "review_request.md").write_text(final_request_text, encoding="utf-8")
        (run_dir / "zip_sha256.txt").write_text(
            f"{zip_sha256}  {zip_path.name}\n",
            encoding="utf-8",
        )
        validation = _validate_clean_extraction(
            zip_path=zip_path,
            extract_dir=clean_extract_dir,
            expected_zip_sha256=zip_sha256,
            final_request_text=final_request_text,
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
        "schema": "phase3b-signature-bucket-payload-footprint-probe-external-review-package/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "package_kind": "external_review_payload_footprint_probe_readiness_and_review_tooling_package",
        "project_root": str(project_root),
        "run_id": str(run_id),
        "run_dir": str(run_dir),
        "zip_path": str(zip_path),
        "zip_sha256": zip_sha256,
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
        "probe_execution_enabled": False,
        "review_required_before_authorization": True,
        "external_review_is_authorization": False,
        "final_review_request_path": str(run_dir / "review_request.md"),
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


def render_package_markdown(payload: Mapping[str, Any]) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    return "\n".join(
        [
            "# Phase3B S88 Payload-Footprint Probe External Review Package",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Zip: `{payload.get('zip_path')}`",
            f"- SHA256: `{payload.get('zip_sha256')}`",
            f"- Clean extraction validated: `{validation.get('validated')}`",
            "- Source mutation performed: `false`",
            "- Probe execution enabled: `false`",
            "- CpSolver.Solve called: `false`",
            "- Proof source: `false`",
            "- Checkpoint written: `false`",
            "- Review required before authorization: `true`",
            "",
            "This package asks external review whether S86/S87 readiness and review tooling are safe to request authorization for exactly one future enabled `42x32` no-solve payload-footprint probe. It is not authorization.",
            "",
        ]
    )


def _review_request_text(
    inputs: Mapping[str, Path],
    *,
    package_filename: str,
    package_sha256: str,
) -> str:
    return "\n".join(
        [
            "# Review Request: Phase3B S86/S87 Payload-Footprint Probe Readiness",
            "",
            "Uploaded package to review:",
            "",
            f"- Package filename: `{package_filename}`",
            f"- Package SHA256: `{package_sha256}`",
            "",
            "Status: needs review first. This review is not authorization. If review passes request user/project-owner authorization before executing the single future no-solve probe.",
            "",
            "Gate marker for automated checks: if review passes request user/project-owner authorization.",
            "",
            "Context: S85 implemented default-off payload-footprint stability support under `EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT`. S86 prepares exactly one future enabled `42x32` no-solve probe with six env gates enabled. S87 is fail-closed review tooling that will classify whether the future probe shows payload-footprint stability was effective, unused, still dominated by unstable bounds, still mandatory-scan hot, inconclusive, missing instrumentation, or safety-disqualified.",
            "",
            "Please review these questions:",
            "",
            "1. Is the S86 future command sufficiently narrow: exactly one `42x32` no-solve overlay timing probe with fixed run id and the six required env gates?",
            "2. Are the S86 exact command-vector and forbidden-token guards strict enough to prevent runtime solve, checkpoint/proof/release/viewer/frontdoor drift, duplicate flags, or non-`42x32` targets?",
            "3. Is the S87 fail-closed schema conservative enough for strict sensitive-path schema, hard-boundary flags, run-id mismatch, missing timing, missing support-gap totals, missing payload-footprint totals, and missing support-gap visibility?",
            "4. Are the S87 result classifications appropriate: payload-footprint stability effective, not used, unstable bounds still dominate, mandatory scan still hot, inconclusive, support-gap instrumentation missing, or safety-disqualified?",
            "5. If review passes, is it safe to request user/project-owner authorization for exactly one future enabled `42x32` no-solve payload-footprint probe, still with no runtime solve, no canonical checkpoints, no proof/preflight/release/viewer/frontdoor mutation, and no production default change?",
            "",
            "If there are no blockers, please state only that this single future enabled no-solve payload-footprint probe scope is safe to request user/project-owner authorization; do not treat review approval as authorization.",
            "",
            "Hard boundaries: review-only; no probe execution, no runtime solve, no final `168h`, no `67x20`, no full-wave, no canonical checkpoint writes/imports/backfills, no proof/preflight/release/viewer/frontdoor mutation, no runtime elimination, no production default changes, and no source patch.",
            "",
            "Included local inputs:",
            "",
            *[f"- `{key}`: `{path}`" for key, path in sorted(inputs.items())],
            "",
        ]
    )


def _manifest(
    *,
    project_root: Path,
    run_id: str,
    run_dir: Path,
    zip_path: Path,
    inputs: Mapping[str, Path],
) -> dict[str, Any]:
    return {
        "schema": "phase3b-signature-bucket-payload-footprint-probe-external-review-package-manifest/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "run_id": str(run_id),
        "zip_path": str(zip_path),
        "zip_sha256": None,
        "proof_source": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
        "probe_executed": False,
        "review_required_before_authorization": True,
        "external_review_is_authorization": False,
        "package_contents": _required_entries(),
        "inputs": {
            key: {
                "absolute_path": str(path),
                "exists": path.exists(),
                "sha256": _sha256(path) if path.exists() and path.is_file() else None,
                "package_path": _package_path_for_input(key).as_posix(),
            }
            for key, path in sorted(inputs.items())
        },
        "source_project_root": str(project_root),
        "run_dir": str(run_dir),
    }


def _write_staging_files(
    *,
    staging_dir: Path,
    manifest: Mapping[str, Any],
    inputs: Mapping[str, Path],
) -> None:
    (staging_dir / "README.md").write_text(
        (
            "This package is for Phase3B / Endfield external review of S86/S87 "
            "payload-footprint probe readiness and review tooling. It needs review first; "
            "review is not authorization; if review passes request user/project-owner "
            "authorization. It is not proof evidence and does not execute a probe.\n"
        ),
        encoding="utf-8",
    )
    (staging_dir / "review_request.md").write_text(
        _review_request_text(
            inputs,
            package_filename="filled after zip",
            package_sha256="filled after zip",
        ),
        encoding="utf-8",
    )
    atomic_write_json(staging_dir / "manifest.json", dict(manifest))
    for key, source_path in sorted(inputs.items()):
        package_path = staging_dir / _package_path_for_input(key)
        package_path.parent.mkdir(parents=True, exist_ok=True)
        if not source_path.exists():
            raise FileNotFoundError(f"required review package input is missing: {key}: {source_path}")
        if key == "agents":
            package_path.write_text(_agents_gate_excerpt(source_path), encoding="utf-8")
        else:
            shutil.copy2(source_path, package_path)


def _validate_clean_extraction(
    *,
    zip_path: Path,
    extract_dir: Path,
    expected_zip_sha256: str,
    final_request_text: str,
) -> dict[str, Any]:
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extract_dir)
        names = sorted(archive.namelist())
    missing = [name for name in _required_entries() if not (extract_dir / name).is_file()]
    manifest = _load_json(extract_dir / "manifest.json")
    s84 = _load_json(extract_dir / "evidence/s84_external_review_reply_summary.json")
    s85 = _load_json(extract_dir / "evidence/s85_signature_bucket_payload_footprint_stability_implementation.json")
    s86 = _load_json(extract_dir / "evidence/s86_signature_bucket_payload_footprint_probe_readiness.json")
    request_text = (extract_dir / "review_request.md").read_text(encoding="utf-8")
    s87_builder_text = (
        extract_dir
        / "code_context/scripts/phase3b/checkpoint_free/signature_bucket/payload_footprint/build_probe_review.py"
    ).read_text(encoding="utf-8")
    semantic_checks = {
        "zip_sha256_matches_expected": _sha256(zip_path) == expected_zip_sha256,
        "manifest_review_required_true": manifest.get("review_required_before_authorization") is True,
        "manifest_external_review_not_authorization": manifest.get("external_review_is_authorization") is False,
        "manifest_probe_not_executed": manifest.get("probe_executed") is False,
        "s84_review_passed_not_authorization": s84.get("review_verdict") == "pass"
        and s84.get("review_is_authorization") is False,
        "s85_implemented_and_verified": s85.get("status") == "implemented_and_verified",
        "s86_ready": _mapping(s86.get("readiness")).get("classification")
        == "ready_for_payload_footprint_probe_review",
        "s86_probe_execution_disabled": s86.get("probe_execution_enabled") is False,
        "s87_fail_closed_classes_present": "payload_footprint_probe_inconclusive" in s87_builder_text
        and "safety_disqualified" in s87_builder_text
        and "support_gap_instrumentation_missing" in s87_builder_text,
        "request_has_review_words": all(text in request_text for text in REVIEW_WORDING_REQUIREMENTS),
        "final_request_names_package": str(zip_path.name) in final_request_text,
        "final_request_has_zip_sha": expected_zip_sha256 in final_request_text,
        "final_request_has_review_words": all(text in final_request_text for text in REVIEW_WORDING_REQUIREMENTS),
    }
    return {
        "validated": not missing and all(semantic_checks.values()),
        "zip_path": str(zip_path),
        "zip_sha256": expected_zip_sha256,
        "extract_dir": str(extract_dir),
        "entry_count": len(names),
        "missing_required_entries": missing,
        "semantic_checks": semantic_checks,
    }


def _write_zip(staging_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging_dir.rglob("*")):
            if path.is_file():
                archive.write(
                    _filesystem_path_for_zip(path),
                    path.relative_to(staging_dir).as_posix(),
                )


def _filesystem_path_for_zip(path: Path) -> str:
    absolute = os.path.abspath(os.fspath(path))
    if os.name != "nt" or absolute.startswith("\\\\?\\"):
        return absolute
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute.lstrip("\\")
    return "\\\\?\\" + absolute


def _required_entries() -> list[str]:
    return [
        "README.md",
        "review_request.md",
        "manifest.json",
        "evidence/s82_signature_bucket_template_footprint_support_gap_probe_execution.json",
        "evidence/s80_signature_bucket_template_footprint_support_gap_probe_review.json",
        "evidence/s83_signature_bucket_payload_footprint_stability_strategy.json",
        "evidence/s84_external_review_reply_summary.json",
        "evidence/s84_external_review_reply_raw.md",
        "evidence/s85_signature_bucket_payload_footprint_stability_implementation.json",
        "evidence/s86_signature_bucket_payload_footprint_probe_readiness.json",
        "evidence/s86_future_command_template.json",
        "coordination/agents_s82_s86_gate_excerpt.md",
        "source_context/src/models/exact_coordinate_master.py",
        "test_context/src/tests/test_master.py",
        "test_context/src/tests/test_exact_contract.py",
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/payload_footprint/build_probe_readiness.py",
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/payload_footprint/build_probe_review.py",
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/payload_footprint/build_probe_external_review_package.py",
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/payload_footprint/test_probe_readiness.py",
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/payload_footprint/test_probe_review.py",
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/payload_footprint/test_probe_external_review_package.py",
    ]


def _package_path_for_input(key: str) -> Path:
    mapping = {
        "s82_execution": Path("evidence/s82_signature_bucket_template_footprint_support_gap_probe_execution.json"),
        "s80_review": Path("evidence/s80_signature_bucket_template_footprint_support_gap_probe_review.json"),
        "s83_strategy": Path("evidence/s83_signature_bucket_payload_footprint_stability_strategy.json"),
        "s84_review_summary": Path("evidence/s84_external_review_reply_summary.json"),
        "s84_review_raw": Path("evidence/s84_external_review_reply_raw.md"),
        "s85_implementation": Path("evidence/s85_signature_bucket_payload_footprint_stability_implementation.json"),
        "s86_readiness": Path("evidence/s86_signature_bucket_payload_footprint_probe_readiness.json"),
        "s86_future_command": Path("evidence/s86_future_command_template.json"),
        "agents": Path("coordination/agents_s82_s86_gate_excerpt.md"),
        "exact_coordinate_master_source": Path("source_context/src/models/exact_coordinate_master.py"),
        "test_master": Path("test_context/src/tests/test_master.py"),
        "exact_contract_tests": Path("test_context/src/tests/test_exact_contract.py"),
        "s86_builder": Path(
            "code_context/scripts/phase3b/checkpoint_free/signature_bucket/payload_footprint/build_probe_readiness.py"
        ),
        "s87_builder": Path(
            "code_context/scripts/phase3b/checkpoint_free/signature_bucket/payload_footprint/build_probe_review.py"
        ),
        "s88_package_builder": Path(
            "code_context/scripts/phase3b/checkpoint_free/signature_bucket/payload_footprint/build_probe_external_review_package.py"
        ),
        "s86_tests": Path(
            "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/payload_footprint/test_probe_readiness.py"
        ),
        "s87_tests": Path(
            "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/payload_footprint/test_probe_review.py"
        ),
        "s88_tests": Path(
            "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/payload_footprint/test_probe_external_review_package.py"
        ),
    }
    return mapping[key]


def _agents_gate_excerpt(path: Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    markers = [
        "GPT Project Review Standing Authorization",
        "Current S81/S82 support-gap probe review and execution state",
        "Current S83/S84 payload-footprint stability review state",
        "Current S84 external review result and S85 authorization gate",
        "Current S85 payload-footprint stability patch state",
        "Current S86/S87 payload-footprint probe readiness state",
    ]
    lines = [line for line in text.splitlines() if any(marker in line for marker in markers)]
    if not lines:
        raise ValueError(f"Could not find S82-S86/review gate excerpt in {path}")
    return "\n".join(["# AGENTS Gate Excerpt", "", *lines, ""])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_package_namespace(path: Path) -> None:
    normalized = str(path).replace("\\", "/").lower()
    if (
        "phase3b_local_13900ks_tuning_20260430" not in normalized
        or "88_signature_bucket_payload_footprint_probe_external_review_package"
        not in normalized
    ):
        raise ValueError(f"Refusing to write outside S88 external review package namespace: {path}")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _resolve_path(root: Path, path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else root / path


def _display_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
