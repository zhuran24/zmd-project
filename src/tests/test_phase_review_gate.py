from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import check_phase_review_gate


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = PROJECT_ROOT / "data" / "review_gates" / "phase_1_2_spike_close.json"


def _write_review_evidence(fake_root: Path, package: str) -> str:
    rel = Path("docs") / "research" / f"{package}.md"
    path = fake_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Review evidence for {package}\n\nPackage: {package}\n",
        encoding="utf-8",
    )
    return rel.as_posix()


def _payload_for_fake_root(fake_root: Path) -> dict:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["required_doc_markers"] = []
    payload["source_boundaries"] = []
    for entry in payload["review_history"]:
        entry["evidence_paths"] = [_write_review_evidence(fake_root, entry["package"])]
    payload["last_reset"]["evidence_paths"] = [
        _write_review_evidence(fake_root, payload["last_reset"]["review_package"])
    ]
    return payload


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
    for entry in payload["review_history"]:
        entry["evidence_paths"] = []
    payload["required_doc_markers"] = []
    gate_path = fake_root / "phase_gate.json"
    gate_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(gate_path)

    assert "phase_1_2_spike_close" in summary
    assert any("source boundary no longer fail-closed" in error for error in errors)


def test_validator_rejects_stale_last_reset_when_later_reset_history_exists(tmp_path: Path) -> None:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["review_history"].append(
        {
            "package": "v999_non_clean_probe",
            "review_type": "independent_full_external",
            "outcome": "major_soundness_findings_found",
            "clean": False,
            "major_or_soundness_findings": 1,
            "resets_counter": True,
            "evidence_paths": [],
        }
    )
    stale_gate = tmp_path / "stale_reset_gate.json"
    stale_gate.write_text(json.dumps(payload), encoding="utf-8")

    summary, errors = check_phase_review_gate.check_gate(stale_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("last_reset.review_package must match the latest resetting" in error for error in errors)


def test_validator_rejects_fake_closed_gate_without_post_reset_clean_reviews(tmp_path: Path) -> None:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    fake_gate = tmp_path / "fake_closed_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("review_history-derived" in error for error in errors)


def test_validator_rejects_fake_clean_reviews_without_evidence(tmp_path: Path) -> None:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    for index in range(3):
        payload["review_history"].append(
            {
                "package": f"v33_clean_full_review_{index + 1}",
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [],
            }
        )
    fake_gate = tmp_path / "fake_clean_reviews_without_evidence.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("evidence_paths must contain at least one" in error for error in errors)


def test_validator_rejects_fake_clean_reviews_with_nonreview_evidence(tmp_path: Path) -> None:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    for index in range(3):
        payload["review_history"].append(
            {
                "package": f"v35_fake_clean_{index + 1}",
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": ["README.md"],
            }
        )
    fake_gate = tmp_path / "fake_clean_reviews_with_nonreview_evidence.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("review/research artifact" in error for error in errors)
    assert any("must match review package" in error for error in errors)


def test_validator_rejects_reused_clean_review_evidence(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    shared_evidence = _write_review_evidence(fake_root, "v35_clean_shared")
    for index in range(3):
        payload["review_history"].append(
            {
                "package": "v35_clean_shared",
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [shared_evidence],
            }
        )
    fake_gate = fake_root / "fake_reused_clean_evidence.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("reuses clean-review evidence path" in error for error in errors)


def test_validator_accepts_closed_gate_with_three_post_reset_clean_reviews(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    for index in range(3):
        package = f"v33_clean_full_review_{index + 1}"
        payload["review_history"].append(
            {
                "package": package,
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [_write_review_evidence(fake_root, package)],
            }
        )
    closed_gate = fake_root / "closed_gate.json"
    closed_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(closed_gate)

    assert "phase_1_2_spike_close" in summary
    assert errors == []
