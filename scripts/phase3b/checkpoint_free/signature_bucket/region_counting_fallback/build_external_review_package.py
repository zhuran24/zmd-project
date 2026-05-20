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
DEFAULT_OUTPUT_DIR = (
    ARTIFACT_ROOT
    / "61_signature_bucket_region_counting_fallback_external_review_package"
)
DEFAULT_RUN_ID = "signature_bucket_region_counting_fallback_external_review_package_001"

DEFAULT_INPUTS = {
    "s50_external_review_summary": ARTIFACT_ROOT
    / "50_signature_bucket_mandatory_scan_region_count_external_review_package"
    / "signature_bucket_mandatory_scan_region_count_external_review_package_001"
    / "external_review_reply_summary.json",
    "s51_implementation": ARTIFACT_ROOT
    / "51_signature_bucket_mandatory_region_counting_implementation"
    / "s51_signature_bucket_mandatory_region_counting_implementation.json",
    "s59_probe": ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_signature_bucket_region_counting_inst_no_solve_001"
    / "overlay_timing_probe.json",
    "s53_review": ARTIFACT_ROOT
    / "53_signature_bucket_mandatory_region_counting_probe_review"
    / "signature_bucket_mandatory_region_counting_probe_review.json",
    "s60_strategy": ARTIFACT_ROOT
    / "60_signature_bucket_region_counting_fallback_strategy"
    / "signature_bucket_region_counting_fallback_strategy.json",
    "agents": WORKSPACE_ROOT / "AGENTS.md",
    "exact_coordinate_master_source": PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py",
    "s53_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "mandatory_region" / "build_mandatory_region_counting_probe_review.py",
    "s60_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "region_counting_fallback" / "build_strategy.py",
    "s61_package_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "region_counting_fallback" / "build_external_review_package.py",
    "s51_focused_tests": PROJECT_ROOT / "src" / "tests" / "test_master.py",
    "s53_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py",
    "s60_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_region_counting_fallback_strategy.py",
    "s61_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_region_counting_fallback_external_review_package.py",
    "exact_contract_tests": PROJECT_ROOT / "src" / "tests" / "test_exact_contract.py",
}

REVIEW_WORDING_REQUIREMENTS = [
    "needs review first",
    "review is not authorization",
    "if review passes request user/project-owner authorization",
]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    package = build_signature_bucket_region_counting_fallback_external_review_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket region-counting fallback external review package")
    print(f"status={package['status']}")
    print(f"zip_path={_display_path(PROJECT_ROOT, Path(package['zip_path']))}")
    print(f"zip_sha256={package.get('zip_sha256')}")
    print(f"clean_extraction_validated={package['clean_extraction_validation']['validated']}")
    return 0 if package["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a clean-extraction-validated S61 external review package for "
            "the S60 residual fallback instrumentation spec."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_region_counting_fallback_external_review_package(
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
        "schema": "phase3b-signature-bucket-region-counting-fallback-external-review-package/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "package_kind": "external_review_residual_fallback_reason_instrumentation_spec_package",
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
        (run_dir / "external_review_package_summary.md").write_text(render_package_markdown(payload), encoding="utf-8")
        atomic_write_json(run_dir / "sensitive_path_before.json", before)
        atomic_write_json(run_dir / "sensitive_path_after.json", after)
        atomic_write_json(run_dir / "sensitive_path_comparison.json", sensitive_comparison)
    return payload


def render_package_markdown(payload: Mapping[str, Any]) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    return "\n".join(
        [
            "# Phase3B S61 Region-Counting Fallback External Review Package",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Zip: `{payload.get('zip_path')}`",
            f"- SHA256: `{payload.get('zip_sha256')}`",
            f"- Clean extraction validated: `{validation.get('validated')}`",
            "- Source mutation performed: `false`",
            "- CpSolver.Solve called: `false`",
            "- Proof source: `false`",
            "- Checkpoint written: `false`",
            "- Review required before authorization: `true`",
            "",
            "This package asks external review whether the S60 default-off fallback-reason instrumentation scope is safe to request authorization for. It is not authorization.",
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
            "# Review Request: Phase3B S60/S61 Signature-Bucket Region-Counting Fallback Instrumentation",
            "",
            "Uploaded package to review:",
            "",
            f"- Package filename: `{package_filename}`",
            f"- Package SHA256: `{package_sha256}`",
            "",
            "Status: needs review first. This review is not authorization. If review passes request user/project-owner authorization before any source patch.",
            "",
            "Gate marker for automated checks: if review passes request user/project-owner authorization.",
            "",
            "Context: S59 completed exactly one enabled `42x32` no-solve probe safely. Mandatory region counting was effective, reducing mandatory scan time from about 68.08s to about 32.27s, but 6,786 of 21,489 attempts still fell back to the legacy scan. Required-optional scan stayed inactive. The proposed next patch is stats-only fallback-reason instrumentation, not another optimization yet.",
            "",
            "Please review these questions:",
            "",
            "1. Is the S60 interpretation correct: the remaining hotspot should be treated as residual mandatory fallback/legacy scan work rather than proof that region counting failed?",
            "2. Is the proposed default-off env gate `EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION` narrow and safe enough to request later user/project-owner authorization?",
            "3. Is it safe for enabled diagnostics to publish bounded fallback reason counters and top fallback entries under the existing `signature_tightening_instrumentation` output, without changing ModelProto, constraints, region-counting choices, scheduler, proof, or checkpoints?",
            "4. Are the proposed fallback reason categories sufficient to explain why attempts do not use compact region counting?",
            "5. Are the proposed tests enough for a later stats-only patch: default-off no delta, enabled no proto/constraint delta, reason coverage, and bounded output?",
            "6. If there are no blockers, please state only that this default-off fallback-reason instrumentation scope is safe to request user/project-owner authorization; do not treat review approval as authorization.",
            "",
            "Hard boundaries: this is review-only; do not approve final 168h, runtime solve, another enabled probe, canonical checkpoint writes/imports/backfills, proof/preflight/release/viewer/frontdoor mutation, runtime elimination, production default changes, or direct implementation without later user/project-owner authorization.",
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
        "schema": "phase3b-signature-bucket-region-counting-fallback-external-review-package-manifest/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "run_id": str(run_id),
        "zip_path": str(zip_path),
        "zip_sha256": None,
        "proof_source": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
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
            "This package is for Phase3B / Endfield external review of the S60 "
            "signature-bucket mandatory region-counting fallback instrumentation spec. "
            "It needs review first; review is not authorization; if review passes "
            "request user/project-owner authorization. It is not proof evidence and "
            "does not authorize or perform source mutation.\n"
        ),
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
        if key == "exact_coordinate_master_source":
            package_path.write_text(_source_snippet(source_path), encoding="utf-8")
        elif key == "s51_focused_tests":
            package_path.write_text(_test_snippet(source_path), encoding="utf-8")
        elif key == "agents":
            package_path.write_text(_agents_gate_excerpt(source_path), encoding="utf-8")
        else:
            shutil.copy2(source_path, package_path)


def _source_snippet(source_path: Path) -> str:
    text = Path(source_path).read_text(encoding="utf-8")
    sections = [
        _snippet_around(text, "def _mandatory_region_counting_payload", 8, 80),
        _snippet_around(text, "def _mandatory_region_blocked_counts_for_domain", 8, 120),
        _snippet_around(text, "def _apply_ghost_anchor_signature_bucket_tightening", 8, 360),
        _snippet_around(text, "signature_tightening_instrumentation = tightening_stats.get", 6, 24),
    ]
    return "\n\n# ---- snippet section ----\n\n".join(sections)


def _test_snippet(source_path: Path) -> str:
    text = Path(source_path).read_text(encoding="utf-8")
    sections = [
        _snippet_around(text, "def test_ghost_signature_bucket_mandatory_region_counting_enabled_matches_legacy_supported_fixture", 4, 60),
        _snippet_around(text, "def test_ghost_signature_bucket_mandatory_region_counting_falls_back_for_unsupported_footprints", 4, 60),
        _snippet_around(text, "def test_exact_core_overlay_signature_bucket_mandatory_region_counting_matches_legacy", 4, 80),
    ]
    return "\n\n# ---- snippet section ----\n\n".join(sections)


def _snippet_around(text: str, marker: str, before: int, after: int) -> str:
    lines = text.splitlines()
    marker_index = next((idx for idx, line in enumerate(lines) if marker in line), None)
    if marker_index is None:
        raise ValueError(f"marker not found for source snippet: {marker}")
    start = max(0, marker_index - int(before))
    end = min(len(lines), marker_index + int(after))
    return "\n".join(f"{idx + 1}: {lines[idx]}" for idx in range(start, end))


def _agents_gate_excerpt(path: Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    markers = [
        "GPT Project Review Standing Authorization",
        "Current S51 mandatory-region-counting source patch state",
        "Current S58 external review result",
        "Current S59 enabled no-solve probe result",
    ]
    lines = [line for line in text.splitlines() if any(marker in line for marker in markers)]
    if not lines:
        raise ValueError(f"Could not find S51/S58/S59/review gate excerpt in {path}")
    return "\n".join(["# AGENTS Gate Excerpt", "", *lines, ""])


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
    s60 = _load_json(extract_dir / "evidence/s60_signature_bucket_region_counting_fallback_strategy.json")
    s53 = _load_json(extract_dir / "evidence/s53_signature_bucket_mandatory_region_counting_probe_review.json")
    request_text = (extract_dir / "review_request.md").read_text(encoding="utf-8")
    semantic_checks = {
        "zip_sha256_matches_expected": _sha256(zip_path) == expected_zip_sha256,
        "manifest_review_required_true": manifest.get("review_required_before_authorization") is True,
        "manifest_external_review_not_authorization": manifest.get("external_review_is_authorization") is False,
        "s53_effective": _mapping(s53.get("interpretation")).get("classification")
        == "mandatory_region_counting_effective",
        "s60_classification": _mapping(s60.get("interpretation")).get("classification")
        == "mandatory_region_counting_effective_but_fallback_residual_strategy_required",
        "s60_source_mutation_false": s60.get("source_mutation_performed") is False,
        "s60_implementation_allowed_false": _mapping(s60.get("interpretation")).get("implementation_allowed_now") is False,
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
        "evidence/s50_external_review_reply_summary.json",
        "evidence/s51_signature_bucket_mandatory_region_counting_implementation.json",
        "evidence/s59_overlay_timing_probe.json",
        "evidence/s53_signature_bucket_mandatory_region_counting_probe_review.json",
        "evidence/s60_signature_bucket_region_counting_fallback_strategy.json",
        "coordination/agents_s51_s58_s59_gate_excerpt.md",
        "source_context/src/models/exact_coordinate_master_region_fallback_snippets.py",
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/mandatory_region/build_mandatory_region_counting_probe_review.py",
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/region_counting_fallback/build_strategy.py",
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/region_counting_fallback/build_external_review_package.py",
        "test_context/src/tests/test_master_region_counting_snippets.py",
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/mandatory_region/test_mandatory_region_counting_probe_review.py",
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/region_counting_fallback/test_strategy.py",
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/region_counting_fallback/test_external_review_package.py",
        "test_context/src/tests/test_exact_contract.py",
    ]


def _package_path_for_input(key: str) -> Path:
    mapping = {
        "s50_external_review_summary": Path("evidence/s50_external_review_reply_summary.json"),
        "s51_implementation": Path("evidence/s51_signature_bucket_mandatory_region_counting_implementation.json"),
        "s59_probe": Path("evidence/s59_overlay_timing_probe.json"),
        "s53_review": Path("evidence/s53_signature_bucket_mandatory_region_counting_probe_review.json"),
        "s60_strategy": Path("evidence/s60_signature_bucket_region_counting_fallback_strategy.json"),
        "agents": Path("coordination/agents_s51_s58_s59_gate_excerpt.md"),
        "exact_coordinate_master_source": Path(
            "source_context/src/models/exact_coordinate_master_region_fallback_snippets.py"
        ),
        "s53_builder": Path(
            "code_context/scripts/phase3b/checkpoint_free/signature_bucket/mandatory_region/build_mandatory_region_counting_probe_review.py"
        ),
        "s60_builder": Path(
            "code_context/scripts/phase3b/checkpoint_free/signature_bucket/region_counting_fallback/build_strategy.py"
        ),
        "s61_package_builder": Path(
            "code_context/scripts/phase3b/checkpoint_free/signature_bucket/region_counting_fallback/build_external_review_package.py"
        ),
        "s51_focused_tests": Path("test_context/src/tests/test_master_region_counting_snippets.py"),
        "s53_tests": Path(
            "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/mandatory_region/test_mandatory_region_counting_probe_review.py"
        ),
        "s60_tests": Path(
            "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/region_counting_fallback/test_strategy.py"
        ),
        "s61_tests": Path(
            "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/region_counting_fallback/test_external_review_package.py"
        ),
        "exact_contract_tests": Path("test_context/src/tests/test_exact_contract.py"),
    }
    return mapping[key]


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
        or "61_signature_bucket_region_counting_fallback_external_review_package" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S61 external review package namespace: {path}")


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
