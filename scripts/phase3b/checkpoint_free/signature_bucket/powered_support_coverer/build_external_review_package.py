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
S122_DIR = ARTIFACT_ROOT / "122_signature_bucket_powered_support_coverer_strategy"
S123_DIR = ARTIFACT_ROOT / "123_signature_bucket_powered_support_coverer_external_review_package"
DEFAULT_RUN_ID = "s122_powered_support_coverer_review_001"

S118_REVIEW = (
    ARTIFACT_ROOT
    / "118_signature_bucket_port_profile_cache_probe_review"
    / "signature_bucket_port_profile_cache_probe_review.json"
)
S119_REVIEW_SUMMARY = (
    ARTIFACT_ROOT
    / "119_signature_bucket_port_profile_cache_probe_external_review_package"
    / "s117_s118_port_profile_cache_probe_review_001"
    / "external_review_reply_summary.json"
)
S120_EXECUTION = (
    ARTIFACT_ROOT
    / "120_signature_bucket_port_profile_cache_probe_execution"
    / "signature_bucket_port_profile_cache_probe_execution.json"
)
S121_REPAIR = (
    ARTIFACT_ROOT
    / "121_port_profile_cache_probe_review_schema_repair"
    / "port_profile_cache_probe_review_schema_repair.json"
)

PACKAGE_INPUTS = {
    "agents_gate": WORKSPACE_ROOT / "AGENTS.md",
    "s118_probe_review": S118_REVIEW,
    "s119_review_summary": S119_REVIEW_SUMMARY,
    "s120_probe_execution": S120_EXECUTION,
    "s121_schema_repair": S121_REPAIR,
    "s122_strategy": S122_DIR / "signature_bucket_powered_support_coverer_strategy.json",
    "master_model_source": PROJECT_ROOT / "src" / "models" / "master_model.py",
    "exact_coordinate_master_source": PROJECT_ROOT / "src" / "models" / "exact_coordinate_master.py",
    "test_master": PROJECT_ROOT / "src" / "tests" / "test_master.py",
    "exact_contract_tests": PROJECT_ROOT / "src" / "tests" / "test_exact_contract.py",
    "s118_review_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "port_profile_cache" / "build_probe_review.py",
    "s123_builder": PROJECT_ROOT
    / "scripts" / "phase3b" / "checkpoint_free" / "signature_bucket" / "powered_support_coverer" / "build_external_review_package.py",
    "s118_review_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_port_profile_cache_probe_review.py",
    "s123_package_tests": PROJECT_ROOT
    / "src"
    / "tests"
    / "test_phase3b_checkpoint_free_signature_bucket_powered_support_coverer_external_review_package.py",
}

REVIEW_WORDING_REQUIREMENTS = (
    "needs review first",
    "review is not authorization",
    "if review passes request user/project-owner authorization",
)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    strategy = build_powered_support_coverer_strategy(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.strategy_output_dir),
        no_write=bool(args.no_write),
    )
    package = build_powered_support_coverer_external_review_package(
        project_root=PROJECT_ROOT,
        output_dir=_resolve_path(PROJECT_ROOT, args.package_output_dir),
        run_id=str(args.run_id),
        no_write=bool(args.no_write),
    )
    print("phase3b signature bucket powered support coverer strategy/package")
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
            "Build S122 powered-support-coverer hotspot strategy and S123 "
            "external review package."
        )
    )
    parser.add_argument("--strategy-output-dir", type=Path, default=S122_DIR)
    parser.add_argument("--package-output-dir", type=Path, default=S123_DIR)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def build_powered_support_coverer_strategy(
    *,
    project_root: Path,
    output_dir: Path,
    no_write: bool = False,
    s118_review_path: Path = S118_REVIEW,
    s119_review_summary_path: Path = S119_REVIEW_SUMMARY,
    s120_execution_path: Path = S120_EXECUTION,
    s121_repair_path: Path = S121_REPAIR,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    output_dir = _resolve_path(project_root, output_dir)
    _assert_strategy_namespace(output_dir)
    s118 = _load_json(_resolve_path(project_root, s118_review_path))
    s119 = _load_json(_resolve_path(project_root, s119_review_summary_path))
    s120 = _load_json(_resolve_path(project_root, s120_execution_path))
    s121 = _load_json(_resolve_path(project_root, s121_repair_path))
    classification = _classify_strategy(s118=s118, s119=s119, s120=s120, s121=s121)
    phase_seconds = _mapping(_mapping(s118.get("interpretation")).get("phase_seconds"))
    totals = _mapping(_mapping(s118.get("subphase_summary")).get("totals"))
    payload = {
        "schema": "phase3b-signature-bucket-powered-support-coverer-strategy/v0",
        "generated_at": _now(),
        "status": "completed" if classification != "manual_review_required" else "manual_review_required",
        "classification": classification,
        "project_root": str(project_root),
        "inputs": {
            "s118_probe_review": str(_resolve_path(project_root, s118_review_path)),
            "s119_review_summary": str(_resolve_path(project_root, s119_review_summary_path)),
            "s120_probe_execution": str(_resolve_path(project_root, s120_execution_path)),
            "s121_schema_repair": str(_resolve_path(project_root, s121_repair_path)),
        },
        "evidence": {
            "s119_review_verdict": s119.get("review_verdict"),
            "s120_status": s120.get("status"),
            "s121_status": s121.get("status"),
            "s118_status": s118.get("status"),
            "s118_classification": _mapping(s118.get("interpretation")).get("classification"),
            "dominant_phase": _mapping(s118.get("interpretation")).get("dominant_phase"),
            "dominant_seconds": _float(_mapping(s118.get("interpretation")).get("dominant_seconds")),
            "model_build_seconds": _float(s118.get("model_build_seconds")),
            "port_profile_cache_total_seconds": _float(
                _mapping(_mapping(s118.get("subphase_summary")).get("required_numeric")).get(
                    "index_pools_total_seconds"
                )
            ),
            "powered_support_coverer_seconds": _float(
                phase_seconds.get("powered_support_coverer_build")
            ),
            "compact_capacity_signature_store_seconds": _float(
                phase_seconds.get("compact_capacity_signature_store")
            ),
            "per_template_pose_cache_seconds": _float(
                phase_seconds.get("per_template_pose_cache_build")
            ),
            "support_coverer_scan_count": _int_or_none(totals.get("support_coverer_scan_count")),
            "support_coverer_candidate_count": _int_or_none(
                totals.get("support_coverer_candidate_count")
            ),
            "anchor_shape_group_count": _int_or_none(totals.get("anchor_shape_group_count")),
            "powered_template_count": _int_or_none(totals.get("powered_template_count")),
            "sensitive_path_clean": _mapping(s118.get("probe_safety")).get("sensitive_path_clean"),
            "checkpoint_written": s118.get("checkpoint_written"),
            "proof_source": s118.get("proof_source"),
        },
        "current_cost_shape": {
            "dominant_phase": "powered_support_coverer_build",
            "loop_location": "MasterPlacementModel._index_pools powered-template support-coverer loop",
            "loop_summary": [
                "for each powered non-pole template, group poses by anchor and shape token",
                "for each group, union cell_to_poles over representative pose cells",
                "filter coverers by checking disjointness against power_pole_cells",
                "write filtered coverers into per-pose power_index",
                "accumulate compact_item_counts_by_pole for later compact signature storage",
            ],
        },
        "future_patch_spec_for_review": {
            "review_kind": "default_off_stats_only_detailed_instrumentation",
            "env_var": "EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION",
            "target_scope": "MasterPlacementModel._index_pools powered support-coverer loop only",
            "default_off_contract": [
                "unset/false creates no new build_stats keys",
                "enabled path records diagnostics only",
                "no ModelProto, variable, constraint, hint, scheduler, proof, checkpoint, candidate-order, or production-default change",
                "invalid env values fail fast and mention the env var",
            ],
            "proposed_fields": [
                "phase_seconds.coverer_union_collect",
                "phase_seconds.coverer_disjoint_filter",
                "phase_seconds.power_index_expansion",
                "phase_seconds.compact_item_accumulation",
                "phase_seconds.stats_finalize",
                "totals.group_count",
                "totals.representative_cells_scanned",
                "totals.candidate_coverers_seen",
                "totals.filtered_coverers_kept",
                "totals.pose_indices_expanded",
                "totals.compact_items_accumulated",
                "top_slow_support_coverer_groups",
            ],
            "top_entry_fields": [
                "template",
                "anchor",
                "shape_token",
                "pose_count",
                "representative_cell_count",
                "candidate_coverer_count",
                "filtered_coverer_count",
                "elapsed_seconds",
            ],
        },
        "blocked_actions": [
            "do_not_implement_the_future_source_patch_in_s122_or_s123",
            "do_not_rerun_s120_probe",
            "do_not_run_runtime_solve",
            "do_not_run_67x20_or_full_wave",
            "do_not_write_canonical_checkpoints",
            "do_not_promote_local_results_to_proof",
            "do_not_change_production_defaults",
        ],
        "next_gate": {
            "status": "external_review_before_powered_support_coverer_source_patch",
            "if_review_passes": (
                "request user/project-owner authorization for the default-off stats-only "
                "powered support-coverer instrumentation patch"
            ),
        },
    }
    if not no_write:
        output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(output_dir / "signature_bucket_powered_support_coverer_strategy.json", payload)
        (output_dir / "signature_bucket_powered_support_coverer_strategy.md").write_text(
            render_powered_support_coverer_strategy_markdown(payload),
            encoding="utf-8",
        )
    return payload


def build_powered_support_coverer_external_review_package(
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
    strategy_path = S122_DIR / "signature_bucket_powered_support_coverer_strategy.json"
    if not strategy_path.exists() and not no_write:
        build_powered_support_coverer_strategy(project_root=project_root, output_dir=S122_DIR)
    before = build_sensitive_path_fingerprint(project_root)
    inputs = {key: _resolve_path(project_root, path) for key, path in PACKAGE_INPUTS.items()}
    manifest = _build_manifest(project_root, run_id, inputs)
    request_text = _review_request_text(run_id, manifest)
    package_hashes: dict[str, str | None] = {
        key: _sha256_file(path) if path.exists() and path.is_file() else None
        for key, path in inputs.items()
    }
    payload = {
        "schema": "phase3b-signature-bucket-powered-support-coverer-external-review-package/v0",
        "generated_at": _now(),
        "status": "completed",
        "run_id": run_id,
        "project_root": str(project_root),
        "output_dir": str(output_dir),
        "run_dir": str(run_dir),
        "package_kind": "review_only_powered_support_coverer_strategy_package",
        "probe_execution_enabled": False,
        "source_mutation_performed": False,
        "runtime_execution_performed": False,
        "checkpoint_written": False,
        "proof_source": False,
        "review_is_authorization": False,
        "authorization_required_next": True,
        "inputs": {key: str(path) for key, path in inputs.items()},
        "input_hashes": package_hashes,
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
                "do_not_rerun_s120_probe",
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
        validation = _validate_clean_extraction(run_dir, zip_path, payload["zip_sha256"], request_text)
        payload["clean_extraction_validation"] = validation
        after = build_sensitive_path_fingerprint(project_root)
        payload["sensitive_path_comparison"] = compare_sensitive_path_fingerprints(before, after)
        atomic_write_json(run_dir / "external_review_package_summary.json", payload)
        (run_dir / "external_review_package_summary.md").write_text(
            render_powered_support_coverer_package_markdown(payload),
            encoding="utf-8",
        )
    else:
        payload["zip_path"] = str(run_dir / f"{run_id}.zip")
        payload["zip_sha256"] = None
        payload["expanded_review_bundle_path"] = str(run_dir / f"{run_id}_expanded_review_bundle.md")
        payload["expanded_review_bundle_sha256"] = None
    return payload


def render_powered_support_coverer_strategy_markdown(payload: Mapping[str, Any]) -> str:
    evidence = _mapping(payload.get("evidence"))
    spec = _mapping(payload.get("future_patch_spec_for_review"))
    lines = [
        "# S122 Powered Support-Coverer Strategy",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Classification: `{payload.get('classification')}`",
        f"- Dominant phase: `{evidence.get('dominant_phase')}`",
        f"- Dominant seconds: `{evidence.get('dominant_seconds')}`",
        f"- Env proposed for future review: `{spec.get('env_var')}`",
        "",
        "S120/S121 show the port/profile cache probe is safe and classify the current hotspot as `powered_support_coverer_build`. The cost sits inside `MasterPlacementModel._index_pools()` while constructing coverer sets and compact signature inputs for powered non-pole templates.",
        "",
        "This artifact does not implement a source patch. It proposes a future default-off stats-only instrumentation patch so the next reviewed step can split the powered support-coverer loop into smaller subphases.",
    ]
    return "\n".join(lines) + "\n"


def render_powered_support_coverer_package_markdown(payload: Mapping[str, Any]) -> str:
    validation = _mapping(payload.get("clean_extraction_validation"))
    return (
        "# S123 Powered Support-Coverer External Review Package\n\n"
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
    s118: Mapping[str, Any],
    s119: Mapping[str, Any],
    s120: Mapping[str, Any],
    s121: Mapping[str, Any],
) -> str:
    if s119.get("review_verdict") != "pass":
        return "manual_review_required"
    if s121.get("status") != "implemented_and_verified":
        return "manual_review_required"
    if s118.get("status") != "completed":
        return "manual_review_required"
    if _mapping(s118.get("interpretation")).get("classification") != "powered_support_coverer_hotspot":
        return "manual_review_required"
    if _mapping(s118.get("probe_safety")).get("sensitive_path_clean") is not True:
        return "manual_review_required"
    if s120.get("status") not in {
        "completed_review_initially_inconclusive_then_repaired",
        "completed",
    }:
        return "manual_review_required"
    return "powered_support_coverer_detail_instrumentation_strategy_required"


def _review_request_text(run_id: str, manifest: Mapping[str, Any]) -> str:
    zip_filename = f"{run_id}.zip"
    zip_sha = manifest.get("zip_sha256", "TO_BE_FILLED_AFTER_ZIP")
    return "\n".join(
        [
            "Review Request: Phase3B S122 Powered Support-Coverer Detail Instrumentation Strategy",
            "",
            f"Uploaded package: {zip_filename}",
            f"SHA256: {zip_sha}",
            "",
            "This needs review first. review is not authorization. if review passes request user/project-owner authorization for the future default-off source patch.",
            "",
            "Please review S120/S121 evidence and S122 strategy only. Do not treat this package as source-patch authorization, proof evidence, runtime evidence, or checkpoint evidence.",
            "",
            "Questions:",
            "1. Does S120/S121 support classifying the next hotspot as powered_support_coverer_build inside MasterPlacementModel._index_pools()?",
            "2. Is the proposed default-off env gate EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION narrow enough?",
            "3. Are the proposed fields enough to split coverer union collection, disjoint filtering, power_index expansion, compact item accumulation, and stats finalization?",
            "4. Does the default-off stats-only scope avoid ModelProto, variable, constraint, hint, scheduler, proof, checkpoint, runtime, and production-default risk?",
            "5. If review passes, is the correct verdict only safe to request user/project-owner authorization, not authorization itself?",
        ]
    ) + "\n"


def _build_manifest(project_root: Path, run_id: str, inputs: Mapping[str, Path]) -> dict[str, Any]:
    entries = []
    for key, source_path in sorted(inputs.items()):
        entries.append(
            {
                "key": key,
                "source_path": str(source_path),
                "filename": _package_filename_for_key(key, source_path),
                "exists": source_path.exists(),
                "sha256": _sha256_file(source_path) if source_path.exists() and source_path.is_file() else None,
            }
        )
    return {
        "schema": "phase3b-powered-support-coverer-review-package-manifest/v0",
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
    evidence_dir = package_root / "evidence"
    code_dir = package_root / "code_context"
    test_dir = package_root / "test_context"
    for entry in manifest.get("entries", []):
        if not isinstance(entry, Mapping):
            continue
        key = str(entry.get("key"))
        source_path = inputs.get(key)
        if source_path is None or not source_path.exists() or not source_path.is_file():
            continue
        dest_dir = evidence_dir
        if key.endswith("_source") or key.endswith("_builder") or key == "agents_gate":
            dest_dir = code_dir
        if key.endswith("_tests") or key in {"test_master", "exact_contract_tests"}:
            dest_dir = test_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_dir / str(entry.get("filename")))
    manifest_path = package_root / "manifest.json"
    manifest_copy = json.loads(json.dumps(manifest))
    atomic_write_json(manifest_path, manifest_copy)


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
                chunks.extend([f"## {subdir}/{filename}", "", "```", path.read_text(encoding="utf-8", errors="replace"), "```", ""])
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


def _package_filename_for_key(key: str, path: Path) -> str:
    if key == "agents_gate":
        return "AGENTS.md"
    return path.name


def _assert_strategy_namespace(output_dir: Path) -> None:
    normalized = str(output_dir).replace("\\", "/")
    if "122_signature_bucket_powered_support_coverer_strategy" not in normalized:
        raise ValueError(f"S122 strategy namespace violation: {output_dir}")


def _assert_package_namespace(output_dir: Path) -> None:
    normalized = str(output_dir).replace("\\", "/")
    if "123_signature_bucket_powered_support_coverer_external_review_package" not in normalized:
        raise ValueError(f"S123 package namespace violation: {output_dir}")


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
