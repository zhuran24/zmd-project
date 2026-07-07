"""P1.2-FIX-3 red tests: the manual phase gate is bound to the FIX-1 fixed-witness verifier.

These tests pin the PHASE-GATE-STRUCTURE soundness fix: a closed / next_allowed
phase gate may no longer be accepted on JSON shape + acknowledgement alone.  The
gate's witness-bound close condition requires the fixed-witness terminal verifier
to be present and wired into the certified publish path, and that requirement is
enforced for every gate state (so lifting the stay-blocked sentinel never silently
drops it).
"""

from __future__ import annotations

from pathlib import Path

from scripts import check_p1_2_proof_obligations
from scripts import check_phase_review_gate

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = PROJECT_ROOT / "data" / "review_gates" / "phase_1_2_spike_close.json"


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_p1_2_fix_3_phase_gate_requires_fixed_witness_verifier_present(
    tmp_path: Path,
    monkeypatch,
) -> None:
    # A verifier module that drops one of the required public entry points must
    # fail the gate, even though the real gate JSON is otherwise consistent.
    stub = _write(
        tmp_path / "terminal_fixed_witness_verifier.py",
        "def verify_terminal_fixed_witness():\n    return None\n",
    )
    monkeypatch.setattr(check_phase_review_gate, "FIXED_WITNESS_VERIFIER_PATH", stub)
    _summary, errors = check_phase_review_gate.check_gate(GATE_PATH)
    assert any(
        "must define project_terminal_fixed_witness_records_for_sink" in error
        for error in errors
    )

    # A missing verifier module fails closed.
    monkeypatch.setattr(
        check_phase_review_gate,
        "FIXED_WITNESS_VERIFIER_PATH",
        tmp_path / "does_not_exist.py",
    )
    _summary, errors = check_phase_review_gate.check_gate(GATE_PATH)
    assert any("fixed-witness terminal verifier missing" in error for error in errors)


def test_p1_2_fix_3_phase_gate_requires_fixed_witness_close_binding_call() -> None:
    # The gate checker's close binding must actually consult the verifier.
    binding_errors = check_phase_review_gate._check_fixed_witness_close_binding()
    assert binding_errors == []
    presence_errors = check_phase_review_gate._fixed_witness_verifier_functions_present()
    assert presence_errors == []


def test_p1_2_fix_3_phase_gate_witness_bound_close_condition_stays_blocked() -> None:
    # Historical name. Owner 2026-07-07 closed P1.2 / opened P1.3B, so the stay-blocked
    # sentinel is lifted (next_allowed=True no longer forces a "must remain blocked" error).
    # What REMAINS enforced — unconditionally, per the function's design — is the fixed-witness
    # publish binding; it passes for BOTH gate states here because the real publish path is wired.
    for next_allowed in (True, False):
        binding = check_p1_2_proof_obligations._check_phase_gate_fixed_witness_close_binding(
            next_allowed=next_allowed
        )
        assert binding == []


def test_p1_2_fix_3_publish_binding_detects_unwired_verifier(tmp_path: Path) -> None:
    # Real publish path is wired -> no errors.
    assert check_p1_2_proof_obligations._fixed_witness_publish_binding_errors() == []

    # A publish path that no longer calls the fixed-witness capsule fails closed.
    unwired_frontier = _write(
        tmp_path / "certified_frontier.py",
        "def build_sink_verified_terminal_frontier_evidence(**kwargs):\n    return {}\n",
    )
    unwired_campaign = _write(
        tmp_path / "exact_campaign.py",
        "def terminal_certified_final_result_violation_for_project(*args, **kwargs):\n"
        "    return _terminal_certified_final_result_violation_for_project_authority(\n"
        "        *args, **kwargs\n"
        "    )\n"
        "\n"
        "def _terminal_certified_final_result_violation_for_project_authority(\n"
        "    *args, **kwargs\n"
        "):\n"
        "    return None\n",
    )
    errors = check_p1_2_proof_obligations._fixed_witness_publish_binding_errors(
        certified_frontier_path=unwired_frontier,
        exact_campaign_path=unwired_campaign,
    )
    joined = "\n".join(errors)
    assert "must import build_terminal_fixed_witness_projection_at_sink" in joined
    assert "must call imported fixed-witness capsule symbol" in joined
    assert "project-bound terminal validator must gate on capsule field" in joined


def test_p1_2_fix_3_provenance_requires_check_gate_fixed_witness_binding(
    tmp_path: Path,
    monkeypatch,
) -> None:
    # The real provenance contract is satisfied.
    assert check_p1_2_proof_obligations._check_phase_gate_provenance_contract() == []

    # Removing the close-binding call from check_gate must be caught.
    source = check_p1_2_proof_obligations.PHASE_GATE_SCRIPT_PATH.read_text(encoding="utf-8")
    mutated = source.replace(
        "    errors.extend(_check_fixed_witness_close_binding())\n",
        "",
    )
    assert mutated != source, "fixture must remove the close-binding call"
    stub = _write(tmp_path / "check_phase_review_gate.py", mutated)
    monkeypatch.setattr(check_p1_2_proof_obligations, "PHASE_GATE_SCRIPT_PATH", stub)
    errors = check_p1_2_proof_obligations._check_phase_gate_provenance_contract()
    assert any(
        "check_gate must call _check_fixed_witness_close_binding" in error
        for error in errors
    )
