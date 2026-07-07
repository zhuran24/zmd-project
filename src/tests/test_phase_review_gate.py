from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import check_phase_review_gate

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = PROJECT_ROOT / "data" / "review_gates" / "phase_1_2_spike_close.json"


def _load_payload() -> dict:
    # Negative/mutation tests below need a valid BLOCKED base regardless of the committed
    # gate's current owner-close state (owner closed P1.2 on 2026-07-07). Load the committed
    # gate for its boilerplate (manual_review_standard, informational_history, ...) but reset
    # the decision fields to the blocked baseline so each test mutates a known-blocked gate.
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["status"] = "blocked_manual_review_count"
    payload.get("owner_manual_state", {})["p1_2_close_status"] = "not_closed"
    payload.get("owner_manual_state", {})["p1_3b_entry_allowed"] = False
    payload.get("next_phase_entry", {})["allowed"] = False
    payload.pop("owner_manual_decision", None)
    return payload


def _write_gate(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "phase_1_2_spike_close.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _manual_decision() -> dict:
    return {
        "p1_3b_entry_allowed": True,
        "counting_authority": "owner_manual_count_outside_repo",
        "decision_id": "owner-v50-manual-fixture",
        "decided_by": "owner",
        "decided_at": "2026-06-08",
        "decision_note": "Owner manually verified three clean reviews outside repo-derived automation.",
        "acknowledges_repo_does_not_prove_clean_count": True,
        "acknowledges_owner_verified_three_clean_reviews": True,
    }


def test_phase_review_gate_manifest_is_consistent() -> None:
    # Since owner 2026-07-07 closed P1.2 and opened P1.3 via owner_manual_decision,
    # the committed gate is a valid owner-closed shape (next_allowed=True).
    summary, errors = check_phase_review_gate.check_gate(GATE_PATH)
    assert errors == []
    assert "phase_1_2_spike_close" in summary
    assert "next_allowed=True" in summary
    assert "owner_manual_count_outside_repo" in summary


def test_require_ready_fails_while_manual_gate_blocked() -> None:
    # Historical name. Since owner 2026-07-07 opened P1.3 via owner_manual_decision,
    # --require-ready now PASSES for the committed gate (returncode 0). This guards that
    # the committed gate is a valid owner-opened state that --require-ready accepts.
    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_phase_review_gate.py",
            "--require-ready",
            "phase_1_2_spike_close",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "status=closed_manual_owner_decision" in result.stdout
    assert "next_allowed=True" in result.stdout


def test_manual_gate_rejects_auto_counter_fields(tmp_path: Path) -> None:
    payload = _load_payload()
    payload["counters"] = {
        "consecutive_clean_full_reviews_after_reset": 3,
        "required_consecutive_clean_full_reviews": 3,
        "remaining_clean_full_reviews": 0,
    }
    path = _write_gate(tmp_path, payload)
    _summary, errors = check_phase_review_gate.check_gate(path)
    assert any("repo-derived clean-count authority key: counters" in error for error in errors)


def test_manual_gate_rejects_next_phase_allowed_without_owner_decision(tmp_path: Path) -> None:
    payload = _load_payload()
    payload["next_phase_entry"]["allowed"] = True
    payload["owner_manual_state"]["p1_3b_entry_allowed"] = True
    payload["status"] = "closed_manual_owner_decision"
    path = _write_gate(tmp_path, payload)
    _summary, errors = check_phase_review_gate.check_gate(path)
    assert any("owner_manual_decision must be an object" in error for error in errors)


def test_manual_gate_rejects_closed_status_without_owner_decision(tmp_path: Path) -> None:
    payload = _load_payload()
    payload["status"] = "closed_manual_owner_decision"
    path = _write_gate(tmp_path, payload)
    _summary, errors = check_phase_review_gate.check_gate(path)
    assert any("closed manual gate should allow P1.3 (machine field p1_3b_entry_allowed)" in error for error in errors)


def test_manual_gate_accepts_owner_decision_authority_fixture(tmp_path: Path) -> None:
    payload = _load_payload()
    payload["status"] = "closed_manual_owner_decision"
    payload["next_phase_entry"]["allowed"] = True
    payload["owner_manual_state"]["p1_3b_entry_allowed"] = True
    payload["owner_manual_decision"] = _manual_decision()
    path = _write_gate(tmp_path, payload)
    _summary, errors = check_phase_review_gate.check_gate(path)
    assert errors == []


def test_manual_gate_receipts_are_informational_only(tmp_path: Path) -> None:
    payload = _load_payload()
    payload["receipt_policy"]["can_open_p1_3b"] = True
    path = _write_gate(tmp_path, payload)
    _summary, errors = check_phase_review_gate.check_gate(path)
    assert any("receipt_policy.can_open_p1_3b must be false" in error for error in errors)


def test_manual_gate_requires_step_8_fail_closed_when_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_lifecycle = tmp_path / "lifecycle.py"
    fake_lifecycle.write_text(
        "def step_8_apply_to_master(cut, master):\n    return None\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_phase_review_gate, "LIFECYCLE_PATH", fake_lifecycle)
    # This invariant is about the BLOCKED gate state (next_allowed=false); the committed
    # gate is owner-closed since 2026-07-07 (next_allowed=true, where step_8 is unconstrained),
    # so test the boundary on a synthetic blocked gate.
    blocked_gate = _write_gate(tmp_path, _load_payload())
    summary, errors = check_phase_review_gate.check_gate(blocked_gate)
    assert "phase_1_2_spike_close" in summary
    assert any("step_8_apply_to_master must remain fail-closed" in error for error in errors)


def test_json_loader_rejects_duplicate_keys(tmp_path: Path) -> None:
    fake_gate = tmp_path / "dup.json"
    fake_gate.write_text(
        '{"schema_version": 2, "schema_version": 2, "gate_id": "phase_1_2_spike_close"}',
        encoding="utf-8",
    )
    with pytest.raises(check_phase_review_gate.GateError, match="duplicate JSON object key"):
        check_phase_review_gate.load_gate(fake_gate)


def test_json_loader_rejects_boolean_schema_version(tmp_path: Path) -> None:
    payload = _load_payload()
    payload["schema_version"] = True
    path = _write_gate(tmp_path, payload)
    _summary, errors = check_phase_review_gate.check_gate(path)
    assert any("schema_version must be an integer" in error for error in errors)


def test_manual_gate_rejects_receipt_auto_authority_in_standard(tmp_path: Path) -> None:
    payload = _load_payload()
    payload["manual_review_standard"]["repo_derives_clean_count_from_receipts"] = True
    path = _write_gate(tmp_path, payload)
    _summary, errors = check_phase_review_gate.check_gate(path)
    assert any("repo must not derive clean-review count from receipts" in error for error in errors)
