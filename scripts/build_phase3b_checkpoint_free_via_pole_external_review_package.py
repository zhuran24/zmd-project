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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.sensitive_path_audit import (  # noqa: E402
    build_sensitive_path_fingerprint,
    compare_sensitive_path_fingerprints,
)
from src.search.exact_campaign import atomic_write_json  # noqa: E402

ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "phase3b_local_13900ks_tuning_20260430"
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "33_via_pole_external_review_package"
DEFAULT_RUN_ID = "via_pole_external_review_package_001"
DEFAULT_INPUTS = {
    "s29_shape_inventory_comparison": ARTIFACT_ROOT
    / "29_candidate_shape_inventory_comparison"
    / "candidate_shape_inventory_comparison_exec_001"
    / "candidate_shape_inventory_comparison.json",
    "s30_shape_scaling_review": ARTIFACT_ROOT
    / "30_candidate_shape_scaling_review"
    / "candidate_shape_scaling_review.json",
    "s31_patch_spec": ARTIFACT_ROOT
    / "31_via_pole_shape_instrumentation_patch_spec"
    / "via_pole_shape_instrumentation_patch_spec.json",
    "s32_authorization_packet": ARTIFACT_ROOT
    / "32_via_pole_instrumentation_authorization_packet"
    / "via_pole_instrumentation_authorization_packet.json",
    "next_decision": ARTIFACT_ROOT / "09_checkpoint_free_scoreboard" / "checkpoint_free_next_decision.json",
    "target_source": PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py",
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    package = build_via_pole_external_review_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b via-pole external review package")
    print(f"status={package['status']}")
    print(f"zip_path={_display_path(PROJECT_ROOT, Path(package['zip_path']))}")
    print(f"clean_extraction_validated={package['clean_extraction_validation']['validated']}")
    return 0 if package["status"] == "completed" else 1


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a clean-extraction-validated external review package for the via-pole instrumentation authorization decision."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_via_pole_external_review_package(
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
    zip_path = run_dir / f"{run_id}.zip"
    request_text = _review_request_text(input_paths)
    manifest = _manifest(project_root, run_id, run_dir, zip_path, input_paths)
    validation: dict[str, Any] = {
        "validated": False,
        "reason": "no_write",
    }
    if not no_write:
        if run_dir.exists():
            shutil.rmtree(run_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)
        _write_staging_files(staging_dir, manifest, request_text, input_paths, project_root)
        _write_zip(staging_dir, zip_path)
        manifest["zip_sha256"] = _sha256(zip_path)
        atomic_write_json(staging_dir / "package_manifest.json", manifest)
        _write_zip(staging_dir, zip_path)
        manifest["zip_sha256"] = _sha256(zip_path)
        atomic_write_json(run_dir / "package_manifest.json", manifest)
        (run_dir / "review_request.md").write_text(request_text, encoding="utf-8")
        validation = _validate_clean_extraction(zip_path, run_dir / "clean_extract")
        atomic_write_json(run_dir / "clean_extraction_validation.json", validation)
    after = build_sensitive_path_fingerprint(project_root)
    sensitive_comparison = compare_sensitive_path_fingerprints(before, after)
    status = (
        "completed"
        if (no_write or validation.get("validated")) and not sensitive_comparison.get("changed")
        else "failed"
    )
    payload = {
        "schema": "phase3b-via-pole-external-review-package/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "package_kind": "external_review_source_patch_authorization_package",
        "project_root": str(project_root),
        "run_id": str(run_id),
        "run_dir": str(run_dir),
        "zip_path": str(zip_path),
        "zip_sha256": manifest.get("zip_sha256"),
        "fresh_solver_run_started": False,
        "main_py_executed": False,
        "exact_campaign_used": False,
        "cp_solver_solve_called": False,
        "proof_source": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
        "candidate_universe_changed": False,
        "production_profile_changed": False,
        "inputs": {key: str(path) for key, path in input_paths.items()},
        "manifest": manifest,
        "clean_extraction_validation": validation,
        "sensitive_path_comparison": sensitive_comparison,
    }
    if not no_write:
        atomic_write_json(run_dir / "external_review_package_summary.json", payload)
        (run_dir / "external_review_package_summary.md").write_text(
            render_external_review_package_markdown(payload),
            encoding="utf-8",
        )
        atomic_write_json(run_dir / "sensitive_path_before.json", before)
        atomic_write_json(run_dir / "sensitive_path_after.json", after)
        atomic_write_json(run_dir / "sensitive_path_comparison.json", sensitive_comparison)
    return payload


def render_external_review_package_markdown(payload: Mapping[str, Any]) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    lines = [
        "# Phase3B Via-Pole External Review Package",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Zip: `{payload.get('zip_path')}`",
        f"- SHA256: `{payload.get('zip_sha256')}`",
        f"- Clean extraction validated: `{validation.get('validated')}`",
        "- Source mutation performed: `false`",
        "- CpSolver.Solve called: `false`",
        "- Proof source: `false`",
        "- Checkpoint written: `false`",
        "",
        "## Review Purpose",
        "",
        "External review should decide whether the default-off via-pole shape instrumentation source patch is safe to authorize. The package itself does not authorize or perform that patch.",
        "",
    ]
    return "\n".join(lines)


def _review_request_text(inputs: Mapping[str, Path]) -> str:
    return "\n".join(
        [
            "# Review Request: Phase3B Via-Pole Shape Instrumentation Authorization",
            "",
            "Please review the included S29-S32 artifacts and source context. The requested verdict is only about whether it is safe to authorize a default-off instrumentation patch for `CoordinateExactMasterDelegate._apply_ghost_anchor_power_capacity_screen`.",
            "",
            "Questions:",
            "",
            "1. Are there blockers to implementing the default-off instrumentation described in S31/S32?",
            "2. Does the proposed env var `EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION` preserve production behavior when unset?",
            "3. Are the validation steps sufficient before running a no-solve 42x32 instrumented inventory?",
            "4. Is there any lower-risk no-source alternative that should be tried first?",
            "",
            "Hard boundaries: do not treat local tuning artifacts as proof; do not request final 168h, canonical checkpoint writes, runtime elimination, proof/preflight/release/viewer/frontdoor mutation, or production default changes.",
            "",
            "Included inputs:",
            "",
            *[f"- `{key}`: `{path}`" for key, path in sorted(inputs.items())],
            "",
        ]
    )


def _manifest(project_root: Path, run_id: str, run_dir: Path, zip_path: Path, inputs: Mapping[str, Path]) -> dict[str, Any]:
    return {
        "schema": "phase3b-via-pole-external-review-package-manifest/v0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "run_id": str(run_id),
        "zip_path": str(zip_path),
        "zip_sha256": None,
        "proof_source": False,
        "checkpoint_written": False,
        "source_mutation_performed": False,
        "package_contents": [
            "review_request.md",
            "package_manifest.json",
            "evidence/s29_candidate_shape_inventory_comparison.json",
            "evidence/s30_candidate_shape_scaling_review.json",
            "evidence/s31_via_pole_shape_instrumentation_patch_spec.json",
            "evidence/s32_via_pole_instrumentation_authorization_packet.json",
            "evidence/checkpoint_free_next_decision.json",
            "source_context/src/models/exact_coordinate_master.py",
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
    staging_dir: Path,
    manifest: Mapping[str, Any],
    request_text: str,
    inputs: Mapping[str, Path],
    project_root: Path,
) -> None:
    (staging_dir / "review_request.md").write_text(request_text, encoding="utf-8")
    atomic_write_json(staging_dir / "package_manifest.json", dict(manifest))
    for key, source_path in sorted(inputs.items()):
        package_path = staging_dir / _package_path_for_input(key)
        package_path.parent.mkdir(parents=True, exist_ok=True)
        if not source_path.exists():
            raise FileNotFoundError(f"required review package input is missing: {key}: {source_path}")
        shutil.copy2(source_path, package_path)
    readme = staging_dir / "README.md"
    readme.write_text(
        "This package is for Phase3B / Endfield external review of a default-off via-pole instrumentation authorization decision. It is not proof evidence and does not authorize source mutation by itself.\n",
        encoding="utf-8",
    )


def _write_zip(staging_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(staging_dir).as_posix())


def _validate_clean_extraction(zip_path: Path, extract_dir: Path) -> dict[str, Any]:
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extract_dir)
        names = sorted(archive.namelist())
    required = [
        "review_request.md",
        "package_manifest.json",
        "evidence/s29_candidate_shape_inventory_comparison.json",
        "evidence/s30_candidate_shape_scaling_review.json",
        "evidence/s31_via_pole_shape_instrumentation_patch_spec.json",
        "evidence/s32_via_pole_instrumentation_authorization_packet.json",
        "evidence/checkpoint_free_next_decision.json",
        "source_context/src/models/exact_coordinate_master.py",
    ]
    missing = [name for name in required if not (extract_dir / name).is_file()]
    parsed = {
        "s31": _load_json(extract_dir / "evidence/s31_via_pole_shape_instrumentation_patch_spec.json"),
        "s32": _load_json(extract_dir / "evidence/s32_via_pole_instrumentation_authorization_packet.json"),
    }
    semantic_checks = {
        "s31_source_mutation_false": parsed["s31"].get("source_mutation_performed") is False,
        "s31_implementation_allowed_false": _mapping(parsed["s31"].get("interpretation")).get("implementation_allowed_now") is False,
        "s32_authorization_required_true": _mapping(parsed["s32"].get("authorization")).get("authorization_required") is True,
        "s32_implementation_allowed_false": _mapping(parsed["s32"].get("authorization")).get("implementation_allowed_now") is False,
    }
    return {
        "validated": not missing and all(semantic_checks.values()),
        "zip_path": str(zip_path),
        "extract_dir": str(extract_dir),
        "entry_count": len(names),
        "missing_required_entries": missing,
        "semantic_checks": semantic_checks,
    }


def _package_path_for_input(key: str) -> Path:
    mapping = {
        "s29_shape_inventory_comparison": Path("evidence/s29_candidate_shape_inventory_comparison.json"),
        "s30_shape_scaling_review": Path("evidence/s30_candidate_shape_scaling_review.json"),
        "s31_patch_spec": Path("evidence/s31_via_pole_shape_instrumentation_patch_spec.json"),
        "s32_authorization_packet": Path("evidence/s32_via_pole_instrumentation_authorization_packet.json"),
        "next_decision": Path("evidence/checkpoint_free_next_decision.json"),
        "target_source": Path("source_context/src/models/exact_coordinate_master.py"),
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
        or "33_via_pole_external_review_package" not in normalized
    ):
        raise ValueError(f"Refusing to write outside via-pole external review package namespace: {path}")


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
