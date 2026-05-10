from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b_operating_profile import (
    ACTIVE_GUARD_FORMULATION_PROFILE_ID,
    ALL_TEMPLATE_BLOCK64_FORMULATION_PROFILE_ID,
    DEFAULT_DIAGNOSTIC_PROFILE_ID,
    DEFAULT_PRODUCTION_PROFILE_ID,
    DELTA_INTERVAL_FORMULATION_PROFILE_ID,
    JOINED_XY_FORMULATION_PROFILE_ID,
    SELECTED_BLOCK_FORMULATION_PROFILE_ID,
    build_phase3b_operating_profile_summary,
)


def test_operating_profile_defaults_are_locked(tmp_path: Path) -> None:
    summary = build_phase3b_operating_profile_summary(tmp_path)
    profile_by_id = summary["profile_by_id"]

    assert summary["metadata"]["source"] == "phase3b_operating_profile_v1"
    assert summary["defaults"]["production_profile_id"] == DEFAULT_PRODUCTION_PROFILE_ID
    assert summary["defaults"]["diagnostic_profile_id"] == DEFAULT_DIAGNOSTIC_PROFILE_ID

    production = profile_by_id[DEFAULT_PRODUCTION_PROFILE_ID]
    assert production["profile_id"] == "prod_4x4_normal"
    assert production["is_default_production"] is True
    assert production["parallel_processes"] == 4
    assert production["env"] == {"EXACT_CP_SAT_WORKERS": "4"}
    assert production["process_priority"] == "normal"
    assert production["frontier_probe_mode"] == "auto"
    assert "--frontier-probe-mode auto" in production["command"]

    diagnostic = profile_by_id[DEFAULT_DIAGNOSTIC_PROFILE_ID]
    assert diagnostic["label"] == "1x1 normal diagnostic"
    assert diagnostic["is_default_diagnostic"] is True
    assert diagnostic["parallel_processes"] == 1
    assert diagnostic["env"] == {"EXACT_CP_SAT_WORKERS": "1"}
    assert diagnostic["process_priority"] == "normal"

    high = profile_by_id["prod_4x4_high"]
    assert high["process_priority"] == "high"
    assert high["is_default_production"] is False
    assert summary["policy"]["high_priority_default"] is False

    formulation = profile_by_id[ALL_TEMPLATE_BLOCK64_FORMULATION_PROFILE_ID]
    assert formulation["role"] == "formulation_diagnostic"
    assert formulation["is_default_production"] is False
    assert formulation["is_default_diagnostic"] is False
    assert formulation["is_formulation_diagnostic"] is True
    assert formulation["env"]["EXACT_POWER_COVERAGE_WITNESS_ENCODING"] == "block_element"
    assert "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY" not in formulation["env"]
    assert formulation["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE"] == "64"
    assert formulation["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"] == ""
    assert formulation["env"]["EXACT_POWER_FAMILY_LOOKUP_ENCODING"] == "linear_shell_guards"
    assert formulation["env"]["EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING"] == "linear_minmax"
    assert "-AllBlockTemplates" in formulation["command"]
    assert "--campaign-hours 168" not in formulation["command"]
    assert formulation["proof_semantics"] == (
        "proof_preserving_encoding_comparison_not_proof_source"
    )

    delta_interval = profile_by_id[DELTA_INTERVAL_FORMULATION_PROFILE_ID]
    assert delta_interval["role"] == "formulation_diagnostic"
    assert delta_interval["is_default_production"] is False
    assert delta_interval["is_default_diagnostic"] is False
    assert delta_interval["is_formulation_diagnostic"] is True
    assert delta_interval["env"]["EXACT_POWER_COVERAGE_WITNESS_ENCODING"] == "block_element"
    assert delta_interval["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE"] == "64"
    assert delta_interval["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"] == ""
    assert delta_interval["env"]["EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING"] == "delta"
    assert delta_interval["env"]["EXACT_POWER_FAMILY_LOOKUP_ENCODING"] == "linear_shell_guards"
    assert delta_interval["env"]["EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING"] == "linear_minmax"
    assert "-AllBlockTemplates" in delta_interval["command"]
    assert "-SelectedIntervalEncoding delta" in delta_interval["command"]
    assert "-AnchorIndices 118,125" in delta_interval["command"]
    assert "--campaign-hours 168" not in delta_interval["command"]
    assert delta_interval["proof_semantics"] == (
        "proof_preserving_encoding_comparison_not_proof_source"
    )

    selected_block = profile_by_id[SELECTED_BLOCK_FORMULATION_PROFILE_ID]
    assert selected_block["role"] == "formulation_diagnostic"
    assert selected_block["is_default_production"] is False
    assert selected_block["is_default_diagnostic"] is False
    assert selected_block["is_formulation_diagnostic"] is True
    assert selected_block["env"]["EXACT_POWER_COVERAGE_WITNESS_ENCODING"] == "block_element"
    assert selected_block["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY"] == "selected_block"
    assert selected_block["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE"] == "64"
    assert selected_block["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"] == ""
    assert selected_block["env"]["EXACT_POWER_FAMILY_LOOKUP_ENCODING"] == "linear_shell_guards"
    assert selected_block["env"]["EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING"] == "linear_minmax"
    assert "-AllBlockTemplates" in selected_block["command"]
    assert "-BlockGeometry selected_block" in selected_block["command"]
    assert "--campaign-hours 168" not in selected_block["command"]
    assert selected_block["proof_semantics"] == (
        "proof_preserving_encoding_comparison_not_proof_source"
    )

    active_guard = profile_by_id[ACTIVE_GUARD_FORMULATION_PROFILE_ID]
    assert active_guard["role"] == "formulation_diagnostic"
    assert active_guard["is_default_production"] is False
    assert active_guard["is_default_diagnostic"] is False
    assert active_guard["is_formulation_diagnostic"] is True
    assert active_guard["env"]["EXACT_POWER_COVERAGE_WITNESS_ENCODING"] == "block_element"
    assert (
        active_guard["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY"]
        == "selected_block_active_guard"
    )
    assert active_guard["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE"] == "64"
    assert active_guard["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"] == ""
    assert active_guard["env"]["EXACT_POWER_FAMILY_LOOKUP_ENCODING"] == "linear_shell_guards"
    assert active_guard["env"]["EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING"] == "linear_minmax"
    assert "-AllBlockTemplates" in active_guard["command"]
    assert "-BlockGeometry selected_block_active_guard" in active_guard["command"]
    assert "-AnchorIndices 118,125" in active_guard["command"]
    assert "-TimeLimitSeconds 45" in active_guard["command"]
    assert "--campaign-hours 168" not in active_guard["command"]
    assert active_guard["proof_semantics"] == (
        "diagnostic_formulation_only_equivalence_unproven_not_proof_source"
    )
    assert active_guard["candidate_elimination_claim"] is False
    assert "not campaign proof" in active_guard["warning"]
    assert "not production readiness" in active_guard["warning"]
    assert "not candidate elimination" in active_guard["warning"]
    assert "large Boolean guard layer" in active_guard["risk_note"]

    joined_xy = profile_by_id[JOINED_XY_FORMULATION_PROFILE_ID]
    assert joined_xy["role"] == "formulation_diagnostic"
    assert joined_xy["is_default_production"] is False
    assert joined_xy["is_default_diagnostic"] is False
    assert joined_xy["is_formulation_diagnostic"] is True
    assert joined_xy["env"]["EXACT_POWER_COVERAGE_WITNESS_ENCODING"] == "block_element"
    assert (
        joined_xy["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY"]
        == "selected_block_active_guard_joined_xy"
    )
    assert joined_xy["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE"] == "64"
    assert joined_xy["env"]["EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"] == ""
    assert joined_xy["env"]["EXACT_POWER_FAMILY_LOOKUP_ENCODING"] == "linear_shell_guards"
    assert joined_xy["env"]["EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING"] == "linear_minmax"
    assert "-AllBlockTemplates" in joined_xy["command"]
    assert "-BlockGeometry selected_block_active_guard_joined_xy" in joined_xy["command"]
    assert "-AnchorIndices 118,119,125" in joined_xy["command"]
    assert "-TimeLimitSeconds 120" in joined_xy["command"]
    assert "--campaign-hours 168" not in joined_xy["command"]
    assert joined_xy["proof_semantics"] == (
        "diagnostic_formulation_only_not_proof_source"
    )
    assert joined_xy["candidate_elimination_claim"] is False
    assert "not campaign proof" in joined_xy["warning"]
    assert "SAT expansion recovery" in joined_xy["risk_note"]
    assert any("joined_xy_probe_synthesis" in path for path in joined_xy["evidence_artifacts"])


def test_operating_profile_cli_writes_and_no_write_skips_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "build_phase3b_operating_profile.py"
    output_dir = tmp_path / "profile_output"
    no_write_dir = tmp_path / "profile_no_write"

    no_write_result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(no_write_dir),
            "--no-write",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert no_write_result.returncode == 0
    assert "phase3b operating profile" in no_write_result.stdout
    assert "prod_4x4_normal" in no_write_result.stdout
    assert not no_write_dir.exists()

    write_result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert write_result.returncode == 0
    json_path = output_dir / "operating_profile.json"
    md_path = output_dir / "operating_profile.md"
    assert json_path.exists()
    assert md_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["defaults"]["production_profile_id"] == "prod_4x4_normal"
    assert "prod_4x4_normal" in md_path.read_text(encoding="utf-8")
    assert ALL_TEMPLATE_BLOCK64_FORMULATION_PROFILE_ID in payload["profile_by_id"]
    assert DELTA_INTERVAL_FORMULATION_PROFILE_ID in payload["profile_by_id"]
    assert ACTIVE_GUARD_FORMULATION_PROFILE_ID in payload["profile_by_id"]
    assert SELECTED_BLOCK_FORMULATION_PROFILE_ID in payload["profile_by_id"]
    assert JOINED_XY_FORMULATION_PROFILE_ID in payload["profile_by_id"]


def test_runner_wrappers_lock_frontier_probe_auto_and_worker_profile() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    prod_script = (repo_root / "scripts" / "run_prod_4x4_normal.ps1").read_text(
        encoding="utf-8"
    )
    diagnostic_script = (repo_root / "scripts" / "run_prod_1x1_normal.ps1").read_text(
        encoding="utf-8"
    )
    high_script = (repo_root / "scripts" / "run_prod_4x4_high.ps1").read_text(
        encoding="utf-8"
    )

    assert '"--parallel-processes", "4"' in prod_script
    assert '"--process-priority", "normal"' in prod_script
    assert '"--frontier-probe-mode", "auto"' in prod_script
    assert '"EXACT_CP_SAT_WORKERS" = "4"' in prod_script

    assert '"--parallel-processes", "1"' in diagnostic_script
    assert '"--process-priority", "normal"' in diagnostic_script
    assert '"--frontier-probe-mode", "auto"' in diagnostic_script
    assert '"EXACT_CP_SAT_WORKERS" = "1"' in diagnostic_script

    assert '"--process-priority", "high"' in high_script
    assert '"--frontier-probe-mode", "auto"' in high_script
    assert '"EXACT_CP_SAT_WORKERS" = "4"' in high_script


def test_block64_anchor_probe_runner_exposes_selected_interval_encoding() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = (
        repo_root / "scripts" / "run_phase3b_block64_low_encoding_anchor_probe.ps1"
    ).read_text(encoding="utf-8")

    assert '[ValidateSet("bounds", "delta")]' in script
    assert '[string]$SelectedIntervalEncoding = "bounds"' in script
    assert '"EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING" = $SelectedIntervalEncoding' in script
    assert "$selectedIntervalScope" in script
