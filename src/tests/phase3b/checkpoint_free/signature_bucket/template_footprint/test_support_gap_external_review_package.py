from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.template_footprint.build_support_gap_external_review_package import (
    DEFAULT_RUN_ID,
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_template_footprint_support_gap_external_review_package,
)


def test_template_footprint_support_gap_external_review_package_builds_clean_zip(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_template_footprint_support_gap_external_review_package(
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


def test_template_footprint_support_gap_external_review_package_manifest_contains_context(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)

    package = build_signature_bucket_template_footprint_support_gap_external_review_package(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        run_id="custom_s77_review_package",
        inputs=inputs,
    )

    with zipfile.ZipFile(Path(package["zip_path"]), "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        s76 = json.loads(
            archive.read(
                "evidence/s76_signature_bucket_template_footprint_support_gap_strategy.json"
            ).decode("utf-8")
        )
        request_text = archive.read("review_request.md").decode("utf-8")

    assert "review_request.md" in names
    assert "evidence/s74_external_review_reply_summary.json" in names
    assert "evidence/s75_signature_bucket_template_footprint_probe_execution.json" in names
    assert "evidence/s73_signature_bucket_template_footprint_probe_review.json" in names
    assert "evidence/s76_signature_bucket_template_footprint_support_gap_strategy.json" in names
    assert "source_context/src/models/exact_coordinate_master.py" in names
    assert "test_context/src/tests/test_master.py" in names
    assert (
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/template_footprint/build_support_gap_strategy.py"
        in names
    )
    assert (
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/template_footprint/test_support_gap_strategy.py"
        in names
    )
    assert manifest["review_required_before_authorization"] is True
    assert manifest["external_review_is_authorization"] is False
    assert manifest["probe_executed"] is False
    assert s76["interpretation"]["classification"] == (
        "template_footprint_support_not_used_strategy_required"
    )
    assert "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION" in request_text


def test_template_footprint_support_gap_external_review_package_no_write(tmp_path: Path) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_template_footprint_support_gap_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
        no_write=True,
    )

    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["reason"] == "no_write"
    assert not (output_dir / DEFAULT_RUN_ID).exists()


def test_template_footprint_support_gap_external_review_package_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="S77 external review package namespace"):
        build_signature_bucket_template_footprint_support_gap_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_package_inputs(tmp_path: Path) -> dict[str, Path]:
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "s74_review_summary": inputs_dir / "s74_review_summary.json",
        "s74_review_raw": inputs_dir / "s74_review_raw.md",
        "s75_execution": inputs_dir / "s75_execution.json",
        "s73_review": inputs_dir / "s73_review.json",
        "s71_implementation": inputs_dir / "s71_implementation.json",
        "s76_strategy": inputs_dir / "s76_strategy.json",
        "agents": inputs_dir / "AGENTS.md",
        "exact_coordinate_master_source": inputs_dir / "exact_coordinate_master.py",
        "test_master": inputs_dir / "test_master.py",
        "exact_contract_tests": inputs_dir / "test_exact_contract.py",
        "s71_probe_readiness_builder": inputs_dir / "s72_builder.py",
        "s73_probe_review_builder": inputs_dir / "s73_builder.py",
        "s74_package_builder": inputs_dir / "s74_builder.py",
        "s76_strategy_builder": inputs_dir / "s76_builder.py",
        "s77_package_builder": inputs_dir / "s77_builder.py",
        "s71_tests": inputs_dir / "test_s72.py",
        "s73_tests": inputs_dir / "test_s73.py",
        "s74_tests": inputs_dir / "test_s74.py",
        "s76_tests": inputs_dir / "test_s76.py",
        "s77_tests": inputs_dir / "test_s77.py",
    }
    paths["s74_review_summary"].write_text(
        json.dumps(
            {
                "status": "completed",
                "review_verdict": "pass",
                "review_is_authorization": False,
                "authorization_required_next": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s74_review_raw"].write_text(
        "This single future enabled 42x32 no-solve template-footprint probe scope is safe to request user/project-owner authorization; this review is not authorization.\n",
        encoding="utf-8",
    )
    paths["s75_execution"].write_text(
        json.dumps(
            {
                "status": "completed",
                "s73_classification": "template_footprint_support_not_used",
                "safety": {"sensitive_path_changed": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s73_review"].write_text(
        json.dumps(
            {
                "status": "completed",
                "interpretation": {
                    "classification": "template_footprint_support_not_used",
                    "template_footprint_support_used": 0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s71_implementation"].write_text(
        json.dumps({"status": "implemented_and_verified"}) + "\n",
        encoding="utf-8",
    )
    paths["s76_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": "template_footprint_support_not_used_strategy_required"
                },
                "future_diagnostic_spec": {
                    "env_var": "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION"
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
                "- Current S74 external review result and S75 no-solve probe state.",
                "- template_footprint_support_not_used.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["exact_coordinate_master_source"].write_text(
        "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT\nmandatory_template_footprint_support_used\n",
        encoding="utf-8",
    )
    paths["test_master"].write_text("# full test_master fixture\n", encoding="utf-8")
    paths["s76_strategy_builder"].write_text(
        "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION\n",
        encoding="utf-8",
    )
    for key in (
        "exact_contract_tests",
        "s71_probe_readiness_builder",
        "s73_probe_review_builder",
        "s74_package_builder",
        "s77_package_builder",
        "s71_tests",
        "s73_tests",
        "s74_tests",
        "s76_tests",
        "s77_tests",
    ):
        paths[key].write_text(f"# fixture for {key}\n", encoding="utf-8")
    return paths


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "77_signature_bucket_template_footprint_support_gap_external_review_package"
    )
