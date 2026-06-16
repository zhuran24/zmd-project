from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.phase3b.short_run.build_readiness_pack import (
    ALLOWED_DURATIONS_SECONDS,
    BLOCKED_UNTIL,
    build_short_run_readiness_pack,
    write_short_run_readiness_pack,
)
from src.runtime.sensitive_path_audit import (
    build_sensitive_path_fingerprint,
    compare_sensitive_path_fingerprints,
)


def test_short_run_readiness_selects_requested_candidates(tmp_path: Path) -> None:
    paths = _write_fixture_inputs(tmp_path)

    packet, command_matrix, fingerprint = build_short_run_readiness_pack(
        project_root=tmp_path,
        integrated_plan_path=paths["integrated_plan"],
        config_matrix_manifest_path=paths["config_manifest"],
        stage_worker_manifest_path=paths["stage_manifest"],
        priority_affinity_manifest_path=paths["priority_manifest"],
    )

    assert packet["schema"] == "phase3b-short-run-readiness-packet/v0"
    assert packet["execution_enabled"] is False
    assert packet["real_short_run_blocked_until"] == BLOCKED_UNTIL
    assert packet["proof_source"] is False
    assert packet["checkpoint_written"] is False
    assert packet["readiness"]["real_short_run_blocked_until"] == BLOCKED_UNTIL
    assert packet["safety"]["execution_enabled"] is False
    assert packet["safety"]["real_short_run_blocked_until"] == BLOCKED_UNTIL
    assert packet["safety"]["checkpoint_written"] is False
    assert [candidate["candidate_id"] for candidate in packet["candidates"]] == [
        "B0_prod_4x4",
        "experimental_13900ks_htoff_3x8_global_normal",
        "experimental_13900ks_htoff_4x5_global_normal",
        "experimental_13900ks_htoff_2x10_global_normal",
        "W1_prod_4x4_stage_6_4_2_4",
        "W3_prod_4x4_stage_6_6_2_6",
        "W6_prod_3x_stage_8_6_2_6",
    ]
    assert len(command_matrix["commands"]) == len(packet["candidates"]) * 2
    assert fingerprint["schema"] == "phase3b-sensitive-path-fingerprint/v0"


def test_short_run_readiness_command_templates_are_blocked_and_safe(tmp_path: Path) -> None:
    paths = _write_fixture_inputs(tmp_path)

    packet, command_matrix, _fingerprint = build_short_run_readiness_pack(
        project_root=tmp_path,
        integrated_plan_path=paths["integrated_plan"],
        config_matrix_manifest_path=paths["config_manifest"],
        stage_worker_manifest_path=paths["stage_manifest"],
        priority_affinity_manifest_path=paths["priority_manifest"],
    )
    commands = command_matrix["commands"]

    assert sorted({command["duration_seconds"] for command in commands}) == list(ALLOWED_DURATIONS_SECONDS)
    for command in commands:
        flattened = " ".join(command["command"]).lower()
        assert command["is_executable_now"] is False
        assert command["execution_enabled"] is False
        assert command["real_short_run_blocked_until"] == BLOCKED_UNTIL
        assert "--resume-campaign" not in flattened
        assert "168" not in command["campaign_hours"]
        assert "write-checkpoint" not in flattened
        assert "import-checkpoint" not in flattened
        assert command["contains_checkpoint_flag"] is False
        assert command["contains_final_168h"] is False

    by_candidate = {candidate["candidate_id"]: candidate for candidate in packet["candidates"]}
    assert by_candidate["experimental_13900ks_htoff_3x8_global_normal"]["env"] == {
        "EXACT_CP_SAT_WORKERS": "8"
    }
    assert by_candidate["W3_prod_4x4_stage_6_6_2_6"]["env"] == {
        "EXACT_MASTER_CP_SAT_WORKERS": "6",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": "6",
        "EXACT_BINDING_CP_SAT_WORKERS": "2",
        "EXACT_ROUTING_CP_SAT_WORKERS": "6",
    }


def test_sensitive_path_fingerprint_compare_detects_missing_existing_and_changed(tmp_path: Path) -> None:
    before = build_sensitive_path_fingerprint(tmp_path)
    assert before["canonical_checkpoint_exists"] is False

    checkpoint = tmp_path / "data" / "checkpoints" / "exact_campaign_state.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text('{"state": 1}', encoding="utf-8")
    after_create = build_sensitive_path_fingerprint(tmp_path)
    comparison = compare_sensitive_path_fingerprints(before, after_create)

    assert after_create["canonical_checkpoint_exists"] is True
    assert comparison["changed"] is True
    assert "data/checkpoints/exact_campaign_state.json" in comparison["changed_paths"]

    before_change = build_sensitive_path_fingerprint(tmp_path)
    checkpoint.write_text('{"state": 2}', encoding="utf-8")
    after_change = build_sensitive_path_fingerprint(tmp_path)
    changed = compare_sensitive_path_fingerprints(before_change, after_change)

    assert changed["changed"] is True
    assert "data/checkpoints/exact_campaign_state.json" in changed["changed_paths"]


def test_short_run_readiness_cli_no_write_and_write(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "short_run" / "build_readiness_pack.py"
    paths = _write_fixture_inputs(tmp_path)
    output_dir = (
        tmp_path
        / ".artifacts"
        / "phase3b_local_13900ks_tuning_20260430"
        / "07_short_run_readiness"
    )
    log_dir = (
        tmp_path
        / ".codex_test_logs"
        / "phase3b"
        / "local_13900ks_tuning_20260430"
        / "07_short_run_readiness"
    )

    base_args = [
        sys.executable,
        str(script),
        "--project-root",
        str(tmp_path),
        "--integrated-plan",
        str(paths["integrated_plan"]),
        "--config-matrix-manifest",
        str(paths["config_manifest"]),
        "--stage-worker-manifest",
        str(paths["stage_manifest"]),
        "--priority-affinity-manifest",
        str(paths["priority_manifest"]),
        "--output-dir",
        str(output_dir),
        "--log-dir",
        str(log_dir),
    ]

    no_write = subprocess.run(
        [*base_args, "--no-write"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert no_write.returncode == 0
    assert "execution_enabled=False" in no_write.stdout
    assert not output_dir.exists()
    assert not log_dir.exists()

    write = subprocess.run(
        base_args,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert write.returncode == 0
    assert (output_dir / "short_run_readiness_packet.json").is_file()
    assert (output_dir / "short_run_readiness_packet.md").is_file()
    assert (output_dir / "dry_run_command_matrix.json").is_file()
    assert (output_dir / "sensitive_path_fingerprint.json").is_file()
    assert (log_dir / "readiness_build_log.json").is_file()

    payload = json.loads((output_dir / "short_run_readiness_packet.json").read_text(encoding="utf-8"))
    assert payload["safety"]["proof_source"] is False
    assert payload["safety"]["main_py_executed"] is False


def _write_fixture_inputs(root: Path) -> dict[str, Path]:
    integrated_plan = root / "docs" / "phase3b_repair5_acceleration_tuning_ai_plan.md"
    integrated_plan.parent.mkdir(parents=True)
    integrated_plan.write_text("# integrated plan\n", encoding="utf-8")

    config_manifest = root / "matrix_manifest.json"
    config_manifest.write_text(json.dumps(_config_manifest_fixture()), encoding="utf-8")

    stage_manifest = root / "stage_worker_manifest.json"
    stage_manifest.write_text(json.dumps(_stage_manifest_fixture()), encoding="utf-8")

    priority_manifest = root / "affinity_priority_manifest.json"
    priority_manifest.write_text(
        json.dumps(
            {
                "schema": "phase3b-priority-affinity-manifest/v0",
                "variants": [{"variant_id": "B0_prod_4x4__normal_unpinned"}],
                "topology": {"pe_mapping": {"confidence": "unverified"}},
            }
        ),
        encoding="utf-8",
    )
    return {
        "integrated_plan": integrated_plan,
        "config_manifest": config_manifest,
        "stage_manifest": stage_manifest,
        "priority_manifest": priority_manifest,
    }


def _config_manifest_fixture() -> dict[str, object]:
    return {
        "schema": "phase3b-config-only-matrix-manifest/v0",
        "profiles": [
            _config_profile("B0_prod_4x4", 4, 4),
            _config_profile("experimental_13900ks_htoff_3x8_global_normal", 3, 8),
            _config_profile("experimental_13900ks_htoff_4x5_global_normal", 4, 5),
            _config_profile("experimental_13900ks_htoff_2x10_global_normal", 2, 10),
        ],
    }


def _stage_manifest_fixture() -> dict[str, object]:
    return {
        "schema": "phase3b-stage-worker-manifest/v0",
        "profiles": [
            _stage_profile("W1_stage_4x_master6_local4_binding2_routing4", 4, 6, 4, 2, 4),
            _stage_profile("W3_stage_4x_master6_local6_binding2_routing6", 4, 6, 6, 2, 6),
            _stage_profile("W6_stage_3x_master8_local6_binding2_routing6", 3, 8, 6, 2, 6),
        ],
    }


def _config_profile(profile_id: str, process_count: int, workers: int) -> dict[str, object]:
    return {
        "profile_id": profile_id,
        "process_count": process_count,
        "global_workers": workers,
        "total_worker_slots": process_count * workers,
        "env": {"EXACT_CP_SAT_WORKERS": str(workers)},
        "process_priority": "normal",
        "frontier_probe_mode": "auto",
        "risk": {"level": "low", "reasons": []},
    }


def _stage_profile(
    profile_id: str,
    process_count: int,
    master: int,
    local_capacity: int,
    binding: int,
    routing: int,
) -> dict[str, object]:
    return {
        "profile_id": profile_id,
        "process_count": process_count,
        "stage_workers": {
            "master": master,
            "local_capacity": local_capacity,
            "binding": binding,
            "routing": routing,
        },
        "max_stage_worker_slots": process_count * max(master, local_capacity, binding, routing),
        "env": {
            "EXACT_MASTER_CP_SAT_WORKERS": str(master),
            "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS": str(local_capacity),
            "EXACT_BINDING_CP_SAT_WORKERS": str(binding),
            "EXACT_ROUTING_CP_SAT_WORKERS": str(routing),
        },
        "process_priority": "normal",
        "frontier_probe_mode": "auto",
        "risk": {"level": "medium", "reasons": ["fixture"]},
    }
