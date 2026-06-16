from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.phase3b.checkpoint_free.signature_bucket.fallback_reason.build_rereview_package_v2 import (
    DEFAULT_RUN_ID,
    REVIEW_WORDING_REQUIREMENTS,
    build_signature_bucket_fallback_reason_probe_rereview_package_v2,
)


def test_fallback_reason_probe_rereview_package_v2_builds_clean_zip(
    tmp_path: Path,
) -> None:
    package = build_signature_bucket_fallback_reason_probe_rereview_package_v2(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        inputs=_write_inputs(tmp_path),
    )

    run_dir = _output_dir(tmp_path) / DEFAULT_RUN_ID
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


def test_fallback_reason_probe_rereview_package_v2_manifest_contains_context(
    tmp_path: Path,
) -> None:
    package = build_signature_bucket_fallback_reason_probe_rereview_package_v2(
        project_root=tmp_path,
        output_dir=_output_dir(tmp_path),
        run_id="custom_s67_rereview",
        inputs=_write_inputs(tmp_path),
    )

    with zipfile.ZipFile(Path(package["zip_path"]), "r") as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        s65 = json.loads(archive.read("evidence/s65_external_review_reply_summary.json").decode("utf-8"))
        s66 = json.loads(
            archive.read(
                "evidence/s66_s64_fallback_reason_probe_review_hardening_implementation.json"
            ).decode("utf-8")
        )

    assert "review_request.md" in names
    assert "evidence/s65_failed_review_reply_raw.md" in names
    assert "evidence/s65_external_review_reply_summary.json" in names
    assert (
        "code_context/scripts/phase3b/checkpoint_free/signature_bucket/fallback_reason/build_external_review_package.py"
        in names
    )
    assert (
        "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/fallback_reason/test_external_review_package.py"
        in names
    )
    assert "evidence/s66_s64_fallback_reason_probe_review_hardening_implementation.json" in names
    assert "evidence/s63_signature_bucket_fallback_reason_probe_readiness.json" in names
    assert "code_context/scripts/phase3b/checkpoint_free/signature_bucket/fallback_reason/build_review.py" in names
    assert "test_context/src/tests/phase3b/checkpoint_free/signature_bucket/fallback_reason/test_review.py" in names
    assert "code_context/scripts/phase3b/checkpoint_free/signature_bucket/fallback_reason/build_rereview_package_v2.py" in names
    assert manifest["review_required_before_authorization"] is True
    assert manifest["external_review_is_authorization"] is False
    assert manifest["probe_execution_performed"] is False
    assert s65["review_verdict"] == "fail_do_not_request_authorization_yet"
    assert s66["status"] == "implemented_and_verified"
    assert s66["hardening"]["fallback_reason_instrumentation_missing_cli_nonzero"] is True


def test_fallback_reason_probe_rereview_package_v2_no_write(tmp_path: Path) -> None:
    output_dir = _output_dir(tmp_path)

    package = build_signature_bucket_fallback_reason_probe_rereview_package_v2(
        project_root=tmp_path,
        output_dir=output_dir,
        inputs=_write_inputs(tmp_path),
        no_write=True,
    )

    assert package["status"] == "completed"
    assert package["clean_extraction_validation"]["reason"] == "no_write"
    assert not (output_dir / DEFAULT_RUN_ID).exists()


def test_fallback_reason_probe_rereview_package_v2_rejects_bad_namespace(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="S67 re-review package namespace"):
        build_signature_bucket_fallback_reason_probe_rereview_package_v2(
            project_root=tmp_path,
            output_dir=tmp_path / "bad",
            no_write=True,
        )


def _write_inputs(root: Path) -> dict[str, Path]:
    inputs_dir = root / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "s65_failed_review_raw": inputs_dir / "s65_failed_review_raw.md",
        "s65_review_summary": inputs_dir / "s65_review_summary.json",
        "s65_package_summary": inputs_dir / "s65_package_summary.json",
        "s65_package_builder": inputs_dir / "s65_package_builder.py",
        "s65_package_tests": inputs_dir / "test_s65_package.py",
        "s66_implementation": inputs_dir / "s66_implementation.json",
        "s63_readiness": inputs_dir / "s63_readiness.json",
        "s63_future_command": inputs_dir / "s63_future_command.json",
        "agents": inputs_dir / "AGENTS.md",
        "s63_builder": inputs_dir / "s63_builder.py",
        "s64_builder": inputs_dir / "s64_builder.py",
        "s66_builder": inputs_dir / "s66_builder.py",
        "s67_package_builder": inputs_dir / "s67_package_builder.py",
        "s63_tests": inputs_dir / "test_s63.py",
        "s64_tests": inputs_dir / "test_s64.py",
        "s67_tests": inputs_dir / "test_s67.py",
        "exact_contract_tests": inputs_dir / "test_exact_contract.py",
    }
    paths["s65_failed_review_raw"].write_text(
        "\n".join(
            [
                "I do not pass this package yet.",
                "S64 needs stricter sensitive_path_comparison schema and non-success missing visibility status.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s65_review_summary"].write_text(
        json.dumps(
            {
                "review_verdict": "fail_do_not_request_authorization_yet",
                "review_is_authorization": False,
                "authorization_required_next": False,
                "probe_execution_allowed_now": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s65_package_summary"].write_text(
        json.dumps(
            {
                "status": "completed",
                "package_kind": "external_review_fallback_reason_probe_readiness_and_review_tooling_package",
                "review_required_before_authorization": True,
                "external_review_is_authorization": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s66_implementation"].write_text(
        json.dumps(
            {
                "status": "implemented_and_verified",
                "hardening": {
                    "sensitive_path_schema_required": "phase3b-sensitive-path-fingerprint-comparison/v0",
                    "fallback_reason_instrumentation_missing_cli_nonzero": True,
                },
                "probe_execution_performed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s63_readiness"].write_text(
        json.dumps(
            {
                "status": "completed",
                "readiness": {"classification": "ready_for_fallback_reason_probe_review"},
                "probe_execution_enabled": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s63_future_command"].write_text(
        json.dumps(
            {
                "command": [
                    "python",
                    "scripts/run_phase3b_checkpoint_free_overlay_timing_probe.py",
                    "--execute-no-solve",
                    "--candidate-key",
                    "42x32",
                    "--run-id",
                    "local_hotspot_42x32_signature_bucket_fallback_reason_inst_no_solve_001",
                ],
                "environment": {
                    "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING": "1",
                    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION": "1",
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
                "- Current S63/S64 fallback-reason probe readiness state: ready.",
                "- Current S65 fallback-reason probe review package: failed review.",
                "- Current S65 external review result: blocked.",
                "- Current S66/S67 S64 fail-closed hardening state: implemented.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s64_builder"].write_text(
        "\n".join(
            [
                "SENSITIVE_PATH_COMPARISON_SCHEMA = 'phase3b-sensitive-path-fingerprint-comparison/v0'",
                "NON_SUCCESS_CLASSIFICATIONS = {'fallback_reason_instrumentation_missing'}",
                "def _sensitive_path_comparison_is_clean(value):",
                "    return value.get('changed_entries') == []",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    paths["s64_tests"].write_text(
        "\n".join(
            [
                "def test_fallback_reason_probe_review_missing_instrumentation_cli_is_nonzero():",
                "    assert True",
                "def test_fallback_reason_probe_review_malformed_sensitive_comparison_disqualifies():",
                "    assert True",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for key in (
        "s65_package_builder",
        "s65_package_tests",
        "s63_builder",
        "s66_builder",
        "s67_package_builder",
        "s63_tests",
        "s67_tests",
        "exact_contract_tests",
    ):
        paths[key].write_text(f"# fixture for {key}\n", encoding="utf-8")
    return paths


def _output_dir(root: Path) -> Path:
    return (
        root
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "67_signature_bucket_fallback_reason_probe_rereview_package_v2"
    )
