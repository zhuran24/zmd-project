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
S126_REVIEW = (
    ARTIFACT_ROOT
    / "126_signature_bucket_powered_support_coverer_probe_review"
    / "signature_bucket_powered_support_coverer_probe_review.json"
)
S127_REVIEW_SUMMARY = (
    ARTIFACT_ROOT
    / "127_signature_bucket_powered_support_coverer_probe_external_review_package"
    / "s125_s126_powered_support_coverer_probe_review_001"
    / "external_review_reply_summary.json"
)
S128_EXECUTION = (
    ARTIFACT_ROOT
    / "128_signature_bucket_powered_support_coverer_probe_execution"
    / "signature_bucket_powered_support_coverer_probe_execution.json"
)
S124_IMPLEMENTATION = (
    ARTIFACT_ROOT
    / "124_signature_bucket_powered_support_coverer_instrumentation_implementation"
    / "signature_bucket_powered_support_coverer_instrumentation_implementation.json"
)
S129_DIR = ARTIFACT_ROOT / "129_signature_bucket_powered_support_coverer_compact_item_strategy"
S130_DIR = (
    ARTIFACT_ROOT
    / "130_signature_bucket_powered_support_coverer_compact_item_external_review_package"
)
DEFAULT_RUN_ID = "s128_compact_item_accumulation_review_001"

REVIEW_WORDING_REQUIREMENTS = (
    "needs review first",
    "review is not authorization",
    "if review passes request user/project-owner authorization",
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_compact_item_accumulation_strategy(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.strategy_output_dir),
        no_write=bool(args.no_write),
    )
    package = build_compact_item_accumulation_external_review_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.package_output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b powered support-coverer compact-item strategy/package")
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
            "Build S129 powered support-coverer compact-item strategy and "
            "S130 external review package."
        )
    )
    parser.add_argument("--strategy-output-dir", type=Path, default=S129_DIR)
    parser.add_argument("--package-output-dir", type=Path, default=S130_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_compact_item_accumulation_strategy(
    *,
    project_root: Path,
    output_dir: Path,
    no_write: bool = False,
    s126_review_path: Path = S126_REVIEW,
    s127_review_summary_path: Path = S127_REVIEW_SUMMARY,
    s128_execution_path: Path = S128_EXECUTION,
    s124_implementation_path: Path = S124_IMPLEMENTATION,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = _resolve_path(project_root, output_dir)
    _assert_strategy_namespace(output_dir)
    s126 = _load_json(_resolve_path(project_root, s126_review_path))
    s127 = _load_json(_resolve_path(project_root, s127_review_summary_path))
    s128 = _load_json(_resolve_path(project_root, s128_execution_path))
    s124 = _load_json(_resolve_path(project_root, s124_implementation_path))
    classification = _classify_strategy(s126=s126, s127=s127, s128=s128, s124=s124)
    subphase = _mapping(s126.get("subphase_summary"))
    phase_seconds = _mapping(subphase.get("phase_seconds"))
    totals = _mapping(subphase.get("totals"))
    interpretation = _mapping(s126.get("interpretation"))
    payload = {
        "schema": "phase3b-powered-support-coverer-compact-item-strategy/v0",
        "generated_at": _now(),
        "status": "completed" if classification != "manual_review_required" else "manual_review_required",
        "classification": classification,
        "project_root": str(project_root),
        "inputs": {
            "s126_probe_review": str(_resolve_path(project_root, s126_review_path)),
            "s127_review_summary": str(_resolve_path(project_root, s127_review_summary_path)),
            "s128_probe_execution": str(_resolve_path(project_root, s128_execution_path)),
            "s124_implementation": str(_resolve_path(project_root, s124_implementation_path)),
        },
        "evidence": {
            "s127_review_verdict": s127.get("review_verdict"),
            "s128_status": s128.get("status"),
            "s124_status": s124.get("status"),
            "s126_status": s126.get("status"),
            "s126_classification": interpretation.get("classification"),
            "dominant_phase": interpretation.get("dominant_phase"),
            "dominant_seconds": _float(interpretation.get("dominant_seconds")),
            "model_build_seconds": _float(s126.get("model_build_seconds")),
            "phase_seconds": dict(sorted(phase_seconds.items())),
            "candidate_coverer_count": _int_or_none(totals.get("candidate_coverer_count")),
            "filtered_coverer_count": _int_or_none(totals.get("filtered_coverer_count")),
            "compact_item_update_count": _int_or_none(totals.get("compact_item_update_count")),
            "group_count": _int_or_none(totals.get("group_count")),
            "pose_count": _int_or_none(totals.get("pose_count")),
            "representative_cell_count": _int_or_none(totals.get("representative_cell_count")),
            "sensitive_path_clean": _mapping(s126.get("probe_safety")).get("sensitive_path_clean"),
            "checkpoint_written": s126.get("checkpoint_written"),
            "proof_source": s126.get("proof_source"),
        },
        "current_cost_shape": {
            "dominant_phase": "compact_item_accumulation",
            "loop_location": "MasterPlacementModel._index_pools powered support-coverer loop",
            "loop_summary": [
                "for each powered support group, iterate all filtered coverers",
                "compute compact item key from anchor minus power-pole anchor plus shape token",
                "increment compact_item_counts_by_pole[pole_idx][compact_item] by group pose count",
                "later expand those multiplicities into compact_signature_by_pole for compact capacity signature storage",
            ],
            "observed_scale": {
                "compact_item_update_count": _int_or_none(totals.get("compact_item_update_count")),
                "filtered_coverer_count": _int_or_none(totals.get("filtered_coverer_count")),
                "group_count": _int_or_none(totals.get("group_count")),
            },
        },
        "future_patch_spec_for_review": {
            "review_kind": "default_off_compact_item_accumulation_optimization_or_deeper_instrumentation",
            "suggested_env_var": "EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION",
            "target_scope": (
                "only the compact_item_counts_by_pole accumulation inside "
                "MasterPlacementModel._index_pools powered support-coverer loop"
            ),
            "default_off_contract": [
                "unset/false preserves current data structures, build_stats, ModelProto, variables, constraints, hints, candidate order, proof/checkpoint paths, runtime behavior, and production defaults",
                "enabled path must produce byte-equivalent compact capacity signatures for supported fixtures",
                "unsupported or ambiguous geometry/data-shape cases must fall back to the existing legacy accumulation loop",
                "invalid env values must fail fast and mention the env var",
            ],
            "optimization_hypotheses_for_review": [
                "batch repeated compact item increments per group instead of per-coverer defaultdict writes when this can be proven equivalent",
                "use local aliases or temporary per-group counters to reduce nested dictionary churn without changing sorted compact signature output",
                "optionally keep stats-only subfields for batchable vs fallback update counts and top slow compact-item groups",
            ],
            "required_tests_for_future_patch": [
                "default-off ModelProto text, variable count, constraint count, constraint type counts, and build_stats remain identical",
                "enabled compact signatures are exactly equal to legacy for representative powered templates",
                "enabled final ModelProto and constraints are identical to legacy baseline",
                "fallback path is exercised for unsupported shapes or non-equivalence cases",
                "checkpoint/proof/release/viewer/frontdoor fingerprints remain unchanged",
            ],
        },
        "blocked_actions": [
            "do_not_implement_the_future_source_patch_in_s129_or_s130",
            "do_not_rerun_s128_probe",
            "do_not_run_runtime_solve",
            "do_not_run_67x20_or_full_wave",
            "do_not_write_canonical_checkpoints",
            "do_not_promote_local_results_to_proof",
            "do_not_change_production_defaults",
        ],
        "next_gate": {
            "status": "external_review_before_compact_item_accumulation_source_patch",
            "if_review_passes": (
                "request user/project-owner authorization for a narrow default-off compact-item "
                "accumulation optimization or deeper instrumentation patch"
            ),
        },
    }
    if not no_write:
        output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(output_dir / "signature_bucket_powered_support_coverer_compact_item_strategy.json", payload)
        (output_dir / "signature_bucket_powered_support_coverer_compact_item_strategy.md").write_text(
            render_strategy_markdown(payload),
            encoding="utf-8",
        )
    return payload


def build_compact_item_accumulation_external_review_package(
    *,
    project_root: Path,
    output_dir: Path,
    run_id: str = DEFAULT_RUN_ID,
    no_write: bool = False,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = _resolve_path(project_root, output_dir)
    _assert_package_namespace(output_dir)
    run_dir = output_dir / run_id
    strategy_path = S129_DIR / "signature_bucket_powered_support_coverer_compact_item_strategy.json"
    if not strategy_path.exists() and not no_write:
        build_compact_item_accumulation_strategy(project_root=project_root, output_dir=S129_DIR)
    before = build_sensitive_path_fingerprint(project_root)
    inputs = _package_inputs(project_root)
    manifest = _build_manifest(project_root, run_id, inputs)
    request_text = _review_request_text(run_id, manifest)
    payload = {
        "schema": "phase3b-powered-support-coverer-compact-item-external-review-package/v0",
        "generated_at": _now(),
        "status": "completed",
        "run_id": run_id,
        "project_root": str(project_root),
        "output_dir": str(output_dir),
        "run_dir": str(run_dir),
        "package_kind": "review_only_compact_item_accumulation_strategy_package",
        "probe_execution_enabled": False,
        "source_mutation_performed": False,
        "runtime_execution_performed": False,
        "checkpoint_written": False,
        "proof_source": False,
        "review_is_authorization": False,
        "authorization_required_next": True,
        "inputs": {key: str(path) for key, path in inputs.items()},
        "manifest": manifest,
        "review_request": request_text,
        "clean_extraction_validation": {
            "validated": False,
            "package_hash_matches": False,
            "manifest_exists": False,
            "manifest_entry_count": 0,
            "request_text_contains_required_wording": False,
        },
        "sensitive_path_comparison": None,
        "next_gate": {
            "status": "upload_to_chatgpt_project_for_external_review",
            "blocked_actions": [
                "do_not_implement_source_patch_before_review_pass",
                "do_not_rerun_s128_probe",
                "do_not_run_runtime_solve",
                "do_not_write_canonical_checkpoints",
                "do_not_promote_local_results_to_proof",
                "do_not_change_production_defaults",
            ],
        },
    }
    if not no_write:
        run_dir.mkdir(parents=True, exist_ok=True)
        package_root = run_dir / "package_contents"
        if package_root.exists():
            shutil.rmtree(package_root)
        _populate_package(package_root, inputs, manifest, request_text)
        zip_path = run_dir / f"{run_id}.zip"
        if zip_path.exists():
            zip_path.unlink()
        _zip_dir(package_root, zip_path)
        zip_sha = _sha256_file(zip_path)
        manifest["zip_sha256"] = zip_sha
        request_text = _review_request_text(run_id, manifest)
        atomic_write_json(run_dir / "manifest.json", manifest)
        (run_dir / "review_request.md").write_text(request_text, encoding="utf-8")
        (run_dir / "zip_sha256.txt").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="utf-8")
        expanded_bundle = run_dir / f"{run_id}_expanded_review_bundle.md"
        expanded_bundle.write_text(
            _expanded_review_bundle(package_root, manifest, request_text),
            encoding="utf-8",
        )
        payload["zip_path"] = str(zip_path)
        payload["zip_sha256"] = zip_sha
        payload["expanded_review_bundle_path"] = str(expanded_bundle)
        payload["expanded_review_bundle_sha256"] = _sha256_file(expanded_bundle)
        validation = _validate_clean_extraction(run_dir, zip_path, zip_sha, request_text)
        payload["clean_extraction_validation"] = validation
        after = build_sensitive_path_fingerprint(project_root)
        payload["sensitive_path_comparison"] = compare_sensitive_path_fingerprints(before, after)
        atomic_write_json(run_dir / "external_review_package_summary.json", payload)
        (run_dir / "external_review_package_summary.md").write_text(
            render_package_markdown(payload),
            encoding="utf-8",
        )
    else:
        payload["zip_path"] = str(run_dir / f"{run_id}.zip")
        payload["zip_sha256"] = None
        payload["expanded_review_bundle_path"] = str(run_dir / f"{run_id}_expanded_review_bundle.md")
        payload["expanded_review_bundle_sha256"] = None
    return payload


def render_strategy_markdown(payload: Mapping[str, Any]) -> str:
    evidence = _mapping(payload.get("evidence"))
    spec = _mapping(payload.get("future_patch_spec_for_review"))
    return "\n".join(
        [
            "# S129 Powered Support-Coverer Compact-Item Strategy",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Classification: `{payload.get('classification')}`",
            f"- Dominant phase: `{evidence.get('dominant_phase')}`",
            f"- Dominant seconds: `{evidence.get('dominant_seconds')}`",
            f"- Suggested env for future reviewed patch: `{spec.get('suggested_env_var')}`",
            "",
            "S128 exposed the next powered support-coverer hotspot as compact item accumulation. This artifact is strategy/review input only; it does not implement a source patch and does not authorize another probe.",
        ]
    ) + "\n"


def render_package_markdown(payload: Mapping[str, Any]) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    return (
        "# S130 Compact-Item External Review Package\n\n"
        f"- Status: `{payload.get('status')}`\n"
        f"- Zip: `{Path(str(payload.get('zip_path'))).name}`\n"
        f"- SHA256: `{payload.get('zip_sha256')}`\n"
        f"- Expanded bundle: `{Path(str(payload.get('expanded_review_bundle_path'))).name}`\n"
        f"- Expanded SHA256: `{payload.get('expanded_review_bundle_sha256')}`\n"
        f"- Clean extraction validated: `{validation.get('validated')}`\n\n"
        "This package is review-only. Review is not authorization.\n"
    )


def _classify_strategy(
    *,
    s126: Mapping[str, Any],
    s127: Mapping[str, Any],
    s128: Mapping[str, Any],
    s124: Mapping[str, Any],
) -> str:
    if s127.get("review_verdict") != "pass":
        return "manual_review_required"
    if s128.get("status") != "completed":
        return "manual_review_required"
    if s124.get("status") not in {"implemented_and_verified", "completed"}:
        return "manual_review_required"
    if s126.get("status") != "completed":
        return "manual_review_required"
    if _mapping(s126.get("interpretation")).get("classification") != "compact_item_accumulation_hotspot":
        return "manual_review_required"
    if _mapping(s126.get("probe_safety")).get("sensitive_path_clean") is not True:
        return "manual_review_required"
    return "powered_support_coverer_compact_item_accumulation_strategy_required"


def _review_request_text(run_id: str, manifest: Mapping[str, Any]) -> str:
    zip_filename = f"{run_id}.zip"
    zip_sha = manifest.get("zip_sha256", "TO_BE_FILLED_AFTER_ZIP")
    return "\n".join(
        [
            "Review Request: Phase3B S129 Powered Support-Coverer Compact Item Strategy",
            "",
            f"Uploaded package: {zip_filename}",
            f"SHA256: {zip_sha}",
            "",
            "This needs review first. review is not authorization. if review passes request user/project-owner authorization for the future default-off source patch.",
            "",
            "Please review S128/S126 evidence and S129 strategy only. Do not treat this package as source-patch authorization, proof evidence, runtime evidence, or checkpoint evidence.",
            "",
            "Questions:",
            "1. Does S128 support classifying compact_item_accumulation as the next powered support-coverer hotspot?",
            "2. Is the proposed future scope narrow enough if limited to compact_item_counts_by_pole accumulation inside MasterPlacementModel._index_pools()?",
            "3. Is a default-off env gate such as EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION appropriate?",
            "4. Are the equivalence/fallback/test requirements sufficient before any implementation?",
            "5. Does the proposed scope avoid ModelProto, variable, constraint, hint, scheduler, proof, checkpoint, runtime, and production-default risks?",
            "6. If review passes, is the verdict only safe to request user/project-owner authorization, not authorization itself?",
        ]
    ) + "\n"


def _package_inputs(project_root: Path) -> dict[str, Path]:
    return {
        "agents_gate": WORKSPACE_ROOT / "AGENTS.md",
        "s124_implementation": S124_IMPLEMENTATION,
        "s126_probe_review": S126_REVIEW,
        "s127_review_summary": S127_REVIEW_SUMMARY,
        "s128_probe_execution": S128_EXECUTION,
        "s129_strategy": S129_DIR / "signature_bucket_powered_support_coverer_compact_item_strategy.json",
        "master_model_source": PROJECT_ROOT / "src" / "models" / "master_model.py",
        "exact_coordinate_master_source": PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py",
        "test_master": PROJECT_ROOT / "src" / "tests" / "test_master.py",
        "exact_contract_tests": PROJECT_ROOT / "src" / "tests" / "test_exact_contract.py",
        "s126_review_builder": PROJECT_ROOT
        / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "powered_support_coverer" / "build_probe_review.py",
        "s130_builder": PROJECT_ROOT
        / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "powered_support_coverer" / "build_compact_item_external_review_package.py",
        "s126_review_tests": PROJECT_ROOT
        / "src"
        / "tests"
        / "test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_probe_review.py",
        "s130_package_tests": PROJECT_ROOT
        / "src"
        / "tests"
        / "test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_compact_item_external_review_package.py",
    }


def _build_manifest(project_root: Path, run_id: str, inputs: Mapping[str, Path]) -> dict[str, Any]:
    entries = []
    for key, source_path in sorted(inputs.items()):
        entries.append(
            {
                "key": key,
                "source_path": str(source_path),
                "filename": "AGENTS.md" if key == "agents_gate" else source_path.name,
                "exists": source_path.exists(),
                "sha256": _sha256_file(source_path) if source_path.exists() and source_path.is_file() else None,
            }
        )
    return {
        "schema": "phase3b-powered-support-coverer-compact-item-review-package-manifest/v0",
        "generated_at": _now(),
        "run_id": run_id,
        "project_root": str(project_root),
        "zip_filename": f"{run_id}.zip",
        "zip_sha256": "TO_BE_FILLED_AFTER_ZIP",
        "entries": entries,
    }


def _populate_package(
    package_root: Path,
    inputs: Mapping[str, Path],
    manifest: Mapping[str, Any],
    request_text: str,
) -> None:
    package_root.mkdir(parents=True, exist_ok=True)
    for entry in manifest.get("entries", []):
        if not isinstance(entry, Mapping):
            continue
        key = str(entry.get("key"))
        source_path = inputs.get(key)
        if source_path is None or not source_path.exists() or not source_path.is_file():
            continue
        subdir = "evidence"
        if key.endswith("_source") or key.endswith("_builder") or key == "agents_gate":
            subdir = "code_context"
        if key.endswith("_tests") or key in {"test_master", "exact_contract_tests"}:
            subdir = "test_context"
        dest_dir = package_root / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_dir / str(entry.get("filename")))
    atomic_write_json(package_root / "manifest.json", manifest)
    (package_root / "review_request.md").write_text(request_text, encoding="utf-8")


def _expanded_review_bundle(
    package_root: Path,
    manifest: Mapping[str, Any],
    request_text: str,
) -> str:
    chunks = [
        "# Expanded Review Bundle",
        "",
        "This text source mirrors the review package for ChatGPT project review when zip inspection is unreliable.",
        "",
        "## review_request.md",
        "",
        "```",
        request_text,
        "```",
        "",
        "## manifest.json",
        "",
        "```json",
        json.dumps(manifest, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    for entry in manifest.get("entries", []):
        if not isinstance(entry, Mapping):
            continue
        filename = str(entry.get("filename"))
        for subdir in ("evidence", "code_context", "test_context"):
            path = package_root / subdir / filename
            if path.exists():
                chunks.extend(
                    [
                        f"## {subdir}/{filename}",
                        "",
                        "```",
                        path.read_text(encoding="utf-8", errors="replace"),
                        "```",
                        "",
                    ]
                )
                break
    return "\n".join(chunks)


def _zip_dir(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(source_dir).as_posix())


def _validate_clean_extraction(
    run_dir: Path,
    zip_path: Path,
    expected_sha: str,
    request_text: str,
) -> dict[str, Any]:
    extract_dir = run_dir / "clean_extraction"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    manifest_path = extract_dir / "manifest.json"
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}
    validation = {
        "validated": True,
        "package_hash_matches": _sha256_file(zip_path) == expected_sha,
        "manifest_exists": manifest_path.exists(),
        "manifest_entry_count": len(manifest.get("entries", [])) if isinstance(manifest, Mapping) else 0,
        "request_text_contains_required_wording": all(
            phrase in request_text for phrase in REVIEW_WORDING_REQUIREMENTS
        ),
    }
    atomic_write_json(run_dir / "clean_extraction_validation.json", validation)
    return validation


def _assert_strategy_namespace(output_dir: Path) -> None:
    if "129_signature_bucket_powered_support_coverer_compact_item_strategy" not in str(output_dir).replace("\\", "/"):
        raise ValueError(f"S129 strategy namespace violation: {output_dir}")


def _assert_package_namespace(output_dir: Path) -> None:
    if "130_signature_bucket_powered_support_coverer_compact_item_external_review_package" not in str(output_dir).replace("\\", "/"):
        raise ValueError(f"S130 package namespace violation: {output_dir}")


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return data


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _int_or_none(value: Any) -> int | None:
    return int(value) if isinstance(value, int) else None


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
