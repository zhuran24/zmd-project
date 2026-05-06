from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator import (
    _evaluate_supporting_artifacts,
    build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_markdown,
    render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_text,
)
from src.search.phase3b_b5a_certification_contracts import chain_fingerprint, sha256_file
from src.search.phase3b_long_run_preflight import (
    EXPECTED_PRODUCTION_FRONTIER_CANDIDATES,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _acceptance_execution_staging_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_acceptance_execution_staging_v1",
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "acceptance_execution_staging_ready": True,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
        },
        "acceptance_execution_staging": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "does_not_execute_acceptance": True,
            "does_not_imply_enablement": True,
            "exact_command_to_run_later": (
                "python temp_scripts/benchmark_parallelism.py --suite-kind "
                "production-acceptance --suite-output "
                ".codex_test_logs/phase3b/production_acceptance_after_change.json"
            ),
            "exact_future_output_path": ".codex_test_logs/phase3b/production_acceptance_after_change.json",
            "prod_4x4_record_match_rules": [
                {
                    "selector": "label",
                    "field": "label",
                    "expected": "prod_4x4",
                    "reason": "primary long-run preflight selector",
                },
                {
                    "selector": "fallback_4x4_parallelism",
                    "fields": {
                        "process_count": 4,
                        "worker_count_per_process": 4,
                    },
                    "reason": "fallback selector when label is absent",
                },
            ],
            "expected_prod_4x4_validity_fields": [
                {
                    "field": "completed",
                    "expected": True,
                    "reason": "completed must be true",
                },
                {
                    "field": "return_code",
                    "expected": 0,
                    "reason": "return_code must be zero",
                },
                {
                    "field": "campaign_valid_after_run",
                    "expected": True,
                    "reason": "campaign validity must hold",
                },
                {
                    "field": "duplicated_work",
                    "expected": False,
                    "reason": "duplicated_work must stay false",
                },
            ],
        },
    }


def _pre_run_acceptance_validation_json() -> dict:
    return {
        "metadata": {
            "source": "phase3b_coordinate_validation_anchor119_row_domain_pre_run_acceptance_validation_v1",
        },
        "candidate": {
            "key": "67x13",
            "anchor_idx": 119,
            "formulation_profile": "joined_xy_block64_all_templates",
        },
        "status": {
            "acceptance_validation_ready_for_review": True,
            "runtime_enablement_allowed": False,
            "acceptance_executed": False,
        },
        "pre_run_acceptance_validation": {
            "guard_id": "anchor119_mixed_lane_no_witness_guard_v0",
            "payload_id": "anchor119_three_label_overlap_above_strip_count_guard_v0",
            "production_profile_id": "prod_4x4_normal",
            "production_acceptance_command": (
                "python temp_scripts/benchmark_parallelism.py --suite-kind "
                "production-acceptance --suite-output "
                ".codex_test_logs/phase3b/production_acceptance_after_change.json"
            ),
            "exact_future_acceptance_json_path": ".codex_test_logs/phase3b/production_acceptance_after_change.json",
            "prod_4x4_record_match_rules": [
                {
                    "selector": "label",
                    "field": "label",
                    "expected": "prod_4x4",
                    "reason": "primary long-run preflight selector",
                },
                {
                    "selector": "fallback_4x4_parallelism",
                    "fields": {
                        "process_count": 4,
                        "worker_count_per_process": 4,
                    },
                    "reason": "fallback selector when label is absent",
                },
            ],
            "required_prod_4x4_validity_fields": [
                {
                    "field": "completed",
                    "expected": True,
                    "reason": "completed must be true",
                },
                {
                    "field": "return_code",
                    "expected": 0,
                    "reason": "return_code must be zero",
                },
                {
                    "field": "campaign_valid_after_run",
                    "expected": True,
                    "reason": "campaign validity must hold",
                },
                {
                    "field": "duplicated_work",
                    "expected": False,
                    "reason": "duplicated_work must stay false",
                },
            ],
        },
    }


def test_anchor119_row_domain_acceptance_result_validator_ready(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    acceptance_execution_staging_path = tmp_path / "acceptance_execution_staging.json"
    pre_run_acceptance_validation_path = (
        tmp_path / "pre_run_acceptance_validation.json"
    )
    _write_json(
        acceptance_execution_staging_path, _acceptance_execution_staging_json()
    )
    _write_json(
        pre_run_acceptance_validation_path, _pre_run_acceptance_validation_json()
    )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator(
            repo_root,
            acceptance_execution_staging_path=acceptance_execution_staging_path,
            pre_run_acceptance_validation_path=pre_run_acceptance_validation_path,
        )
    )

    assert report["metadata"]["source"] == (
        "phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_v1"
    )
    assert report["status"]["acceptance_result_validator_ready"] is True
    assert report["status"]["runtime_enablement_allowed"] is False
    assert report["status"]["acceptance_result_validation_performed"] is False
    validator = report["acceptance_result_validator"]
    assert validator["does_not_execute_acceptance"] is True
    assert validator["does_not_imply_enablement"] is True
    assert validator["does_not_validate_real_acceptance_run_yet"] is True
    assert (
        validator["expected_result_path"]
        == ".codex_test_logs/phase3b/production_acceptance_after_change.json"
    )
    expected_fields = {
        entry["field"]: entry["expected"]
        for entry in validator["expected_prod_4x4_validity_fields"]
    }
    assert expected_fields == {
        "completed": True,
        "return_code": 0,
        "campaign_valid_after_run": True,
        "duplicated_work": False,
    }
    markdown = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_markdown(
            report
        )
    )
    text = (
        render_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator_text(
            report
        )
    )
    assert "Acceptance Result Validator" in markdown
    assert "acceptance_result_validator_ready=True" in text
    assert "does_not_validate_real_acceptance_run_yet=True" in text


def test_anchor119_row_domain_acceptance_result_validator_fails_if_upstream_missing(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    pre_run_acceptance_validation_path = (
        tmp_path / "pre_run_acceptance_validation.json"
    )
    _write_json(
        pre_run_acceptance_validation_path, _pre_run_acceptance_validation_json()
    )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator(
            repo_root,
            acceptance_execution_staging_path=tmp_path / "missing_staging.json",
            pre_run_acceptance_validation_path=pre_run_acceptance_validation_path,
        )
    )

    assert report["status"]["acceptance_result_validator_ready"] is False
    failed = {check["check_id"] for check in report["checks"] if check["status"] == "fail"}
    assert "acceptance_execution_staging_present" in failed


def test_anchor119_row_domain_acceptance_result_validator_records_canonical_chain_hashes(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    acceptance_execution_staging_path = (
        project_root / ".artifacts" / "acceptance_execution_staging.json"
    )
    pre_run_acceptance_validation_path = (
        project_root / ".artifacts" / "pre_run_acceptance_validation.json"
    )
    acceptance_result_path = (
        project_root
        / ".codex_test_logs"
        / "phase3b"
        / "production_acceptance_after_change.json"
    )
    _write_json(
        acceptance_execution_staging_path, _acceptance_execution_staging_json()
    )
    _write_json(
        pre_run_acceptance_validation_path, _pre_run_acceptance_validation_json()
    )
    _write_json(
        acceptance_result_path,
        {
            "suite_kind": "production-acceptance",
            "requested_master_search_profile": "exact_coordinate_guided_branching_v4",
            "benchmark_inputs": {
                "grid_w": 70,
                "grid_h": 70,
                "safe_area_upper_bound": 1347,
                "selected_candidate": [1330, 70, 19],
                "frontier_candidates": EXPECTED_PRODUCTION_FRONTIER_CANDIDATES,
            },
            "run_records": [
                {
                    "label": "prod_4x4",
                    "process_count": 4,
                    "worker_count_per_process": 4,
                    "completed": True,
                    "return_code": 0,
                    "campaign_valid_after_run": True,
                    "duplicated_work": False,
                }
            ],
        },
    )

    report = (
        build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator(
            project_root,
            acceptance_execution_staging_path=acceptance_execution_staging_path,
            pre_run_acceptance_validation_path=pre_run_acceptance_validation_path,
            acceptance_result_path=acceptance_result_path,
        )
    )

    records = report["chain_input_hashes"]
    assert [record["input_id"] for record in records] == [
        "acceptance_execution_staging",
        "pre_run_acceptance_validation",
        "provided_acceptance_result",
    ]
    for record in records:
        path = project_root / record["path"]
        assert record["exists"] is True
        assert record["sha256"] == sha256_file(path)
        assert len(record["sha256"]) == 64
    assert report["chain_fingerprint"] == chain_fingerprint(records)


def test_anchor119_row_domain_acceptance_result_validator_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    acceptance_execution_staging_path = tmp_path / "acceptance_execution_staging.json"
    pre_run_acceptance_validation_path = (
        tmp_path / "pre_run_acceptance_validation.json"
    )
    output_dir = tmp_path / "out"
    _write_json(
        acceptance_execution_staging_path, _acceptance_execution_staging_json()
    )
    _write_json(
        pre_run_acceptance_validation_path, _pre_run_acceptance_validation_json()
    )
    script = (
        repo_root
        / "scripts"
        / "build_phase3b_coordinate_validation_anchor119_row_domain_acceptance_result_validator.py"
    )

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--acceptance-execution-staging",
            str(acceptance_execution_staging_path),
            "--pre-run-acceptance-validation",
            str(pre_run_acceptance_validation_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor119 row-domain acceptance result validator" in no_write.stdout
    assert "expected_result_path=" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(repo_root),
            "--acceptance-execution-staging",
            str(acceptance_execution_staging_path),
            "--pre-run-acceptance-validation",
            str(pre_run_acceptance_validation_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor119_row_domain_acceptance_result_validator_json=" in write.stdout
    payload = json.loads(
        (
            output_dir / "anchor119_row_domain_acceptance_result_validator.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["status"]["acceptance_result_validator_ready"] is True
    assert payload["status"]["acceptance_result_validation_performed"] is False
    assert (
        output_dir / "anchor119_row_domain_acceptance_result_validator.md"
    ).exists()
    assert (
        output_dir / "anchor119_row_domain_acceptance_result_validator.txt"
    ).exists()


def test_acceptance_result_supporting_artifacts_prefer_project_local_mirror(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "clean_project"
    mirror_root = project_root / ".codex_test_logs" / "parallelism_benchmark"
    output_json = mirror_root / "prod_4x4.json"
    log_path = mirror_root / "prod_4x4.log"
    state_path = mirror_root / "workspaces" / "prod_4x4" / "data" / "checkpoints" / "exact_campaign_state.json"
    telemetry_path = mirror_root / "workspaces" / "prod_4x4" / "data" / "checkpoints" / "exact_campaign_telemetry.json"
    record = {
        "target": "production-campaign-run",
        "completed": True,
        "campaign_valid_after_run": True,
        "duplicated_work": False,
        "process_count": 4,
        "requested_master_search_profile": "exact_coordinate_guided_branching_v4",
        "output_json": r"D:\old\endfield_phase3b_project_current\.codex_test_logs\parallelism_benchmark\prod_4x4.json",
        "log_path": r"D:\old\endfield_phase3b_project_current\.codex_test_logs\parallelism_benchmark\prod_4x4.log",
        "campaign_state_path": r"D:\old\endfield_phase3b_project_current\.codex_test_logs\parallelism_benchmark\workspaces\prod_4x4\data\checkpoints\exact_campaign_state.json",
        "campaign_telemetry_path": r"D:\old\endfield_phase3b_project_current\.codex_test_logs\parallelism_benchmark\workspaces\prod_4x4\data\checkpoints\exact_campaign_telemetry.json",
    }
    _write_json(
        output_json,
        {
            "target": record["target"],
            "completed": record["completed"],
            "campaign_valid_after_run": record["campaign_valid_after_run"],
            "duplicated_work": record["duplicated_work"],
            "parallel_processes": record["process_count"],
            "requested_master_search_profile": record["requested_master_search_profile"],
        },
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("ok\n", encoding="utf-8")
    _write_json(state_path, {"ok": True})
    _write_json(telemetry_path, {"ok": True})

    results = _evaluate_supporting_artifacts(project_root, record)

    assert results
    assert all(item["passed"] is True for item in results)
    assert {item["path"] for item in results} >= {
        ".codex_test_logs/parallelism_benchmark/prod_4x4.json",
        ".codex_test_logs/parallelism_benchmark/prod_4x4.log",
        ".codex_test_logs/parallelism_benchmark/workspaces/prod_4x4/data/checkpoints/exact_campaign_state.json",
        ".codex_test_logs/parallelism_benchmark/workspaces/prod_4x4/data/checkpoints/exact_campaign_telemetry.json",
    }
