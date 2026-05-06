from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "build_phase3b_profile_comparison.py"
    spec = importlib.util.spec_from_file_location("build_phase3b_profile_comparison", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_profile_definitions_cover_expected_profiles() -> None:
    module = _load_script_module()
    profiles = {entry["profile_id"]: entry for entry in module._profile_definitions()}

    assert set(profiles) == {
        "base_default_fixed_probe3_sym3",
        "base_delta_interval_fixed_probe3_sym3",
        "selected_block_block64_all_templates",
        "block64_all_templates_low_encoding_linearization0",
        "block64_all_templates_low_encoding_linearization0_delta_interval",
        "block64_protocol_only_low_encoding_linearization0",
    }
    assert (
        profiles["base_delta_interval_fixed_probe3_sym3"]["env"][
            "EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING"
        ]
        == "delta"
    )
    assert (
        profiles["selected_block_block64_all_templates"]["env"][
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY"
        ]
        == "selected_block"
    )
    assert (
        profiles["block64_all_templates_low_encoding_linearization0"]["env"][
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"
        ]
        == ""
    )
    assert (
        profiles["block64_all_templates_low_encoding_linearization0_delta_interval"][
            "env"
        ]["EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING"]
        == "delta"
    )
    assert (
        profiles["block64_protocol_only_low_encoding_linearization0"]["env"][
            "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"
        ]
        == "protocol_storage_box"
    )


def test_profile_comparison_summary_marks_progress_without_proof(tmp_path: Path) -> None:
    module = _load_script_module()
    summary = module._build_summary(
        project_root=tmp_path,
        campaign_state=tmp_path / "state.json",
        candidate="67x13",
        anchors=["119"],
        time_limit_seconds=60.0,
        worker_count=1,
        records=[
            {
                "profile_id": "base_default_fixed_probe3_sym3",
                "exit_code": 0,
                "terminal_count": 0,
                "search_progress_unknown_count": 0,
            },
            {
                "profile_id": "block64_all_templates_low_encoding_linearization0",
                "exit_code": 0,
                "terminal_count": 0,
                "search_progress_unknown_count": 1,
            },
        ],
    )

    assert summary["metadata"]["diagnostic_semantics"] == "profile_comparison_not_proof_source"
    assert summary["status"]["outcome"] == "search_progress_without_terminal"
    assert summary["status"]["proof_source"] is False
    assert summary["status"]["runtime_promotion_ready"] is False
    assert summary["status"]["search_progress_profiles"] == [
        "block64_all_templates_low_encoding_linearization0"
    ]
