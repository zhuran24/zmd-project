"""Tests for the P1.2 proof-obligation consolidation gate."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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
    assert "P1.2 proof obligation check passed" in result.stdout


def test_p1_2_proof_obligation_gate_rejects_boolean_schema_version(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["schema_version"] = True
    fake_manifest = tmp_path / "p1_2_proof_obligations_bool_schema.json"
    fake_manifest.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr(check_p1_2_proof_obligations, "MANIFEST_PATH", fake_manifest)
    exit_code = check_p1_2_proof_obligations.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "schema_version must be an integer" in captured.out
