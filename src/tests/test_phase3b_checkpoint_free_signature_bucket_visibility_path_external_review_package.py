from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.build_phase3b_checkpoint_free_signature_bucket_visibility_path_external_review_package import (
    build_signature_bucket_visibility_path_external_review_package,
)


def test_signature_bucket_visibility_path_external_review_package_builds_and_validates(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "45_signature_bucket_visibility_path_external_review_package"
    )

    package = build_signature_bucket_visibility_path_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        run_id="signature_bucket_visibility_path_external_review_package_001",
        inputs=inputs,
    )

    assert package["status"] == "completed"
    assert package["source_mutation_performed"] is False
    assert package["checkpoint_written"] is False
    assert package["proof_source"] is False
    assert package["clean_extraction_validation"]["validated"] is True
    assert package["zip_sha256"]
    assert Path(package["zip_path"]).exists()
    request = Path(package["final_review_request_path"]).read_text(encoding="utf-8")
    assert "signature_bucket_visibility_path_external_review_package_001.zip" in request
    assert package["zip_sha256"] in request
    assert "needs review first" in request
    assert "review is not authorization" in request
    assert "if review passes request user/project-owner authorization" in request


def test_signature_bucket_visibility_path_external_review_package_zip_contains_context(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "45_signature_bucket_visibility_path_external_review_package"
    )
    package = build_signature_bucket_visibility_path_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
    )

    with zipfile.ZipFile(package["zip_path"], "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        s44 = json.loads(
            archive.read("evidence/s44_signature_bucket_visibility_path_strategy.json").decode(
                "utf-8"
            )
        )
        exact_snippet = archive.read(
            "source_context/src/models/exact_coordinate_master_signature_visibility_snippets.py"
        ).decode("utf-8")
        master_snippet = archive.read(
            "source_context/src/models/master_model_from_exact_core_snippet.py"
        ).decode("utf-8")

    assert "review_request.md" in names
    assert "test_context/src/tests/test_master_signature_bucket_snippet.py" in names
    assert manifest["review_required_before_authorization"] is True
    assert manifest["external_review_is_authorization"] is False
    assert (
        s44["interpretation"]["classification"]
        == "exact_core_overlay_instrumentation_visibility_gap"
    )
    assert "_apply_ghost_anchor_signature_bucket_tightening" in exact_snippet
    assert "_add_global_valid_inequalities" in exact_snippet
    assert "def from_exact_core" in master_snippet


def test_signature_bucket_visibility_path_external_review_package_no_write(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "45_signature_bucket_visibility_path_external_review_package"
    )

    package = build_signature_bucket_visibility_path_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=inputs,
        no_write=True,
    )

    assert package["status"] == "completed"
    assert package["zip_sha256"] is None
    assert not output_dir.exists()


def test_signature_bucket_visibility_path_external_review_package_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    inputs = _write_package_inputs(tmp_path)

    with pytest.raises(ValueError, match="S45 external review package namespace"):
        build_signature_bucket_visibility_path_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            inputs=inputs,
            no_write=True,
        )


def _write_package_inputs(tmp_path: Path) -> dict[str, Path]:
    files: dict[str, Path] = {
        "s41_implementation": tmp_path / "s41.json",
        "s42_readiness": tmp_path / "s42.json",
        "s43_probe": tmp_path / "s43_probe.json",
        "s43_review": tmp_path / "s43_review.json",
        "s44_strategy": tmp_path / "s44.json",
        "agents": tmp_path / "AGENTS.md",
        "exact_coordinate_master_source": tmp_path / "exact_coordinate_master.py",
        "master_model_source": tmp_path / "master_model.py",
        "s44_builder": tmp_path / "s44_builder.py",
        "s45_package_builder": tmp_path / "s45_builder.py",
        "s43_review_builder": tmp_path / "s43_builder.py",
        "s44_tests": tmp_path / "test_s44.py",
        "s45_tests": tmp_path / "test_s45.py",
        "s43_review_tests": tmp_path / "test_s43.py",
        "focused_master_tests": tmp_path / "test_master.py",
        "exact_contract_tests": tmp_path / "test_exact_contract.py",
    }
    files["s41_implementation"].write_text(
        json.dumps({"status": "implemented_and_verified"}) + "\n",
        encoding="utf-8",
    )
    files["s42_readiness"].write_text(
        json.dumps({"status": "completed"}) + "\n",
        encoding="utf-8",
    )
    files["s43_probe"].write_text(
        json.dumps({"status": "completed", "cp_solver_solve_called": False}) + "\n",
        encoding="utf-8",
    )
    files["s43_review"].write_text(
        json.dumps({"status": "completed", "interpretation": {"classification": "instrumentation_inconclusive"}})
        + "\n",
        encoding="utf-8",
    )
    files["s44_strategy"].write_text(
        json.dumps(
            {
                "status": "completed",
                "source_mutation_performed": False,
                "interpretation": {
                    "classification": "exact_core_overlay_instrumentation_visibility_gap",
                    "implementation_allowed_now": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    files["agents"].write_text(
        "\n".join(
            [
                "## GPT Project Review Standing Authorization",
                "- Current S41 signature-bucket instrumentation state",
                "- Current S42 signature-bucket enabled no-solve probe readiness",
                "- Current S43 signature-bucket enabled no-solve probe result",
            ]
        ),
        encoding="utf-8",
    )
    files["exact_coordinate_master_source"].write_text(
        "\n".join(
            [
                "def _apply_ghost_anchor_signature_bucket_tightening(self):",
                "    pass",
                "def _add_global_valid_inequalities(self):",
                "    pass",
            ]
        ),
        encoding="utf-8",
    )
    files["master_model_source"].write_text(
        "def from_exact_core(self):\n    pass\n",
        encoding="utf-8",
    )
    files["focused_master_tests"].write_text(
        "def test_ghost_signature_bucket_tightening_instrumentation_default_off_is_absent():\n    pass\n",
        encoding="utf-8",
    )
    for key, path in files.items():
        if not path.exists():
            path.write_text(f"# {key}\n", encoding="utf-8")
    return files
