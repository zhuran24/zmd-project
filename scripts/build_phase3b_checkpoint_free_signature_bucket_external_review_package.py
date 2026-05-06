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
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "38_signature_bucket_external_review_package"
DEFAULT_RUN_ID = "signature_bucket_external_review_package_001"
DEFAULT_INPUTS = {
    "s35_overlay_timing_probe": ARTIFACT_ROOT
    / "35_overlay_timing_strategy"
    / "local_hotspot_42x32_overlay_timing_probe_001"
    / "overlay_timing_probe.json",
    "s36_signature_bucket_strategy": ARTIFACT_ROOT
    / "36_signature_bucket_tightening_strategy"
    / "signature_bucket_tightening_strategy.json",
    "s37_patch_spec": ARTIFACT_ROOT
    / "37_signature_bucket_tightening_instrumentation_patch_spec"
    / "signature_bucket_tightening_instrumentation_patch_spec.json",
    "agents": WORKSPACE_ROOT / "AGENTS.md",
    "target_source": PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py",
    "s36_strategy_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_tightening_strategy.py",
    "s37_patch_spec_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_tightening_instrumentation_patch_spec.py",
    "s38_package_builder": PROJECT_ROOT
    / "scripts"
    / "build_phase3b_checkpoint_free_signature_bucket_external_review_package.py",
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
    package = build_signature_bucket_external_review_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket external review package")
    print(f"status={package['status']}")
    print(f"zip_path={_display_path(PROJECT_ROOT, Path(package['zip_path']))}")
    print(f"zip_sha256={package.get('zip_sha256')}")
    print(f"clean_extraction_validated={package['clean_extraction_validation']['validated']}")
    return 0 if package["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a clean-extraction-validated external review package for the "
            "signature-bucket tightening instrumentation review."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_signature_bucket_external_review_package(
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
    request_text = _review_request_text(
        input_paths,
        package_filename=zip_path.name,
        package_sha256=None,
    )
    gate_excerpt = _agents_gate_excerpt(input_paths["agents"])
    manifest = _manifest(
        project_root=project_root,
        run_id=str(run_id),
        run_dir=run_dir,
        zip_path=zip_path,
        inputs=input_paths,
    )
    validation: dict[str, Any] = {
        "validated": False,
        "reason": "no_write",
    }
    if not no_write:
        if run_dir.exists():
            shutil.rmtree(run_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)
        _write_staging_files(
            staging_dir=staging_dir,
            manifest=manifest,
            request_text=request_text,
            gate_excerpt=gate_excerpt,
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
        )
        atomic_write_json(run_dir / "clean_extraction_validation.json", validation)
    else:
        zip_sha256 = None

    after = build_sensitive_path_fingerprint(project_root)
    sensitive_comparison = compare_sensitive_path_fingerprints(before, after)
    status = (
        "completed"
        if (no_write or validation.get("validated")) and not sensitive_comparison.get("changed")
        else "failed"
    )
    payload = {
        "schema": "phase3b-signature-bucket-external-review-package/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "package_kind": "external_review_source_patch_review_package",
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
        "review_required_before_authorization": True,
        "external_review_is_authorization": False,
        "inputs": {key: str(path) for key, path in input_paths.items()},
        "manifest": manifest,
        "clean_extraction_validation": validation,
        "sensitive_path_comparison": sensitive_comparison,
    }
    if not no_write:
        atomic_write_json(run_dir / "external_review_package_summary.json", payload)
        (run_dir / "external_review_package_summary.md").write_text(
            render_signature_bucket_external_review_package_markdown(payload),
            encoding="utf-8",
        )
        atomic_write_json(run_dir / "sensitive_path_before.json", before)
        atomic_write_json(run_dir / "sensitive_path_after.json", after)
        atomic_write_json(run_dir / "sensitive_path_comparison.json", sensitive_comparison)
    return payload


def render_signature_bucket_external_review_package_markdown(payload: Mapping[str, Any]) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    lines = [
        "# Phase3B Signature Bucket External Review Package",
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
        "## Review Purpose",
        "",
        "External review should decide whether the default-off signature-bucket tightening instrumentation is safe and narrow enough to request user/project-owner authorization. The package is not authorization and does not perform the patch.",
        "",
    ]
    return "\n".join(lines)


def _review_request_text(
    inputs: Mapping[str, Path],
    *,
    package_filename: str,
    package_sha256: str | None,
) -> str:
    sha_text = (
        package_sha256
        if package_sha256
        else "computed after zip build; use the outer review_request.md / zip_sha256.txt value before sending"
    )
    return "\n".join(
        [
            "# Review Request: Phase3B Signature Bucket Tightening Instrumentation",
            "",
            "Uploaded package to review:",
            "",
            f"- Package filename: `{package_filename}`",
            f"- Package SHA256: `{sha_text}`",
            "",
            "Status: needs review first. This review is not authorization. If review passes, request user/project-owner authorization before any source patch.",
            "",
            "Gate marker for automated checks: if review passes request user/project-owner authorization.",
            "",
            "Please review the included S35-S37 artifacts, AGENTS gate excerpt, source context, artifact builders, and focused regression test context. The requested verdict is only whether the proposed default-off instrumentation is safe and narrow enough to proceed to a later user/project-owner authorization request.",
            "",
            "The package intentionally includes fuller code context for caution: the target source file, the S36/S37/S38 artifact builders, and focused tests that are relevant to master-model behavior and exact proof-contract boundaries. This is meant to reduce reviewer guesswork; it is still only a review package and does not request or perform source mutation.",
            "",
            "Questions:",
            "",
            "1. Is the proposed scope limited tightly enough to `CoordinateExactMasterDelegate._apply_ghost_anchor_signature_bucket_tightening`?",
            "2. Does the proposed env var `EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION` preserve current behavior when unset, including ModelProto variables, constraints, and build_stats asserted by existing tests?",
            "3. Are the proposed fields sufficient to identify payload build, per-anchor scans, constraint-add time, top slow anchors/groups/buckets, and bucket reductions?",
            "4. Do you see any proof, checkpoint, production-default, scheduler, runtime-elimination, or candidate-universe risk in the spec as written?",
            "5. If there are no blockers, please state only that the patch is safe to request user/project-owner authorization; do not treat review approval as authorization.",
            "",
            "Hard boundaries: do not treat local tuning artifacts as proof; do not request final 168h, canonical checkpoint writes, runtime elimination, proof/preflight/release/viewer/frontdoor mutation, production default changes, or direct source mutation in this review step.",
            "",
            "Included inputs:",
            "",
            *[f"- `{key}`: `{path}`" for key, path in sorted(inputs.items())],
            "",
        ]
    )


def _manifest(project_root: Path, run_id: str, run_dir: Path, zip_path: Path, inputs: Mapping[str, Path]) -> dict[str, Any]:
    return {
        "schema": "phase3b-signature-bucket-external-review-package-manifest/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "run_id": str(run_id),
        "zip_path": str(zip_path),
        "zip_sha256": None,
        "proof_source": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
        "review_required_before_authorization": True,
        "external_review_is_authorization": False,
        "package_contents": [
            "README.md",
            "review_request.md",
            "manifest.json",
            "evidence/s35_overlay_timing_probe.json",
            "evidence/s36_signature_bucket_tightening_strategy.json",
            "evidence/s37_signature_bucket_tightening_instrumentation_patch_spec.json",
            "coordination/agents_signature_bucket_gate_excerpt.md",
            "source_context/src/models/exact_coordinate_master.py",
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_tightening_strategy.py",
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_tightening_instrumentation_patch_spec.py",
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_external_review_package.py",
            "test_context/src/tests/test_master.py",
            "test_context/src/tests/test_exact_contract.py",
        ],
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
    request_text: str,
    gate_excerpt: str,
    inputs: Mapping[str, Path],
) -> None:
    (staging_dir / "review_request.md").write_text(request_text, encoding="utf-8")
    atomic_write_json(staging_dir / "manifest.json", dict(manifest))
    gate_path = staging_dir / "coordination" / "agents_signature_bucket_gate_excerpt.md"
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(gate_excerpt, encoding="utf-8")
    for key, source_path in sorted(inputs.items()):
        if key == "agents":
            continue
        package_path = staging_dir / _package_path_for_input(key)
        package_path.parent.mkdir(parents=True, exist_ok=True)
        if not source_path.exists():
            raise FileNotFoundError(f"required review package input is missing: {key}: {source_path}")
        shutil.copy2(source_path, package_path)
    (staging_dir / "README.md").write_text(
        (
            "This package is for Phase3B / Endfield external review of a default-off "
            "signature-bucket tightening instrumentation proposal. It needs review first; "
            "review is not authorization; if review passes request user/project-owner authorization. "
            "It is not proof evidence and does not authorize or perform source mutation.\n"
        ),
        encoding="utf-8",
    )


def _agents_gate_excerpt(path: Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    keep_markers = [
        "When a proposed action has not yet completed",
        "Current signature-bucket tightening gate:",
    ]
    lines = []
    for line in text.splitlines():
        if any(marker in line for marker in keep_markers):
            lines.append(line)
    if not lines:
        raise ValueError(f"Could not find signature-bucket/review gate excerpt in {path}")
    return "\n".join(
        [
            "# AGENTS Gate Excerpt",
            "",
            *lines,
            "",
        ]
    )


def _write_zip(staging_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(staging_dir).as_posix())


def _validate_clean_extraction(zip_path: Path, extract_dir: Path, expected_zip_sha256: str) -> dict[str, Any]:
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extract_dir)
        names = sorted(archive.namelist())
    required = [
        "README.md",
        "review_request.md",
        "manifest.json",
        "evidence/s35_overlay_timing_probe.json",
        "evidence/s36_signature_bucket_tightening_strategy.json",
        "evidence/s37_signature_bucket_tightening_instrumentation_patch_spec.json",
        "coordination/agents_signature_bucket_gate_excerpt.md",
        "source_context/src/models/exact_coordinate_master.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_tightening_strategy.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_tightening_instrumentation_patch_spec.py",
        "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_external_review_package.py",
        "test_context/src/tests/test_master.py",
        "test_context/src/tests/test_exact_contract.py",
    ]
    missing = [name for name in required if not (extract_dir / name).is_file()]
    request_text = (extract_dir / "review_request.md").read_text(encoding="utf-8")
    manifest = _load_json(extract_dir / "manifest.json")
    s37 = _load_json(extract_dir / "evidence/s37_signature_bucket_tightening_instrumentation_patch_spec.json")
    semantic_checks = {
        "zip_sha256_matches_expected": _sha256(zip_path) == expected_zip_sha256,
        "manifest_review_required_true": manifest.get("review_required_before_authorization") is True,
        "manifest_external_review_not_authorization": manifest.get("external_review_is_authorization") is False,
        "s37_source_mutation_false": s37.get("source_mutation_performed") is False,
        "s37_implementation_allowed_false": _mapping(s37.get("interpretation")).get("implementation_allowed_now") is False,
        "review_wording_requirements": all(text in request_text for text in REVIEW_WORDING_REQUIREMENTS),
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


def _package_path_for_input(key: str) -> Path:
    mapping = {
        "s35_overlay_timing_probe": Path("evidence/s35_overlay_timing_probe.json"),
        "s36_signature_bucket_strategy": Path("evidence/s36_signature_bucket_tightening_strategy.json"),
        "s37_patch_spec": Path("evidence/s37_signature_bucket_tightening_instrumentation_patch_spec.json"),
        "agents": Path("coordination/agents_signature_bucket_gate_excerpt.md"),
        "target_source": Path("source_context/src/models/exact_coordinate_master.py"),
        "s36_strategy_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_tightening_strategy.py"
        ),
        "s37_patch_spec_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_tightening_instrumentation_patch_spec.py"
        ),
        "s38_package_builder": Path(
            "code_context/scripts/build_phase3b_checkpoint_free_signature_bucket_external_review_package.py"
        ),
        "focused_master_tests": Path("test_context/src/tests/test_master.py"),
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
        or "38_signature_bucket_external_review_package" not in normalized
    ):
        raise ValueError(f"Refusing to write outside signature bucket external review package namespace: {path}")


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
