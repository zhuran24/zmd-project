from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import check_phase_review_gate


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = PROJECT_ROOT / "data" / "review_gates" / "phase_1_2_spike_close.json"


def test_phase_review_gate_manifest_is_consistent() -> None:
    summary, errors = check_phase_review_gate.check_gate(GATE_PATH)

    assert errors == []
    assert "phase_1_2_spike_close" in summary
    assert "clean=0/3" in summary
    assert "next_allowed=False" in summary


def test_require_ready_fails_while_phase_1_2_is_not_closed() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_phase_review_gate.py",
            "--require-ready",
            "phase_1_2_spike_close",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "phase_1_2_spike_close is not ready" in result.stdout
    assert "clean=0/3" in result.stdout


def test_validator_rejects_premature_next_phase_entry(tmp_path: Path) -> None:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["next_phase_entry"]["allowed"] = True
    bad_gate = tmp_path / "bad_gate.json"
    bad_gate.write_text(json.dumps(payload), encoding="utf-8")

    summary, errors = check_phase_review_gate.check_gate(bad_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("must not allow next phase entry" in error for error in errors)

def test_validator_rejects_premature_source_boundary_implementation(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    source_path = fake_root / "src" / "cuts" / "lifecycle.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "def step_8_apply_to_master(cut, master_model):\n"
        "    return None\n",
        encoding="utf-8",
    )

    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["last_reset"]["evidence_paths"] = []
    payload["review_history"][0]["evidence_paths"] = []
    payload["required_doc_markers"] = []
    gate_path = fake_root / "phase_gate.json"
    gate_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(gate_path)

    assert "phase_1_2_spike_close" in summary
    assert any("source boundary no longer fail-closed" in error for error in errors)
