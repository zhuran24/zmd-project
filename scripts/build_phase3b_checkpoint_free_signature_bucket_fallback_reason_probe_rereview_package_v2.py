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
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "67_signature_bucket_fallback_reason_probe_rereview_package_v2"
DEFAULT_RUN_ID = "s63_s64_fallback_reason_probe_rereview_002"

DEFAULT_INPUTS = {
    "s65_failed_review_raw": ARTIFACT_ROOT
    / "65_signature_bucket_fallback_reason_probe_external_review_package"
    / "signature_bucket_fallback_reason_probe_external_review_package_001"
    / "external_review_reply_raw.md",
    "s65_review_summary": ARTIFACT_ROOT
    / "65_signature_bucket_fallback_reason_probe_external_review_package"
    / "signature_bucket_fallback_reason_probe_external_review_package_001"
    / "external_review_reply_summary.json",
    "s65_package_summary": ARTIFACT_ROOT
    / "65_signature_bucket_fallback_reason_probe_external_review_package"
    / "signature_bucket_fallback_reason_probe_external_review_package_001"
    / "external_review_package_summary.json",
    "s65_package_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_external_review_package.py",
    "s65_package_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_external_review_package.py",
    "s66_implementation": ARTIFACT_ROOT
    / "66_s64_fallback_reason_probe_review_hardening_implementation"
    / "s66_s64_fallback_reason_probe_review_hardening_implementation.json",
    "s63_readiness": ARTIFACT_ROOT
    / "63_signature_bucket_fallback_reason_probe_readiness"
    / "signature_bucket_fallback_reason_probe_readiness.json",
    "s63_future_command": ARTIFACT_ROOT
    / "63_signature_bucket_fallback_reason_probe_readiness"
    / "future_command_template.json",
    "agents": WORKSPACE_ROOT / "AGENTS.md",
    "s63_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_readiness.py",
    "s64_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_review.py",
    "s66_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_s64_fail_closed_hardening.py",
    "s67_package_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_rereview_package_v2.py",
    "s63_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_readiness.py",
    "s64_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_review.py",
    "s67_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_rereview_package_v2.py",
    "exact_contract_tests": PROJECT_ROOT / "src" / "tests" / "test_exact_contract.py",
}

REVIEW_WORDING_REQUIREMENTS = [
    "needs review first",
    "review is not authorization",
    "if review passes request user/project-owner authorization",
]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    package = build_signature_bucket_fallback_reason_probe_rereview_package_v2(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket fallback-reason probe re-review package v2")
    print(f"status={package['status']}")
    print(f"zip_path={_display_path(PROJECT_ROOT, Path(package['zip_path']))}")
    print(f"zip_sha256={package.get('zip_sha256')}")
    print(f"clean_extraction_validated={package['clean_extraction_validation']['validated']}")
    return 0 if package["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the S67 external re-review package for S64 fail-closed hardening."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_fallback_reason_probe_rereview_package_v2(
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
        (run_dir / "zip_sha256.txt").write_text(f"{zip_sha256}  {zip_path.name}\n", encoding="utf-8")
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
        "schema": "phase3b-signature-bucket-fallback-reason-probe-rereview-package-v2/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "package_kind": "external_rereview_v2_s64_fail_closed_hardening_package",
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
            render_package_markdown(payload), encoding="utf-8"
        )
        atomic_write_json(run_dir / "sensitive_path_before.json", before)
        atomic_write_json(run_dir / "sensitive_path_after.json", after)
        atomic_write_json(run_dir / "sensitive_path_comparison.json", sensitive_comparison)
    return payload


def render_package_markdown(payload: Mapping[str, Any]) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    return "\n".join(
        [
            "# Phase3B S67 Fallback-Reason Probe Re-review Package v2",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Zip: `{payload.get('zip_path')}`",
            f"- SHA256: `{payload.get('zip_sha256')}`",
            f"- Clean extraction validated: `{validation.get('validated')}`",
            "- Probe executed in this slice: `false`",
            "- Review required before authorization: `true`",
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
            "# Review Request: Phase3B S67 S64 Fail-Closed Hardening Re-review",
            "",
            f"- Package filename: `{package_filename}`",
            f"- Package SHA256: `{package_sha256}`",
            "",
            "Status: needs review first. This review is not authorization. If review passes request user/project-owner authorization before executing the single enabled `42x32` no-solve fallback-reason probe.",
            "",
            "Gate marker: if review passes request user/project-owner authorization.",
            "",
            "S65 did not pass because S64 did not require the full sensitive-path comparison schema and because `fallback_reason_instrumentation_missing` used success-like status/CLI semantics. S66 hardens both cases and adds focused adversarial tests. This package is review-only and does not execute the future probe.",
            "",
            "Please answer:",
            "",
            "1. Does S66 fully resolve the S65 blockers?",
            "2. Does S64 now require strict clean `sensitive_path_comparison`: schema `phase3b-sensitive-path-fingerprint-comparison/v0`, `changed=false`, `changed_paths=[]`, and `changed_entries=[]`?",
            "3. Does S64 now classify any missing/wrong schema, missing/non-list/nonempty `changed_paths`, or missing/non-list/nonempty `changed_entries` as `safety_disqualified`?",
            "4. Does `fallback_reason_instrumentation_missing` now return non-success status and nonzero CLI exit, preventing automation from treating missing visibility as a passed probe?",
            "5. Are the tests sufficient to request user/project-owner authorization for exactly one future enabled `42x32` no-solve fallback-reason probe?",
            "",
            "Hard boundaries: review-only; do not authorize runtime solve, final 168h, canonical checkpoint writes/imports/backfills, proof/preflight/release/viewer/frontdoor mutation, runtime elimination, production default changes, `67x20`, full-wave, source patches, or direct probe execution. A passing review is not authorization.",
            "",
            "Included inputs:",
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
        "schema": "phase3b-signature-bucket-fallback-reason-probe-rereview-package-v2-manifest/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "run_id": str(run_id),
        "zip_path": str(zip_path),
        "zip_sha256": None,
        "proof_source": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
        "probe_execution_performed": False,
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
        "S67 external re-review package for S64 fail-closed hardening. "
        "It needs review first; review is not authorization; if review passes "
        "request user/project-owner authorization before executing the single future no-solve probe.\n",
        encoding="utf-8",
    )
    (staging_dir / "review_request.md").write_text(
        _review_request_text(inputs, package_filename="filled after zip", package_sha256="filled after zip"),
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
    s65_summary = _load_json(extract_dir / "evidence/s65_external_review_reply_summary.json")
    s66 = _load_json(extract_dir / "evidence/s66_s64_fallback_reason_probe_review_hardening_implementation.json")
    request_text = (extract_dir / "review_request.md").read_text(encoding="utf-8")
    s65_raw = (extract_dir / "evidence/s65_failed_review_reply_raw.md").read_text(encoding="utf-8")
    semantic_checks = {
        "zip_sha256_matches_expected": _sha256(zip_path) == expected_zip_sha256,
        "manifest_review_required_true": manifest.get("review_required_before_authorization") is True,
        "manifest_external_review_not_authorization": manifest.get("external_review_is_authorization") is False,
        "manifest_probe_not_executed": manifest.get("probe_execution_performed") is False,
        "s65_failed_review_captured": (
            s65_summary.get("review_verdict") == "fail_do_not_request_authorization_yet"
            and ("I do not pass" in s65_raw or "does not pass" in s65_raw)
        ),
        "s66_hardening_verified": s66.get("status") == "implemented_and_verified",
        "s66_probe_not_executed": s66.get("probe_execution_performed") is False,
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


def _required_entries() -> list[str]:
    return [
        "README.md",
        "review_request.md",
        "manifest.json",
        "evidence/s65_failed_review_reply_raw.md",
        "evidence/s65_external_review_reply_summary.json",
        "evidence/s65_external_review_package_summary.json",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_external_review_package.py",
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_external_review_package.py",
        "evidence/s66_s64_fallback_reason_probe_review_hardening_implementation.json",
        "evidence/s63_signature_bucket_fallback_reason_probe_readiness.json",
        "evidence/s63_future_command_template.json",
        "coordination/agents_s63_s67_gate_excerpt.md",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_readiness.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_review.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_s64_fail_closed_hardening.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_rereview_package_v2.py",
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_readiness.py",
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_review.py",
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_rereview_package_v2.py",
        "test_context/src/tests/test_exact_contract.py",
    ]


def _package_path_for_input(key: str) -> Path:
    mapping = {
        "s65_failed_review_raw": Path("evidence/s65_failed_review_reply_raw.md"),
        "s65_review_summary": Path("evidence/s65_external_review_reply_summary.json"),
        "s65_package_summary": Path("evidence/s65_external_review_package_summary.json"),
        "s65_package_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_external_review_package.py"
        ),
        "s65_package_tests": Path(
            "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_external_review_package.py"
        ),
        "s66_implementation": Path(
            "evidence/s66_s64_fallback_reason_probe_review_hardening_implementation.json"
        ),
        "s63_readiness": Path("evidence/s63_signature_bucket_fallback_reason_probe_readiness.json"),
        "s63_future_command": Path("evidence/s63_future_command_template.json"),
        "agents": Path("coordination/agents_s63_s67_gate_excerpt.md"),
        "s63_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_readiness.py"
        ),
        "s64_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_review.py"
        ),
        "s66_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_s64_fail_closed_hardening.py"
        ),
        "s67_package_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_rereview_package_v2.py"
        ),
        "s63_tests": Path(
            "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_readiness.py"
        ),
        "s64_tests": Path(
            "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_review.py"
        ),
        "s67_tests": Path(
            "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_fallback_reason_probe_rereview_package_v2.py"
        ),
        "exact_contract_tests": Path("test_context/src/tests/test_exact_contract.py"),
    }
    return mapping[key]


def _agents_gate_excerpt(path: Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    markers = [
        "GPT Project Review Standing Authorization",
        "Current S63/S64 fallback-reason probe readiness state",
        "Current S65 fallback-reason probe review package",
        "Current S65 external review result",
        "Current S66/S67 S64 fail-closed hardening state",
    ]
    lines = [line for line in text.splitlines() if any(marker in line for marker in markers)]
    if not lines:
        raise ValueError(f"Could not find S63-S67 gate excerpt in {path}")
    return "\n".join(["# AGENTS Gate Excerpt", "", *lines, ""])


def _write_zip(staging_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging_dir.rglob("*")):
            if path.is_file():
                archive.write(_filesystem_path_for_zip(path), path.relative_to(staging_dir).as_posix())


def _filesystem_path_for_zip(path: Path) -> str:
    absolute = os.path.abspath(os.fspath(path))
    if os.name != "nt" or absolute.startswith("\\\\?\\"):
        return absolute
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute.lstrip("\\")
    return "\\\\?\\" + absolute


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
        or "67_signature_bucket_fallback_reason_probe_rereview_package_v2" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S67 re-review package namespace: {path}")


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
