from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.region_counting_fallback.build_external_review_package import (
    DEFAULT_RUN_ID,
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_region_counting_fallback_external_review_package,
)


def test_region_counting_fallback_external_review_package_builds_clean_zip(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_region_counting_fallback_external_review_package(
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


def test_region_counting_fallback_external_review_package_manifest_contains_context(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)

    package = build_signature_bucket_region_counting_fallback_external_review_package(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        run_id="custom_s61_review_package",
        inputs=inputs,
    )

    with zipfile.ZipFile(Path(package["zip_path"]), "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        s60 = json.loads(
            archive.read(
                "evidence/s60_signature_bucket_region_counting_fallback_strategy.json"
            ).decode("utf-8")
        )
        source_snippet = archive.read(
            "source_context/src/models/exact_coordinate_master_region_fallback_snippets.py"
        ).decode("utf-8")

    assert "review_request.md" in names
    assert "evidence/s59_overlay_timing_probe.json" in names
    assert "evidence/s53_signature_bucket_mandatory_region_counting_probe_review.json" in names
    assert "evidence/s60_signature_bucket_region_counting_fallback_strategy.json" in names
    assert (
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/region_counting_fallback/test_strategy.py"
        in names
    )
    assert (
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/region_counting_fallback/test_external_review_package.py"
        in names
    )
    assert manifest["review_required_before_authorization"] is True
    assert manifest["external_review_is_authorization"] is False
    assert (
        s60["interpretation"]["classification"]
        == "mandatory_region_counting_effective_but_fallback_residual_strategy_required"
    )
    assert s60["source_mutation_performed"] is False
    assert "def _mandatory_region_counting_payload" in source_snippet
    assert "def _mandatory_region_blocked_counts_for_domain" in source_snippet
    assert "def _apply_ghost_anchor_signature_bucket_tightening" in source_snippet


def test_region_counting_fallback_external_review_package_no_write_does_not_create_run_dir(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_region_counting_fallback_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
        no_write=True,
    )

    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["reason"] == "no_write"
    assert not (output_dir / DEFAULT_RUN_ID).exists()


def test_region_counting_fallback_external_review_package_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="S61 external review package namespace"):
        build_signature_bucket_region_counting_fallback_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_package_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "s50_external_review_summary": inputs_dir / "s50_external_review_summary.json",
        "s51_implementation": inputs_dir / "s51.json",
        "s59_probe": inputs_dir / "s59_probe.json",
        "s53_review": inputs_dir / "s53_review.json",
        "s60_strategy": inputs_dir / "s60_strategy.json",
        "agents": inputs_dir / "AGENTS.md",
        "exact_coordinate_master_source": inputs_dir / "exact_coordinate_master.py",
        "s53_builder": inputs_dir / "s53_builder.py",
        "s60_builder": inputs_dir / "s60_builder.py",
        "s61_package_builder": inputs_dir / "s61_package_builder.py",
        "s51_focused_tests": inputs_dir / "test_master.py",
        "s53_tests": inputs_dir / "test_s53.py",
        "s60_tests": inputs_dir / "test_s60.py",
        "s61_tests": inputs_dir / "test_s61.py",
        "exact_contract_tests": inputs_dir / "test_exact_contract.py",
    }
    paths["s50_external_review_summary"].write_text(
        json.dumps(
            {
                "status": "review_passed_safe_to_request_authorization",
                "review_verdict": {
                    "scope_safe_to_request_authorization": True,
                    "review_is_authorization": False,
                },
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
    paths["s59_probe"].write_text(
        json.dumps(
            {
                "status": "completed",
                "execute_no_solve": True,
                "cp_solver_solve_called": False,
                "checkpoint_written": False,
                "proof_source": False,
                "runtime_execution_performed": False,
                "sensitive_path_comparison": {"changed": False, "changed_paths": []},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s53_review"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {
                    "classification": "mandatory_region_counting_effective"
                },
                "signature_instrumentation": {
                    "present": True,
                    "region_counting_status": "mandatory_region_counting_used",
                    "phase_seconds": {"per_anchor_mandatory_scan": 32.27},
                    "totals": {
                        "mandatory_region_counting_attempts": 21489,
                        "mandatory_region_counting_used": 14703,
                        "mandatory_region_counting_fallbacks": 6786,
                    },
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s60_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": "mandatory_region_counting_effective_but_fallback_residual_strategy_required",
                    "implementation_allowed_now": False,
                },
                "future_patch_spec": {
                    "env_var": "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION"
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
                "- Current S51 mandatory-region-counting source patch state: implemented.",
                "- Current S58 external review result: passed, not authorization.",
                "- Current S59 enabled no-solve probe result: mandatory_region_counting_effective.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["exact_coordinate_master_source"].write_text(
        "\n".join(
            [
                "def _mandatory_region_counting_payload(self):",
                "    return {}",
                "",
                "def _mandatory_region_blocked_counts_for_domain(self):",
                "    return {}",
                "",
                "class CoordinateExactMasterDelegate:",
                "    def _apply_ghost_anchor_signature_bucket_tightening(self):",
                "        for cell in domain.get(\"cells\", []):",
                "            blocked_pose_indices = set()",
                "        signature_tightening_instrumentation = tightening_stats.get(",
                "            \"signature_tightening_instrumentation\"",
                "        )",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s51_focused_tests"].write_text(
        "\n".join(
            [
                "def test_ghost_signature_bucket_mandatory_region_counting_enabled_matches_legacy_supported_fixture():",
                "    assert True",
                "",
                "def test_ghost_signature_bucket_mandatory_region_counting_falls_back_for_unsupported_footprints():",
                "    assert True",
                "",
                "def test_exact_core_overlay_signature_bucket_mandatory_region_counting_matches_legacy():",
                "    assert True",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for key in (
        "s53_builder",
        "s60_builder",
        "s61_package_builder",
        "s53_tests",
        "s60_tests",
        "s61_tests",
        "exact_contract_tests",
    ):
        paths[key].write_text(f"# fixture for {key}\n", encoding="utf-8")
    return paths


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "61_signature_bucket_region_counting_fallback_external_review_package"
    )
