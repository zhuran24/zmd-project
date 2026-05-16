from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.template_footprint.build_support_external_review_package import (
    DEFAULT_RUN_ID,
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_template_footprint_support_external_review_package,
)


def test_template_footprint_support_external_review_package_builds_clean_zip(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_template_footprint_support_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
    )

    run_dir = output_dir / DEFAULT_RUN_ID
    zip_path = Path(package["zip_path"])
    assert package["status"] == "completed"
    assert zip_path.is_file()
    assert package["clean_extraction_validation"]["validated"] is True
    assert package["sensitive_path_comparison"]["changed"] is False
    request_text = (run_dir / "review_request.md").read_text(encoding="utf-8")
    assert zip_path.name in request_text
    assert package["zip_sha256"] in request_text
    for phrase in REVIEW_WORDING_REQUIREMENTS:
        assert phrase in request_text


def test_template_footprint_support_external_review_package_manifest_contains_context(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)

    package = build_signature_bucket_template_footprint_support_external_review_package(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        run_id="custom_s70_review_package",
        inputs=inputs,
    )

    with zipfile.ZipFile(Path(package["zip_path"]), "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        s64 = json.loads(
            archive.read(
                "evidence/s64_signature_bucket_fallback_reason_probe_review.json"
            ).decode("utf-8")
        )
        s69 = json.loads(
            archive.read(
                "evidence/s69_signature_bucket_template_footprint_support_strategy.json"
            ).decode("utf-8")
        )
        source_snippet = archive.read(
            "source_context/src/models/exact_coordinate_master_template_footprint_snippets.py"
        ).decode("utf-8")

    assert "review_request.md" in names
    assert "evidence/s68_signature_bucket_fallback_reason_probe_execution.json" in names
    assert "evidence/s68_overlay_timing_probe.json" in names
    assert "evidence/s64_signature_bucket_fallback_reason_probe_review.json" in names
    assert "evidence/s69_signature_bucket_template_footprint_support_strategy.json" in names
    assert (
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/template_footprint/test_support_strategy.py"
        in names
    )
    assert (
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/template_footprint/test_support_external_review_package.py"
        in names
    )
    assert manifest["review_required_before_authorization"] is True
    assert manifest["external_review_is_authorization"] is False
    assert s64["interpretation"]["classification"] == "unsupported_footprint_dominates"
    assert (
        s69["interpretation"]["classification"]
        == "unsupported_template_footprint_support_strategy_required"
    )
    assert s69["source_mutation_performed"] is False
    assert "def _pose_has_template_rect_footprint" in source_snippet
    assert "def _mandatory_region_counting_payload" in source_snippet
    assert "def _apply_ghost_anchor_signature_bucket_tightening" in source_snippet


def test_template_footprint_support_external_review_package_no_write(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_template_footprint_support_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
        no_write=True,
    )

    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["reason"] == "no_write"
    assert not (output_dir / DEFAULT_RUN_ID).exists()


def test_template_footprint_support_external_review_package_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="S70 external review package namespace"):
        build_signature_bucket_template_footprint_support_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_package_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "s67_external_review_summary": inputs_dir / "s67_external_review_summary.json",
        "s51_implementation": inputs_dir / "s51.json",
        "s62_implementation": inputs_dir / "s62.json",
        "s68_execution": inputs_dir / "s68_execution.json",
        "s68_probe": inputs_dir / "s68_probe.json",
        "s64_review": inputs_dir / "s64_review.json",
        "s69_strategy": inputs_dir / "s69_strategy.json",
        "agents": inputs_dir / "AGENTS.md",
        "exact_coordinate_master_source": inputs_dir / "exact_coordinate_master.py",
        "s64_builder": inputs_dir / "s64_builder.py",
        "s69_builder": inputs_dir / "s69_builder.py",
        "s70_package_builder": inputs_dir / "s70_package_builder.py",
        "s62_focused_tests": inputs_dir / "test_master.py",
        "s64_tests": inputs_dir / "test_s64.py",
        "s69_tests": inputs_dir / "test_s69.py",
        "s70_tests": inputs_dir / "test_s70.py",
        "exact_contract_tests": inputs_dir / "test_exact_contract.py",
    }
    paths["s67_external_review_summary"].write_text(
        json.dumps(
            {
                "status": "review_passed_safe_to_request_authorization",
                "review_verdict": "pass",
                "review_is_authorization": False,
                "authorization_required_next": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s51_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "source_patch": {
                    "env_var": "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s62_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "source_patch": {
                    "env_var": "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s68_execution"].write_text(json.dumps(_s68_payload()) + "\n", encoding="utf-8")
    paths["s68_probe"].write_text(
        json.dumps(
            {
                "status": "completed",
                "execute_no_solve": True,
                "cp_solver_solve_called": False,
                "checkpoint_written": False,
                "proof_source": False,
                "runtime_execution_performed": False,
                "sensitive_path_comparison": {
                    "schema": "phase3b-sensitive-path-fingerprint-comparison/v0",
                    "changed": False,
                    "changed_paths": [],
                    "changed_entries": [],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s64_review"].write_text(json.dumps(_s64_payload()) + "\n", encoding="utf-8")
    paths["s69_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": "unsupported_template_footprint_support_strategy_required",
                    "implementation_allowed_now": False,
                },
                "future_patch_spec": {
                    "env_var": "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT"
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["agents"].write_text(
        "\n".join(
            [
                "## GPT Project Review Standing Authorization",
                "- Current S67 external review result: pass, review is not authorization.",
                "- Current S68 fallback-reason no-solve probe result: unsupported_footprint_dominates.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["exact_coordinate_master_source"].write_text(_source_fixture(), encoding="utf-8")
    paths["s62_focused_tests"].write_text(_test_master_fixture(), encoding="utf-8")
    for key in (
        "s64_builder",
        "s69_builder",
        "s70_package_builder",
        "s64_tests",
        "s69_tests",
        "s70_tests",
        "exact_contract_tests",
    ):
        paths[key].write_text(f"# fixture for {key}\n", encoding="utf-8")
    return paths


def _s68_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "probe": {
            "run_id": "local_hotspot_42x32_signature_bucket_fallback_reason_inst_no_solve_001",
            "overlay_timing_probe_json": "probe.json",
            "model_build_seconds": 38.14,
            "signature_bucket_tightening_seconds": 28.78,
        },
        "safety": {
            "execute_no_solve": True,
            "no_solve": True,
            "cp_solver_solve_called": False,
            "runtime_execution_performed": False,
            "checkpoint_written": False,
            "proof_source": False,
            "sensitive_path_comparison_changed": False,
        },
        "s64_review": {
            "status": "completed",
            "classification": "unsupported_footprint_dominates",
            "dominant_reason": "unsupported_or_missing_template_footprint",
            "dominant_reason_count": 6786,
            "dominant_reason_ratio": 1.0,
            "fallback_reason_total": 6786,
            "mandatory_scan_seconds": 27.09,
            "mandatory_region_counting_attempts": 21489,
            "mandatory_region_counting_used": 14703,
            "mandatory_region_counting_fallbacks": 6786,
        },
    }


def _s64_payload() -> dict[str, object]:
    return {
        "status": "completed",
        "interpretation": {
            "classification": "unsupported_footprint_dominates",
            "dominant_reason": "unsupported_or_missing_template_footprint",
            "dominant_reason_count": 6786,
            "dominant_reason_ratio": 1.0,
            "fallback_reason_total": 6786,
            "mandatory_scan_seconds": 27.097,
        },
        "signature_instrumentation": {
            "present": True,
            "fallback_reason_visibility": "fallback_reason_instrumentation_visible",
            "fallback_reasons": {"unsupported_or_missing_template_footprint": 6786},
            "top_fallback_entries": [
                {
                    "rect_idx": 1058,
                    "anchor": {"x": 27, "y": 5},
                    "group_id_or_template": "group::manufacturing_6x4::filling_capsule::13",
                    "bucket_id": "__all__",
                    "reason": "unsupported_or_missing_template_footprint",
                    "legacy_scan_count": 1344,
                    "legacy_pose_hits": 124160,
                    "elapsed_seconds": 0.008,
                }
            ],
        },
    }


def _source_fixture() -> str:
    return (
        "\n".join(
            [
                "class CoordinateExactMasterDelegate:",
                "    def _pose_has_template_rect_footprint(self):",
                "        return False",
                "",
                "    def _mandatory_region_counting_payload(self):",
                "        return {'reason': 'unsupported_pose_footprint'}",
                "",
                "    def _mandatory_region_blocked_counts_for_domain(self):",
                "        return {}",
                "",
                "    def _apply_ghost_anchor_signature_bucket_tightening(self):",
                "        def _fallback_reason_category(reason):",
                "            return 'unsupported_or_missing_template_footprint'",
                "        for cell in domain.get('cells', []):",
                "            pass",
            ]
        )
        + "\n"
    )


def _test_master_fixture() -> str:
    return (
        "\n".join(
            [
                "def test_ghost_signature_bucket_mandatory_region_counting_enabled_matches_legacy_supported_fixture():",
                "    assert True",
                "",
                "def test_ghost_signature_bucket_mandatory_region_counting_falls_back_for_unsupported_footprints():",
                "    assert True",
                "",
                "def test_ghost_signature_bucket_mandatory_region_fallback_instrumentation_default_off_is_absent():",
                "    assert True",
                "",
                "def test_ghost_signature_bucket_mandatory_region_fallback_instrumentation_supported_fixture_has_empty_output():",
                "    assert True",
                "",
                "def test_exact_core_overlay_signature_bucket_mandatory_region_fallback_instrumentation_matches_legacy():",
                "    assert True",
            ]
        )
        + "\n"
    )


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "70_signature_bucket_template_footprint_support_external_review_package"
    )
