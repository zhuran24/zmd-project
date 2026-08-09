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
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "45_signature_bucket_visibility_path_external_review_package"
DEFAULT_RUN_ID = "signature_bucket_visibility_path_external_review_package_001"

DEFAULT_INPUTS = {
    "s41_implementation": ARTIFACT_ROOT
    / "41_signature_bucket_instrumentation_implementation"
    / "s41_signature_bucket_instrumentation_implementation.json",
    "s42_readiness": ARTIFACT_ROOT
    / "42_signature_bucket_enabled_no_solve_probe_readiness"
    / "signature_bucket_enabled_no_solve_probe_readiness.json",
    "s43_probe": ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_signature_bucket_inst_no_solve_001"
    / "overlay_timing_probe.json",
    "s43_review": ARTIFACT_ROOT
    / "43_signature_bucket_enabled_no_solve_probe_review"
    / "signature_bucket_enabled_no_solve_probe_review.json",
    "s44_strategy": ARTIFACT_ROOT
    / "44_signature_bucket_visibility_path_strategy"
    / "signature_bucket_visibility_path_strategy.json",
    "agents": WORKSPACE_ROOT / "AGENTS.md",
    "exact_coordinate_master_source": PROJECT_ROOT
    / "src"
    / "models"
    / "exact_coordinate_master.py",
    "master_model_source": PROJECT_ROOT / "src" / "models" / "master_model.py",
    "s44_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "visibility" / "build_path_strategy.py",
    "s45_package_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "visibility" / "build_path_external_review_package.py",
    "s43_review_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "enabled_no_solve" / "build_review.py",
    "s44_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_visibility_path_strategy.py",
    "s45_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_visibility_path_external_review_package.py",
    "s43_review_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_enabled_no_solve_probe_review.py",
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
    package = build_signature_bucket_visibility_path_external_review_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket visibility path external review package")
    print(f"status={package['status']}")
    print(f"zip_path={_display_path(PROJECT_ROOT, Path(package['zip_path']))}")
    print(f"zip_sha256={package.get('zip_sha256')}")
    print(f"clean_extraction_validated={package['clean_extraction_validation']['validated']}")
    return 0 if package["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a clean-extraction-validated S45 external review package for "
            "the signature-bucket visibility-path patch spec."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_visibility_path_external_review_package(
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
        "schema": "phase3b-signature-bucket-visibility-path-external-review-package/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "package_kind": "external_review_visibility_path_patch_spec_package",
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
            render_signature_bucket_visibility_path_external_review_package_markdown(payload),
            encoding="utf-8",
        )
        atomic_write_json(run_dir / "sensitive_path_before.json", before)
        atomic_write_json(run_dir / "sensitive_path_after.json", after)
        atomic_write_json(run_dir / "sensitive_path_comparison.json", sensitive_comparison)
    return payload


def render_signature_bucket_visibility_path_external_review_package_markdown(
    payload: Mapping[str, Any],
) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    return "\n".join(
        [
            "# Phase3B S45 Signature Bucket Visibility Path External Review Package",
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
            "This package asks external review whether the S44 stats-only visibility-path patch spec is safe to request authorization for. It is not authorization.",
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
            "# Review Request: Phase3B S44/S45 Signature Bucket Visibility Path",
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
            "Context: S43 completed the single enabled `42x32` no-solve probe safely, but `signature_tightening_instrumentation` was missing from final `build_stats`. S44 proposes a narrow stats-only visibility fix for the exact-core overlay path.",
            "",
            "Please review these questions:",
            "",
            "1. Does S44 correctly classify the issue as an exact-core overlay instrumentation visibility gap rather than a solver/runtime/proof issue?",
            "2. Is the proposed source-patch scope narrow enough: keep collection in `_apply_ghost_anchor_signature_bucket_tightening`, keep normal-path `_add_global_valid_inequalities` copy unchanged, and add only a method-local stats copy after the existing ghost-conditioned count writes?",
            "3. Is the rejected approach correct: do not call `_add_global_valid_inequalities` from `MasterPlacementModel.from_exact_core`, because that could add or duplicate constraints?",
            "4. Does the default-off contract preserve no instrumentation key, no ModelProto delta, no variable/constraint delta, no scheduler/proof/checkpoint effects, and unchanged production defaults?",
            "5. If there are no blockers, please state only that the visibility-path patch is safe to request user/project-owner authorization; do not treat review approval as authorization.",
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
        "schema": "phase3b-signature-bucket-visibility-path-external-review-package-manifest/v0",
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
            "This package is for Phase3B / Endfield external review of the S44 "
            "signature-bucket instrumentation visibility-path patch spec. It needs "
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
        if key in {"exact_coordinate_master_source", "master_model_source", "focused_master_tests"}:
            package_path.write_text(_source_snippet(key, source_path), encoding="utf-8")
        elif key == "agents":
            package_path.write_text(_agents_gate_excerpt(source_path), encoding="utf-8")
        else:
            shutil.copy2(source_path, package_path)


def _source_snippet(key: str, source_path: Path) -> str:
    text = Path(source_path).read_text(encoding="utf-8")
    if key == "exact_coordinate_master_source":
        sections = [
            _snippet_around(text, "def _apply_ghost_anchor_signature_bucket_tightening", 8, 420),
            _snippet_around(text, "def _add_global_valid_inequalities", 8, 300),
        ]
    elif key == "master_model_source":
        sections = [_snippet_around(text, "def from_exact_core", 8, 130)]
    elif key == "focused_master_tests":
        sections = [
            _snippet_around(
                text,
                "def test_ghost_signature_bucket_tightening_instrumentation_default_off_is_absent",
                4,
                160,
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
        "Current S43 signature-bucket enabled no-solve probe result",
        "Current S42 signature-bucket enabled no-solve probe readiness",
        "Current S41 signature-bucket instrumentation state",
    ]
    lines = [line for line in text.splitlines() if any(marker in line for marker in markers)]
    if not lines:
        raise ValueError(f"Could not find S41-S43/review gate excerpt in {path}")
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
    resolved = str(path.resolve())
    if os.name != "nt" or resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved.lstrip("\\")
    return "\\\\?\\" + resolved


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
    s44 = _load_json(extract_dir / "evidence/s44_signature_bucket_visibility_path_strategy.json")
    package_request_text = (extract_dir / "review_request.md").read_text(encoding="utf-8")
    semantic_checks = {
        "zip_sha256_matches_expected": _sha256(zip_path) == expected_zip_sha256,
        "manifest_review_required_true": manifest.get("review_required_before_authorization") is True,
        "manifest_external_review_not_authorization": manifest.get("external_review_is_authorization") is False,
        "s44_classification": _mapping(s44.get("interpretation")).get("classification")
        == "exact_core_overlay_instrumentation_visibility_gap",
        "s44_source_mutation_false": s44.get("source_mutation_performed") is False,
        "s44_implementation_allowed_false": _mapping(s44.get("interpretation")).get("implementation_allowed_now") is False,
        "package_request_has_review_words": all(text in package_request_text for text in REVIEW_WORDING_REQUIREMENTS),
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
        "evidence/s41_signature_bucket_instrumentation_implementation.json",
        "evidence/s42_signature_bucket_enabled_no_solve_probe_readiness.json",
        "evidence/s43_overlay_timing_probe.json",
        "evidence/s43_signature_bucket_enabled_no_solve_probe_review.json",
        "evidence/s44_signature_bucket_visibility_path_strategy.json",
        "coordination/agents_s41_s43_gate_excerpt.md",
        "source_context/src/models/exact_coordinate_master_signature_visibility_snippets.py",
        "source_context/src/models/master_model_from_exact_core_snippet.py",
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/visibility/build_path_strategy.py",
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/visibility/build_path_external_review_package.py",
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/enabled_no_solve/build_review.py",
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/visibility/test_path_strategy.py",
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/visibility/test_path_external_review_package.py",
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/enabled_no_solve/test_review.py",
        "test_context/src/tests/test_master_signature_bucket_snippet.py",
        "test_context/src/tests/test_exact_contract.py",
    ]


def _package_path_for_input(key: str) -> Path:
    mapping = {
        "s41_implementation": Path("evidence/s41_signature_bucket_instrumentation_implementation.json"),
        "s42_readiness": Path("evidence/s42_signature_bucket_enabled_no_solve_probe_readiness.json"),
        "s43_probe": Path("evidence/s43_overlay_timing_probe.json"),
        "s43_review": Path("evidence/s43_signature_bucket_enabled_no_solve_probe_review.json"),
        "s44_strategy": Path("evidence/s44_signature_bucket_visibility_path_strategy.json"),
        "agents": Path("coordination/agents_s41_s43_gate_excerpt.md"),
        "exact_coordinate_master_source": Path(
            "source_context/src/models/exact_coordinate_master_signature_visibility_snippets.py"
        ),
        "master_model_source": Path("source_context/src/models/master_model_from_exact_core_snippet.py"),
        "s44_builder": Path(
            "code_context/scripts/phase3b/checkpoint_free/signature_bucket/visibility/build_path_strategy.py"
        ),
        "s45_package_builder": Path(
            "code_context/scripts/phase3b/checkpoint_free/signature_bucket/visibility/build_path_external_review_package.py"
        ),
        "s43_review_builder": Path(
            "code_context/scripts/phase3b/checkpoint_free/signature_bucket/enabled_no_solve/build_review.py"
        ),
        "s44_tests": Path(
            "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/visibility/test_path_strategy.py"
        ),
        "s45_tests": Path(
            "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/visibility/test_path_external_review_package.py"
        ),
        "s43_review_tests": Path(
            "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/enabled_no_solve/test_review.py"
        ),
        "focused_master_tests": Path("test_context/src/tests/test_master_signature_bucket_snippet.py"),
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
        or "45_signature_bucket_visibility_path_external_review_package" not in normalized
    ):
        raise ValueError(f"Refusing to write outside S45 external review package namespace: {path}")


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
