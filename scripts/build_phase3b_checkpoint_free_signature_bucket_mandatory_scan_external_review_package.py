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
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "50_signature_bucket_mandatory_scan_region_count_external_review_package"
DEFAULT_RUN_ID = "signature_bucket_mandatory_scan_region_count_external_review_package_001"

DEFAULT_INPUTS = {
    "s46_implementation": ARTIFACT_ROOT
    / "46_signature_bucket_visibility_path_patch_implementation"
    / "s46_signature_bucket_visibility_path_patch_implementation.json",
    "s48_probe": ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_signature_bucket_visibility_inst_no_solve_001"
    / "overlay_timing_probe.json",
    "s48_review": ARTIFACT_ROOT
    / "48_signature_bucket_visibility_probe_review"
    / "signature_bucket_visibility_probe_review.json",
    "s49_strategy": ARTIFACT_ROOT
    / "49_signature_bucket_mandatory_scan_strategy"
    / "signature_bucket_mandatory_scan_strategy.json",
    "agents": WORKSPACE_ROOT / "AGENTS.md",
    "exact_coordinate_master_source": PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py",
    "s49_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_mandatory_scan_strategy.py",
    "s50_package_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_mandatory_scan_external_review_package.py",
    "s48_review_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_visibility_probe_review.py",
    "s49_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_mandatory_scan_strategy.py",
    "s50_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_mandatory_scan_external_review_package.py",
    "focused_master_tests": PROJECT_ROOT / "src" / "tests" / "test_master.py",
    "exact_contract_tests": PROJECT_ROOT / "src" / "tests" / "test_exact_contract.py",
}

REVIEW_WORDING_REQUIREMENTS = [
    "needs review first",
    "review is not authorization",
    "if review passes request user/project-owner authorization",
]


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    package = build_signature_bucket_mandatory_scan_external_review_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket mandatory scan external review package")
    print(f"status={package['status']}")
    print(f"zip_path={_display_path(PROJECT_ROOT, Path(package['zip_path']))}")
    print(f"zip_sha256={package.get('zip_sha256')}")
    print(f"clean_extraction_validated={package['clean_extraction_validation']['validated']}")
    return 0 if package["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a clean-extraction-validated S50 external review package for "
            "the mandatory signature-bucket region-counting patch spec."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_mandatory_scan_external_review_package(
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
    package_request_text = _review_request_text(
        input_paths,
        package_filename=zip_path.name,
        package_sha256="outer review request supplies the final zip SHA256",
    )
    manifest = _manifest(
        project_root=project_root,
        run_id=str(run_id),
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
        _write_staging_files(
            staging_dir=staging_dir,
            manifest=manifest,
            package_request_text=package_request_text,
            inputs=input_paths,
        )
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
        "schema": "phase3b-signature-bucket-mandatory-scan-external-review-package/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "package_kind": "external_review_mandatory_scan_region_count_patch_spec_package",
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
        "production_profile_changed": False,
        "runtime_execution_performed": False,
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
            render_signature_bucket_mandatory_scan_external_review_package_markdown(payload),
            encoding="utf-8",
        )
        atomic_write_json(run_dir / "sensitive_path_before.json", before)
        atomic_write_json(run_dir / "sensitive_path_after.json", after)
        atomic_write_json(run_dir / "sensitive_path_comparison.json", sensitive_comparison)
    return payload


def render_signature_bucket_mandatory_scan_external_review_package_markdown(
    payload: Mapping[str, Any],
) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    return "\n".join(
        [
            "# Phase3B S50 Mandatory Scan Region Count External Review Package",
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
            "This package asks external review whether the S49 default-off mandatory region-counting optimization spec is safe to request authorization for. It is not authorization.",
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
            "# Review Request: Phase3B S49/S50 Mandatory Signature-Bucket Region Counting",
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
            "Context: S48 completed the single enabled `42x32` no-solve visibility probe safely and showed S46 fixed build_stats visibility. The remaining hotspot is `per_anchor_mandatory_scan`, which spent about 68s scanning mandatory bucket cells/pose hits while required-optional scan stayed inactive.",
            "",
            "Please review these questions:",
            "",
            "1. Does the proposed default-off scope stay narrow enough: only replace mandatory blocked-count computation inside `_apply_ghost_anchor_signature_bucket_tightening` when exact compact region counting is available?",
            "2. Does the region-overlap counting approach appear capable of preserving exact blocked bucket counts, assuming tests compare it against the legacy per-cell/per-pose-hit scan?",
            "3. Is fallback-to-legacy sufficient when compact geometry is unsupported, missing, or equivalence cannot be proven?",
            "4. Does the default-off contract preserve proof safety, production defaults, ModelProto shape, scheduler behavior, and checkpoint semantics?",
            "5. Are the proposed tests enough to prove enabled output matches legacy constraints for covered fixtures?",
            "6. If there are no blockers, please state only that this default-off optimization scope is safe to request user/project-owner authorization; do not treat review approval as authorization.",
            "",
            "Hard boundaries: this is review-only; do not approve final 168h, runtime solve, canonical checkpoint writes/imports/backfills, proof/preflight/release/viewer/frontdoor mutation, runtime elimination, production default changes, or direct implementation without later user/project-owner authorization.",
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
        "schema": "phase3b-signature-bucket-mandatory-scan-external-review-package-manifest/v0",
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
    package_request_text: str,
    inputs: Mapping[str, Path],
) -> None:
    (staging_dir / "README.md").write_text(
        (
            "This package is for Phase3B / Endfield external review of the S49 "
            "mandatory signature-bucket region-counting optimization spec. It needs "
            "review first; review is not authorization; if review passes request "
            "user/project-owner authorization. It is not proof evidence and does not "
            "authorize or perform source mutation.\n"
        ),
        encoding="utf-8",
    )
    (staging_dir / "review_request.md").write_text(package_request_text, encoding="utf-8")
    atomic_write_json(staging_dir / "manifest.json", dict(manifest))
    for key, source_path in sorted(inputs.items()):
        package_path = staging_dir / _package_path_for_input(key)
        package_path.parent.mkdir(parents=True, exist_ok=True)
        if not source_path.exists():
            raise FileNotFoundError(f"required review package input is missing: {key}: {source_path}")
        if key in {"exact_coordinate_master_source", "focused_master_tests"}:
            package_path.write_text(_source_snippet(key, source_path), encoding="utf-8")
        elif key == "agents":
            package_path.write_text(_agents_gate_excerpt(source_path), encoding="utf-8")
        else:
            shutil.copy2(source_path, package_path)


def _source_snippet(key: str, source_path: Path) -> str:
    text = Path(source_path).read_text(encoding="utf-8")
    if key == "exact_coordinate_master_source":
        sections = [
            _snippet_around(text, "class SignatureRegion", 8, 35),
            _snippet_around(text, "def _build_bucket_regions", 8, 130),
            _snippet_around(text, "def _apply_ghost_anchor_signature_bucket_tightening", 8, 430),
        ]
    elif key == "focused_master_tests":
        sections = [
            _snippet_around(
                text,
                "def test_exact_core_overlay_signature_bucket_tightening_instrumentation_records_mandatory_without_model_delta",
                6,
                90,
            )
        ]
    else:
        sections = [text]
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
        "Current S46 visibility-path source patch state",
        "Current S48 signature-bucket visibility probe result",
    ]
    lines = [line for line in text.splitlines() if any(marker in line for marker in markers)]
    if not lines:
        raise ValueError(f"Could not find S46/S48/review gate excerpt in {path}")
    return "\n".join(["# AGENTS Gate Excerpt", "", *lines, ""])


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
    # Avoid Path.resolve() here. On Windows pytest temp paths can occasionally
    # resolve through transient NTFS deletion aliases, while abspath is enough
    # for zipfile source reads and still supports extended-length prefixing.
    absolute = os.path.abspath(os.fspath(path))
    if os.name != "nt" or absolute.startswith("\\\\?\\"):
        return absolute
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute.lstrip("\\")
    return "\\\\?\\" + absolute


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
    s49 = _load_json(extract_dir / "evidence/s49_signature_bucket_mandatory_scan_strategy.json")
    request_text = (extract_dir / "review_request.md").read_text(encoding="utf-8")
    semantic_checks = {
        "zip_sha256_matches_expected": _sha256(zip_path) == expected_zip_sha256,
        "manifest_review_required_true": manifest.get("review_required_before_authorization") is True,
        "manifest_external_review_not_authorization": manifest.get("external_review_is_authorization") is False,
        "s49_classification": _mapping(s49.get("interpretation")).get("classification")
        == "mandatory_signature_bucket_region_counting_strategy_required",
        "s49_source_mutation_false": s49.get("source_mutation_performed") is False,
        "s49_implementation_allowed_false": _mapping(s49.get("interpretation")).get("implementation_allowed_now") is False,
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
        "evidence/s46_signature_bucket_visibility_path_patch_implementation.json",
        "evidence/s48_overlay_timing_probe.json",
        "evidence/s48_signature_bucket_visibility_probe_review.json",
        "evidence/s49_signature_bucket_mandatory_scan_strategy.json",
        "coordination/agents_s46_s48_gate_excerpt.md",
        "source_context/src/models/exact_coordinate_master_mandatory_scan_snippets.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_scan_strategy.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_scan_external_review_package.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_visibility_probe_review.py",
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_scan_strategy.py",
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_scan_external_review_package.py",
        "test_context/src/tests/test_master_signature_bucket_exact_core_overlay_snippet.py",
        "test_context/src/tests/test_exact_contract.py",
    ]


def _package_path_for_input(key: str) -> Path:
    mapping = {
        "s46_implementation": Path("evidence/s46_signature_bucket_visibility_path_patch_implementation.json"),
        "s48_probe": Path("evidence/s48_overlay_timing_probe.json"),
        "s48_review": Path("evidence/s48_signature_bucket_visibility_probe_review.json"),
        "s49_strategy": Path("evidence/s49_signature_bucket_mandatory_scan_strategy.json"),
        "agents": Path("coordination/agents_s46_s48_gate_excerpt.md"),
        "exact_coordinate_master_source": Path(
            "source_context/src/models/exact_coordinate_master_mandatory_scan_snippets.py"
        ),
        "s49_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_scan_strategy.py"
        ),
        "s50_package_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_scan_external_review_package.py"
        ),
        "s48_review_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_visibility_probe_review.py"
        ),
        "s49_tests": Path(
            "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_scan_strategy.py"
        ),
        "s50_tests": Path(
            "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_scan_external_review_package.py"
        ),
        "focused_master_tests": Path("test_context/src/tests/test_master_signature_bucket_exact_core_overlay_snippet.py"),
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
        or "50_signature_bucket_mandatory_scan_region_count_external_review_package" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S50 external review package namespace: {path}")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
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
