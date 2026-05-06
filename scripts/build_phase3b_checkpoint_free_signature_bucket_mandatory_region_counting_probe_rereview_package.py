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
DEFAULT_OUTPUT_DIR = (
    ARTIFACT_ROOT
    / "56_signature_bucket_mandatory_region_counting_probe_rereview_package"
)
DEFAULT_RUN_ID = "s52_s53_region_probe_rereview_002"
DEFAULT_ZIP_FILENAME = f"{DEFAULT_RUN_ID}.zip"

DEFAULT_INPUTS = {
    "s54_failed_review_summary": ARTIFACT_ROOT
    / "54_signature_bucket_mandatory_region_counting_probe_external_review_package"
    / "s52_s53_region_probe_readiness_review_001"
    / "external_review_reply_summary.json",
    "s54_failed_review_raw": ARTIFACT_ROOT
    / "54_signature_bucket_mandatory_region_counting_probe_external_review_package"
    / "s52_s53_region_probe_readiness_review_001"
    / "external_review_reply_raw.md",
    "s55_implementation": ARTIFACT_ROOT
    / "55_s52_s53_readiness_hardening_implementation"
    / "s55_s52_s53_readiness_hardening_implementation.json",
    "s48_probe_review": ARTIFACT_ROOT
    / "48_signature_bucket_visibility_probe_review"
    / "signature_bucket_visibility_probe_review.json",
    "s49_strategy": ARTIFACT_ROOT
    / "49_signature_bucket_mandatory_scan_strategy"
    / "signature_bucket_mandatory_scan_strategy.json",
    "s50_review_summary": ARTIFACT_ROOT
    / "50_signature_bucket_mandatory_scan_region_count_external_review_package"
    / "signature_bucket_mandatory_scan_region_count_external_review_package_001"
    / "external_review_reply_summary.json",
    "s51_implementation": ARTIFACT_ROOT
    / "51_signature_bucket_mandatory_region_counting_implementation"
    / "s51_signature_bucket_mandatory_region_counting_implementation.json",
    "s52_readiness": ARTIFACT_ROOT
    / "52_signature_bucket_mandatory_region_counting_probe_readiness"
    / "signature_bucket_mandatory_region_counting_probe_readiness.json",
    "s52_future_command": ARTIFACT_ROOT
    / "52_signature_bucket_mandatory_region_counting_probe_readiness"
    / "future_command_template.json",
    "agents": WORKSPACE_ROOT / "AGENTS.md",
    "exact_coordinate_master_source": PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py",
    "s52_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_readiness.py",
    "s53_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py",
    "s54_package_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_external_review_package.py",
    "s56_package_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_rereview_package.py",
    "s52_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_readiness.py",
    "s53_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py",
    "s56_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_rereview_package.py",
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
    package = build_signature_bucket_mandatory_region_counting_probe_rereview_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket mandatory region-counting probe re-review package")
    print(f"status={package['status']}")
    print(f"zip_path={_display_path(PROJECT_ROOT, Path(package['zip_path']))}")
    print(f"zip_sha256={package.get('zip_sha256')}")
    print(f"clean_extraction_validated={package['clean_extraction_validation']['validated']}")
    return 0 if package["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a clean-extraction-validated S56 external re-review package "
            "after hardening S52/S53 mandatory region-counting probe readiness "
            "and review tooling."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_mandatory_region_counting_probe_rereview_package(
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
        "schema": "phase3b-signature-bucket-mandatory-region-counting-probe-rereview-package/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "package_kind": "external_rereview_mandatory_region_counting_probe_readiness_hardening_package",
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
            render_signature_bucket_mandatory_region_counting_probe_rereview_package_markdown(
                payload
            ),
            encoding="utf-8",
        )
        atomic_write_json(run_dir / "sensitive_path_before.json", before)
        atomic_write_json(run_dir / "sensitive_path_after.json", after)
        atomic_write_json(run_dir / "sensitive_path_comparison.json", sensitive_comparison)
    return payload


def render_signature_bucket_mandatory_region_counting_probe_rereview_package_markdown(
    payload: Mapping[str, Any],
) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    return "\n".join(
        [
            "# Phase3B S56 Mandatory Region Counting Probe Re-review Package",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Zip: `{payload.get('zip_path')}`",
            f"- SHA256: `{payload.get('zip_sha256')}`",
            f"- Clean extraction validated: `{validation.get('validated')}`",
            "- Probe executed in this slice: `false`",
            "- Source mutation performed: `false`",
            "- CpSolver.Solve called: `false`",
            "- Proof source: `false`",
            "- Checkpoint written: `false`",
            "- Review required before authorization: `true`",
            "",
            "This S56 package asks external re-review whether the hardened S52/S53 readiness and review tooling resolves the S54 blockers and is safe to request authorization for exactly one future enabled 42x32 no-solve probe. It is not authorization.",
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
            "# Review Request: Phase3B S56 S52/S53 Mandatory Region Counting Probe Readiness Re-review",
            "",
            "Uploaded package to review:",
            "",
            f"- Package filename: `{package_filename}`",
            f"- Package SHA256: `{package_sha256}`",
            "",
            "Status: needs review first. This review is not authorization. If review passes request user/project-owner authorization before executing the single enabled no-solve probe.",
            "",
            "Gate marker for automated checks: if review passes request user/project-owner authorization.",
            "",
            "Context: S54 external review did not pass because S52/S53 needed hardening. S55 has now hardened S52 to require exact command-vector equality and hardened S53 to fail closed on missing timing metrics, hard-boundary flags, and malformed sensitive-path comparison. S52 remains only a readiness artifact for one future enabled `42x32` no-solve probe, and S53 remains only the review tooling that will classify the probe after it exists. No probe is executed by this package.",
            "",
            "Please review these questions:",
            "",
            "1. Does the S55 hardening fully resolve the S54 blockers?",
            "2. Does S52 now require exact command-vector equality for the single future command and reject duplicate/extra/mutated flags?",
            "3. Does S53 now fail closed for missing baseline or mandatory-scan seconds, hard-boundary flags, and missing or malformed `sensitive_path_comparison`?",
            "4. Do S52/S53 still preserve the safety boundary: no `CpSolver.Solve`, no `main.py`, no `ExactCampaign`, no checkpoint write/import/backfill, no proof/preflight/release/viewer/frontdoor mutation, no production default change?",
            "5. Are the adversarial tests sufficient before asking the user/project-owner to authorize exactly one future enabled no-solve diagnostic probe?",
            "6. If there are no blockers, please state only that the hardened S52/S53 readiness scope is safe to request user/project-owner authorization for the single future no-solve probe; do not treat review approval as authorization.",
            "",
            "Hard boundaries: this is review-only; do not approve runtime solve, final 168h, canonical checkpoint writes/imports/backfills, proof/preflight/release/viewer/frontdoor mutation, runtime elimination, production default changes, `67x20`, full-wave, or direct execution without later user/project-owner authorization.",
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
        "schema": "phase3b-signature-bucket-mandatory-region-counting-probe-rereview-package-manifest/v0",
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
    package_request_text: str,
    inputs: Mapping[str, Path],
) -> None:
    (staging_dir / "README.md").write_text(
        (
            "This S56 package is for Phase3B / Endfield external re-review of "
            "the S55 hardening applied to S52/S53 mandatory region-counting "
            "probe readiness and review tooling after the S54 review blockers. "
            "It needs review first; review is not authorization; if review passes "
            "request user/project-owner authorization before executing the single "
            "future enabled no-solve probe. It is not proof evidence and does not "
            "execute the probe or perform source mutation.\n"
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
            _snippet_around(text, "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV", 8, 35),
            _snippet_around(text, "def resolve_ghost_signature_bucket_mandatory_region_counting_enabled", 6, 35),
            _snippet_around(text, "def _mandatory_region_counting_payload", 8, 95),
            _snippet_around(text, "def _apply_ghost_anchor_signature_bucket_tightening", 8, 360),
        ]
    elif key == "focused_master_tests":
        sections = [
            _snippet_around(
                text,
                "def test_ghost_signature_bucket_mandatory_region_counting_enabled_matches_legacy_supported_fixture",
                6,
                95,
            ),
            _snippet_around(
                text,
                "def test_exact_core_overlay_signature_bucket_mandatory_region_counting_matches_legacy",
                6,
                90,
            ),
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
        "Current S51 mandatory-region-counting source patch state",
        "Current S52/S53 mandatory-region-counting probe readiness state",
        "Current S54 external review result",
        "Current S55 S52/S53 readiness hardening state",
    ]
    lines = [line for line in text.splitlines() if any(marker in line for marker in markers)]
    if not lines:
        raise ValueError(f"Could not find S51/S52/S53/review gate excerpt in {path}")
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
    s54 = _load_json(extract_dir / "evidence/s54_failed_review_reply_summary.json")
    s55 = _load_json(
        extract_dir / "evidence/s55_s52_s53_readiness_hardening_implementation.json"
    )
    s52 = _load_json(
        extract_dir / "evidence/s52_signature_bucket_mandatory_region_counting_probe_readiness.json"
    )
    request_text = (extract_dir / "review_request.md").read_text(encoding="utf-8")
    semantic_checks = {
        "zip_sha256_matches_expected": _sha256(zip_path) == expected_zip_sha256,
        "manifest_review_required_true": manifest.get("review_required_before_authorization") is True,
        "manifest_external_review_not_authorization": manifest.get("external_review_is_authorization") is False,
        "manifest_probe_not_executed": manifest.get("probe_execution_performed") is False,
        "s54_review_failed_captured": s54.get("status") == "review_failed_blocked",
        "s55_hardening_verified": s55.get("status") == "implemented_and_verified",
        "s55_probe_not_executed": s55.get("probe_execution_performed") is False,
        "s52_completed": s52.get("status") == "completed",
        "s52_ready_classification": _mapping(s52.get("readiness")).get("classification")
        == "ready_for_mandatory_region_counting_probe_review",
        "s52_probe_execution_disabled": s52.get("probe_execution_enabled") is False,
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
        "evidence/s54_failed_review_reply_summary.json",
        "evidence/s54_failed_review_reply_raw.md",
        "evidence/s55_s52_s53_readiness_hardening_implementation.json",
        "evidence/s48_signature_bucket_visibility_probe_review.json",
        "evidence/s49_signature_bucket_mandatory_scan_strategy.json",
        "evidence/s50_external_review_reply_summary.json",
        "evidence/s51_signature_bucket_mandatory_region_counting_implementation.json",
        "evidence/s52_signature_bucket_mandatory_region_counting_probe_readiness.json",
        "evidence/s52_future_command_template.json",
        "coordination/agents_s51_s52_gate_excerpt.md",
        "source_context/src/models/exact_coordinate_master_region_counting_snippets.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_readiness.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_external_review_package.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_rereview_package.py",
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_readiness.py",
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py",
        "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_rereview_package.py",
        "test_context/src/tests/test_master_mandatory_region_counting_snippets.py",
        "test_context/src/tests/test_exact_contract.py",
    ]


def _package_path_for_input(key: str) -> Path:
    mapping = {
        "s54_failed_review_summary": Path("evidence/s54_failed_review_reply_summary.json"),
        "s54_failed_review_raw": Path("evidence/s54_failed_review_reply_raw.md"),
        "s55_implementation": Path(
            "evidence/s55_s52_s53_readiness_hardening_implementation.json"
        ),
        "s48_probe_review": Path("evidence/s48_signature_bucket_visibility_probe_review.json"),
        "s49_strategy": Path("evidence/s49_signature_bucket_mandatory_scan_strategy.json"),
        "s50_review_summary": Path("evidence/s50_external_review_reply_summary.json"),
        "s51_implementation": Path(
            "evidence/s51_signature_bucket_mandatory_region_counting_implementation.json"
        ),
        "s52_readiness": Path(
            "evidence/s52_signature_bucket_mandatory_region_counting_probe_readiness.json"
        ),
        "s52_future_command": Path("evidence/s52_future_command_template.json"),
        "agents": Path("coordination/agents_s51_s52_gate_excerpt.md"),
        "exact_coordinate_master_source": Path(
            "source_context/src/models/exact_coordinate_master_region_counting_snippets.py"
        ),
        "s52_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_readiness.py"
        ),
        "s53_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py"
        ),
        "s54_package_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_external_review_package.py"
        ),
        "s56_package_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_rereview_package.py"
        ),
        "s52_tests": Path(
            "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_readiness.py"
        ),
        "s53_tests": Path(
            "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_review.py"
        ),
        "s56_tests": Path(
            "test_context/src/tests/test_phase3b_checkpoint_free_signature_bucket_mandatory_region_counting_probe_rereview_package.py"
        ),
        "focused_master_tests": Path(
            "test_context/src/tests/test_master_mandatory_region_counting_snippets.py"
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
        or "56_signature_bucket_mandatory_region_counting_probe_rereview_package"
        not in normalized
    ):
        raise ValueError(f"Refusing to write outside S56 re-review package namespace: {path}")


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
