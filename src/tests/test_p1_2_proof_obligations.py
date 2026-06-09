"""Tests for the P1.2 proof-obligation consolidation gate."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import check_p1_2_proof_obligations


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "data" / "proof_obligations" / "p1_2_proof_obligations.json"


def test_p1_2_proof_obligation_gate_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_p1_2_proof_obligations.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "P1.2 proof obligation check passed: 5 obligations anchored" in result.stdout


def test_p1_2_proof_obligation_manifest_has_required_ids() -> None:
    manifest = check_p1_2_proof_obligations._load_json(MANIFEST_PATH)
    obligation_ids = {item["id"] for item in manifest["obligations"]}

    assert check_p1_2_proof_obligations.REQUIRED_OBLIGATION_IDS <= obligation_ids
    assert "PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS" in obligation_ids
    assert manifest["phase_gate_required_anchor"] == "v64_power_witness_representation_env_guard"


def test_p1_2_proof_obligation_gate_rejects_boolean_schema_version() -> None:
    with pytest.raises(check_p1_2_proof_obligations.CheckError, match="schema_version must be an integer"):
        check_p1_2_proof_obligations._require_int(True, "schema_version")


def test_p1_2_proof_obligation_manifest_is_strict_json(tmp_path: Path) -> None:
    duplicate_key_manifest = tmp_path / "duplicate.json"
    duplicate_key_manifest.write_text('{"schema_version": 1, "schema_version": 1}', encoding="utf-8")

    with pytest.raises(check_p1_2_proof_obligations.CheckError, match="duplicate JSON object key"):
        check_p1_2_proof_obligations._load_json(duplicate_key_manifest)


def test_p1_2_proof_obligation_manifest_lists_replay_regressions() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    replay_obligation = next(
        item for item in manifest["obligations"] if item["id"] == "PO-CERTIFIED-CUT-REPLAY-FAITHFULNESS"
    )

    required_tests = set(replay_obligation["required_tests"])
    assert "test_persisted_cut_replay_fails_closed_on_unresolved_conflict_member" in required_tests
    assert "test_coordinate_replay_alias_collision_fails_closed_instead_of_one_literal_ban" in required_tests
    assert "test_pose_bool_replay_alias_collision_fails_closed" in required_tests
    assert "test_legacy_benders_cut_alias_collision_fails_closed" in required_tests
    assert "test_v63_outer_search_blocks_ghost_anchor_filter_env_before_session" in required_tests
    assert (
        "test_exact_campaign_resume_rejects_certified_final_result_without_terminal_frontier_evidence"
        in required_tests
    )
    assert (
        "test_delivery_manifest_rejects_certified_status_without_terminal_frontier_evidence"
        in required_tests
    )
    assert (
        "test_inspector_hides_stale_final_result_without_terminal_frontier_evidence"
        in required_tests
    )
    assert (
        "test_b5a_anchor_sprint_does_not_promote_stale_certified_final_result"
        in required_tests
    )
