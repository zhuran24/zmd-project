from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.via_pole.build_external_review_package import (
    build_via_pole_external_review_package,
)


def test_external_review_package_builds_zip_and_validates_clean_extraction(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "33_via_pole_external_review_package"
    )

    package = build_via_pole_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        run_id="pkg_001",
        inputs=inputs,
    )

    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["validated"] is True
    assert package["source_mutation_performed"] is False
    zip_path = Path(package["zip_path"])
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path, "r") as archive:
        names = set(archive.namelist())
    assert "review_request.md" in names
    assert "evidence/s31_via_pole_shape_instrumentation_patch_spec.json" in names
    assert "source_context/src/models/exact_coordinate_master.py" in names
    assert (output_dir / "pkg_001" / "clean_extraction_validation.json").exists()


def test_external_review_package_no_write_returns_payload_without_zip(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "33_via_pole_external_review_package"
    )

    package = build_via_pole_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        run_id="pkg_001",
        inputs=inputs,
        no_write=True,
    )

    assert package["status"] == "completed"
    assert not (output_dir / "pkg_001" / "pkg_001.zip").exists()


def test_external_review_package_rejects_bad_namespace(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)

    with pytest.raises(ValueError, match="external review package namespace"):
        build_via_pole_external_review_package(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            inputs=inputs,
        )


def test_external_review_package_fails_when_clean_validation_fails(tmp_path: Path) -> None:
    inputs = _write_inputs(tmp_path)
    s32 = inputs["s32_authorization_packet"]
    payload = json.loads(s32.read_text(encoding="utf-8"))
    payload["authorization"]["authorization_required"] = False
    s32.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "33_via_pole_external_review_package"
    )

    package = build_via_pole_external_review_package(
        project_root=tmp_path,
        output_dir=output_dir,
        run_id="pkg_001",
        inputs=inputs,
    )

    assert package["status"] == "failed"
    assert package["clean_extraction_validation"]["validated"] is False


def _write_inputs(root: Path) -> dict[str, Path]:
    evidence = root / "evidence"
    source = root / "src" / "models"
    evidence.mkdir(parents=True)
    source.mkdir(parents=True)
    paths = {
        "s29_shape_inventory_comparison": evidence / "s29.json",
        "s30_shape_scaling_review": evidence / "s30.json",
        "s31_patch_spec": evidence / "s31.json",
        "s32_authorization_packet": evidence / "s32.json",
        "next_decision": evidence / "next.json",
        "target_source": source / "exact_coordinate_master.py",
    }
    paths["s29_shape_inventory_comparison"].write_text(json.dumps({"status": "completed"}) + "\n", encoding="utf-8")
    paths["s30_shape_scaling_review"].write_text(json.dumps({"status": "completed"}) + "\n", encoding="utf-8")
    paths["s31_patch_spec"].write_text(
        json.dumps(
            {
                "source_mutation_performed": False,
                "interpretation": {"implementation_allowed_now": False},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s32_authorization_packet"].write_text(
        json.dumps(
            {
                "authorization": {
                    "authorization_required": True,
                    "implementation_allowed_now": False,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["next_decision"].write_text(
        json.dumps(
            {
                "recommendation": {
                    "action": "hold_for_default_off_via_pole_shape_instrumentation_source_authorization"
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["target_source"].write_text("def target():\n    return None\n", encoding="utf-8")
    return paths
