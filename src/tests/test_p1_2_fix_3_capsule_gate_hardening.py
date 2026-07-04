"""P1.2 FIX-3 capsule/phase-gate hardening regressions."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts import check_p1_2_proof_obligations
from scripts import check_phase_review_gate

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "data" / "proof_obligations" / "p1_2_proof_obligations.json"
GATE_PATH = PROJECT_ROOT / "data" / "review_gates" / "phase_1_2_spike_close.json"


def _manifest() -> dict[str, object]:
    return copy.deepcopy(check_p1_2_proof_obligations._load_json(MANIFEST_PATH))


def _gate_payload(anchor: str) -> dict[str, object]:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["current_review_anchor"] = anchor
    payload["owner_manual_state"]["current_review_anchor"] = anchor
    return payload


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_fix_3_unknown_review_anchor_fails_closed(tmp_path: Path, monkeypatch) -> None:
    manifest = _manifest()
    unknown_anchor = "v100_unreviewed_reseal_probe"
    manifest["review_anchor"] = unknown_anchor
    manifest["phase_gate_required_anchor"] = unknown_anchor
    manifest["close_kernel_contract"]["review_anchor"] = unknown_anchor
    phase_gate = _write_json(tmp_path / "phase_gate.json", _gate_payload(unknown_anchor))
    monkeypatch.setattr(check_p1_2_proof_obligations, "PHASE_GATE_PATH", phase_gate)

    contract_errors = check_p1_2_proof_obligations._check_close_kernel_contract(manifest)
    anchor_errors = check_p1_2_proof_obligations._check_phase_anchor(manifest)
    joined = "\n".join(contract_errors + anchor_errors)

    assert "review_anchor must equal approved checker anchor" in joined
    assert "phase_gate_required_anchor must equal approved checker anchor" in joined
    assert "close_kernel_contract.review_anchor must equal approved checker anchor" in joined
    assert "phase gate current_review_anchor must equal approved checker anchor" in joined
    assert "phase gate owner_manual_state.current_review_anchor must equal approved checker anchor" in joined


def test_fix_3_coordinated_anchor_and_source_hash_reseal_is_rejected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    manifest = _manifest()
    unknown_anchor = "v100_unreviewed_reseal_probe"
    manifest["review_anchor"] = unknown_anchor
    manifest["phase_gate_required_anchor"] = unknown_anchor
    manifest["close_kernel_contract"]["review_anchor"] = unknown_anchor
    for entry in manifest["close_kernel_contract"]["sink_files"]:
        if entry["path"] == "src/search/terminal_fixed_witness_verifier.py":
            entry["source_sha256"] = "0" * 64
            break
    phase_gate = _write_json(tmp_path / "phase_gate.json", _gate_payload(unknown_anchor))
    monkeypatch.setattr(check_p1_2_proof_obligations, "PHASE_GATE_PATH", phase_gate)

    errors = (
        check_p1_2_proof_obligations._check_close_kernel_contract(manifest)
        + check_p1_2_proof_obligations._check_phase_anchor(manifest)
    )

    assert any(
        "src/search/terminal_fixed_witness_verifier.py v99 source_sha256 changed without checker-floor reseal"
        in error
        for error in errors
    )
    assert any("must equal approved checker anchor" in error for error in errors)


def test_fix_3_v99_static_floor_runs_without_any_v99_anchor() -> None:
    manifest = _manifest()
    unknown_anchor = "v100_unreviewed_reseal_probe"
    manifest["review_anchor"] = unknown_anchor
    manifest["phase_gate_required_anchor"] = unknown_anchor
    manifest["close_kernel_contract"]["review_anchor"] = unknown_anchor
    manifest["close_kernel_contract"]["proof_bearing_tokens"] = [
        token
        for token in manifest["close_kernel_contract"]["proof_bearing_tokens"]
        if token != "proof_bearing"
    ]

    errors = check_p1_2_proof_obligations._check_close_kernel_contract(manifest)

    assert "close_kernel_contract.proof_bearing_tokens missing v99 sealed token: proof_bearing" in errors


def test_fix_3_phase_checker_rejects_two_empty_function_verifier_stub(
    tmp_path: Path,
    monkeypatch,
) -> None:
    verifier_stub = _write(
        tmp_path / "terminal_fixed_witness_verifier.py",
        "def project_terminal_fixed_witness_records_for_sink(*args, **kwargs):\n"
        "    return None\n",
    )
    core_stub = _write(
        tmp_path / "pr2_l0_fixed_witness_core.py",
        "def verify_terminal_fixed_witness(*args, **kwargs):\n"
        "    return None\n\n"
        "def _project_terminal_fixed_witness_records_from_capsule(*args, **kwargs):\n"
        "    return None\n",
    )
    monkeypatch.setattr(check_phase_review_gate, "FIXED_WITNESS_VERIFIER_PATH", verifier_stub)
    monkeypatch.setattr(check_phase_review_gate, "FIXED_WITNESS_CORE_PATH", core_stub)

    _summary, errors = check_phase_review_gate.check_gate(GATE_PATH)

    assert any("verify_terminal_fixed_witness must rerun binding and routing" in error for error in errors)
    assert any("fixed-witness projection must demote rejected terminal records" in error for error in errors)


def test_fix_3_phase_checker_rejects_fake_capsule_projection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_capsule = _write(
        tmp_path / "terminal_fixed_witness_capsule.py",
        "def build_terminal_fixed_witness_projection_at_sink(*args, **kwargs):\n"
        "    return None\n",
    )
    monkeypatch.setattr(check_phase_review_gate, "FIXED_WITNESS_CAPSULE_PATH", fake_capsule)

    _summary, errors = check_phase_review_gate.check_gate(GATE_PATH)

    assert any("fixed-witness capsule must invoke isolated replay" in error for error in errors)
    assert any("fixed-witness capsule response must gate publishable verdicts" in error for error in errors)


def test_fix_3_capsule_name_guard_dead_branch_manifest_reseal_is_rejected(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    fake_capsule = _write(
        project_root / "src" / "search" / "terminal_fixed_witness_capsule.py",
        "_NEVER = False\n\n"
        "def _invoke_isolated_capsule(*args, **kwargs):\n"
        "    nonce = 'decoy'\n"
        "    if _NEVER:\n"
        "        subprocess.run(['python', \"-I\"], check=False)\n"
        "    return {'nonce': nonce}\n\n"
        "def _verdict_from_capsule_response(payload):\n"
        "    return payload\n\n"
        "def _capsule_response_violation(*args, **kwargs):\n"
        "    return None\n\n"
        "def _project_terminal_fixed_witness_records_from_capsule(*args, **kwargs):\n"
        "    return kwargs\n\n"
        "def build_terminal_fixed_witness_projection_at_sink(*args, **kwargs):\n"
        "    if _NEVER:\n"
        "        response = _invoke_isolated_capsule(*args, **kwargs)\n"
        "        verdict = _verdict_from_capsule_response(response.get('verdict'))\n"
        "        reason = _capsule_response_violation(response=response, verdict=verdict)\n"
        "        return _project_terminal_fixed_witness_records_from_capsule(reason=reason)\n"
        "    return type(\n"
        "        'Projection',\n"
        "        (),\n"
        "        {'publishable': True, 'projected_status': 'CERTIFIED'},\n"
        "    )()\n\n"
        "def _execute_isolated_capsule_request(request):\n"
        "    if _NEVER:\n"
        "        from src.search.terminal_fixed_witness_verifier import verify_terminal_fixed_witness\n"
        "        verify_terminal_fixed_witness(state=request, project_root='.')\n"
        "    return {'verdict': {'publishable': True}}\n",
    )
    manifest = _manifest()
    capsule_entry = next(
        entry
        for entry in manifest["close_kernel_contract"]["sink_files"]
        if entry["path"] == "src/search/terminal_fixed_witness_capsule.py"
    )
    capsule_entry["source_sha256"] = check_p1_2_proof_obligations._sha256_file(fake_capsule)

    wiring_errors = check_p1_2_proof_obligations._fixed_witness_capsule_wiring_errors(
        capsule_path=fake_capsule
    )
    phase_errors = check_phase_review_gate._fixed_witness_capsule_semantics_errors(path=fake_capsule)
    contract_errors = check_p1_2_proof_obligations._check_close_kernel_contract(
        manifest,
        project_root=project_root,
    )

    assert "fixed-witness capsule must call _invoke_isolated_capsule" in wiring_errors
    assert "fixed-witness capsule must launch an external subprocess" in wiring_errors
    assert any("fixed-witness capsule must invoke isolated replay" in error for error in phase_errors)
    assert any(
        "fixed-witness capsule isolated replay must launch python -I with a nonce" in error
        for error in phase_errors
    )
    assert (
        "src/search/terminal_fixed_witness_capsule.py v99 source_sha256 changed without "
        "checker-floor reseal"
    ) in contract_errors
    assert (
        "src/search/terminal_fixed_witness_capsule.py current source hash drifted from the "
        "v99 sealed floor"
    ) in contract_errors


def test_fix_3_publish_wiring_rejects_required_symbol_shadowing(tmp_path: Path) -> None:
    good_frontier = _write(
        tmp_path / "good_frontier.py",
        "from src.search.terminal_fixed_witness_capsule import build_terminal_fixed_witness_projection_at_sink\n\n"
        "def build_sink_verified_terminal_frontier_evidence(**kwargs):\n"
        "    fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(**kwargs)\n"
        "    replayed_records = fixed_witness_projection.durable_candidate_records\n"
        "    return {\n"
        "        'candidate_records': replayed_records,\n"
        "        'public_candidate_records': fixed_witness_projection.candidate_records,\n"
        "        'fixed_witness_verdict': fixed_witness_projection.verdict.to_dict(),\n"
        "        'fixed_witness_publishable': bool(fixed_witness_projection.publishable),\n"
        "    }\n",
    )
    shadowed_frontier = _write(
        tmp_path / "shadowed_frontier.py",
        "from src.search.terminal_fixed_witness_capsule import build_terminal_fixed_witness_projection_at_sink\n\n"
        "def build_sink_verified_terminal_frontier_evidence(**kwargs):\n"
        "    def build_terminal_fixed_witness_projection_at_sink(**inner):\n"
        "        return inner\n"
        "    fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(**kwargs)\n"
        "    replayed_records = fixed_witness_projection.durable_candidate_records\n"
        "    return {\n"
        "        'candidate_records': replayed_records,\n"
        "        'public_candidate_records': fixed_witness_projection.candidate_records,\n"
        "        'fixed_witness_verdict': fixed_witness_projection.verdict.to_dict(),\n"
        "        'fixed_witness_publishable': bool(fixed_witness_projection.publishable),\n"
        "    }\n",
    )
    good_campaign = _write(
        tmp_path / "good_campaign.py",
        "from src.search.terminal_fixed_witness_capsule import build_terminal_fixed_witness_projection_at_sink\n\n"
        "def terminal_certified_final_result_violation_for_project(state, *, project_root, campaign_path=None):\n"
        "    return _terminal_certified_final_result_violation_for_project_authority(\n"
        "        state, project_root=project_root, campaign_path=campaign_path,\n"
        "    )\n\n"
        "def _terminal_certified_final_result_violation_for_project_authority(state, *, project_root, campaign_path):\n"
        "    fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(state=state)\n"
        "    replayed_records = fixed_witness_projection.candidate_records\n"
        "    return terminal_certified_final_result_violation(\n"
        "        {'candidates': replayed_records},\n"
        "        candidate_records_override=replayed_records,\n"
        "    )\n",
    )
    param_shadow_campaign = _write(
        tmp_path / "param_shadow_campaign.py",
        "from src.search.terminal_fixed_witness_capsule import build_terminal_fixed_witness_projection_at_sink\n\n"
        "def terminal_certified_final_result_violation_for_project(\n"
        "    state, *, project_root, campaign_path=None\n"
        "):\n"
        "    return _terminal_certified_final_result_violation_for_project_authority(\n"
        "        state, project_root=project_root, campaign_path=campaign_path,\n"
        "    )\n\n"
        "def _terminal_certified_final_result_violation_for_project_authority(\n"
        "    state, *, project_root, campaign_path, build_terminal_fixed_witness_projection_at_sink=None\n"
        "):\n"
        "    fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(state=state)\n"
        "    replayed_records = fixed_witness_projection.candidate_records\n"
        "    return terminal_certified_final_result_violation(\n"
        "        {'candidates': replayed_records},\n"
        "        candidate_records_override=replayed_records,\n"
        "    )\n",
    )

    nested_errors = check_p1_2_proof_obligations._fixed_witness_publish_binding_errors(
        certified_frontier_path=shadowed_frontier,
        exact_campaign_path=good_campaign,
    )
    param_errors = check_p1_2_proof_obligations._fixed_witness_publish_binding_errors(
        certified_frontier_path=good_frontier,
        exact_campaign_path=param_shadow_campaign,
    )

    assert any("shadows imported fixed-witness capsule symbol" in error for error in nested_errors)
    assert any("shadows imported fixed-witness capsule symbol" in error for error in param_errors)


def test_fix_3_publish_wiring_rejects_dead_branch_capsule_call(tmp_path: Path) -> None:
    dead_frontier = _write(
        tmp_path / "dead_frontier.py",
        "from src.search.terminal_fixed_witness_capsule import build_terminal_fixed_witness_projection_at_sink\n\n"
        "def build_sink_verified_terminal_frontier_evidence(**kwargs):\n"
        "    if 0:\n"
        "        fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(**kwargs)\n"
        "    return {}\n",
    )
    good_campaign = _write(
        tmp_path / "good_campaign.py",
        "from src.search.terminal_fixed_witness_capsule import build_terminal_fixed_witness_projection_at_sink\n\n"
        "def terminal_certified_final_result_violation_for_project(state, *, project_root, campaign_path=None):\n"
        "    return _terminal_certified_final_result_violation_for_project_authority(\n"
        "        state, project_root=project_root, campaign_path=campaign_path,\n"
        "    )\n\n"
        "def _terminal_certified_final_result_violation_for_project_authority(state, *, project_root, campaign_path):\n"
        "    fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(state=state)\n"
        "    replayed_records = fixed_witness_projection.candidate_records\n"
        "    return terminal_certified_final_result_violation(\n"
        "        {'candidates': replayed_records},\n"
        "        candidate_records_override=replayed_records,\n"
        "    )\n",
    )

    errors = check_p1_2_proof_obligations._fixed_witness_publish_binding_errors(
        certified_frontier_path=dead_frontier,
        exact_campaign_path=good_campaign,
    )

    assert any("reachable main path" in error for error in errors)


@pytest.mark.parametrize(
    ("case_name", "dead_call_source"),
    [
        (
            "if_not_true",
            "    if not True:\n"
            "        fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(**kwargs)\n",
        ),
        (
            "if_not_true_name",
            "    if not _ALWAYS:\n"
            "        fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(**kwargs)\n",
        ),
        (
            "ifexp_dead_body",
            "    fixed_witness_projection = (\n"
            "        build_terminal_fixed_witness_projection_at_sink(**kwargs) if _NEVER else None\n"
            "    )\n",
        ),
        (
            "boolop_false_and",
            "    _NEVER and build_terminal_fixed_witness_projection_at_sink(**kwargs)\n",
        ),
        (
            "post_return",
            "    return {}\n"
            "    fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(**kwargs)\n",
        ),
    ],
)
def test_fix_3_publish_wiring_rejects_runtime_dead_capsule_call_forms(
    tmp_path: Path,
    case_name: str,
    dead_call_source: str,
) -> None:
    dead_frontier = _write(
        tmp_path / f"dead_frontier_{case_name}.py",
        "_NEVER = False\n"
        "_ALWAYS = True\n"
        "from src.search.terminal_fixed_witness_capsule import build_terminal_fixed_witness_projection_at_sink\n\n"
        "def build_sink_verified_terminal_frontier_evidence(**kwargs):\n"
        f"{dead_call_source}"
        "    return {}\n",
    )
    good_campaign = _write(
        tmp_path / f"good_campaign_{case_name}.py",
        "from src.search.terminal_fixed_witness_capsule import build_terminal_fixed_witness_projection_at_sink\n\n"
        "def terminal_certified_final_result_violation_for_project(state, *, project_root, campaign_path=None):\n"
        "    return _terminal_certified_final_result_violation_for_project_authority(\n"
        "        state, project_root=project_root, campaign_path=campaign_path,\n"
        "    )\n\n"
        "def _terminal_certified_final_result_violation_for_project_authority(state, *, project_root, campaign_path):\n"
        "    fixed_witness_projection = build_terminal_fixed_witness_projection_at_sink(state=state)\n"
        "    replayed_records = fixed_witness_projection.candidate_records\n"
        "    return terminal_certified_final_result_violation(\n"
        "        {'candidates': replayed_records},\n"
        "        candidate_records_override=replayed_records,\n"
        "    )\n",
    )

    errors = check_p1_2_proof_obligations._fixed_witness_publish_binding_errors(
        certified_frontier_path=dead_frontier,
        exact_campaign_path=good_campaign,
    )

    assert any("reachable main path" in error for error in errors)


@pytest.mark.parametrize(
    "body_source",
    [
        "    if runtime_var:\n"
        "        build_terminal_fixed_witness_projection_at_sink()\n",
        "    for item in items:\n"
        "        build_terminal_fixed_witness_projection_at_sink(item)\n",
        "    with manager:\n"
        "        build_terminal_fixed_witness_projection_at_sink()\n",
        "    try:\n"
        "        build_terminal_fixed_witness_projection_at_sink()\n"
        "    except Exception:\n"
        "        pass\n",
    ],
)
def test_fix_3_reachable_call_keeps_runtime_control_flow_live(
    tmp_path: Path,
    body_source: str,
) -> None:
    source = _write(
        tmp_path / "runtime_control_flow.py",
        "def build_terminal_fixed_witness_projection_at_sink(*args, **kwargs):\n"
        "    return None\n\n"
        "def wrapper(runtime_var, items, manager):\n"
        f"{body_source}",
    )
    tree = check_p1_2_proof_obligations._parse_python(source)
    wrapper = check_p1_2_proof_obligations._function_def(tree, "wrapper", path=source)

    assert check_p1_2_proof_obligations._direct_calls_name(
        wrapper,
        "build_terminal_fixed_witness_projection_at_sink",
    )


@pytest.mark.parametrize(
    ("case_name", "dead_call_source"),
    [
        (
            "if_not_true",
            "    if not True:\n"
            "        response = _invoke_isolated_capsule(*args, **kwargs)\n"
            "    else:\n"
            "        response = None\n",
        ),
        (
            "if_not_true_name",
            "    if not _ALWAYS:\n"
            "        response = _invoke_isolated_capsule(*args, **kwargs)\n"
            "    else:\n"
            "        response = None\n",
        ),
        (
            "ifexp_dead_body",
            "    response = _invoke_isolated_capsule(*args, **kwargs) if _NEVER else None\n",
        ),
        (
            "boolop_false_and",
            "    response = None\n"
            "    _NEVER and _invoke_isolated_capsule(*args, **kwargs)\n",
        ),
        (
            "post_return",
            "    response = None\n"
            "    verdict = _verdict_from_capsule_response({})\n"
            "    reason = _capsule_response_violation(response=response, verdict=verdict)\n"
            "    result = _project_terminal_fixed_witness_records_from_capsule(reason=reason)\n"
            "    return result\n"
            "    response = _invoke_isolated_capsule(*args, **kwargs)\n",
        ),
    ],
)
def test_fix_3_phase_capsule_rejects_runtime_dead_isolated_replay_forms(
    tmp_path: Path,
    case_name: str,
    dead_call_source: str,
) -> None:
    fake_capsule = _write(
        tmp_path / f"terminal_fixed_witness_capsule_{case_name}.py",
        "import subprocess\n\n"
        "_NEVER = False\n"
        "_ALWAYS = True\n\n"
        "def _invoke_isolated_capsule(*args, **kwargs):\n"
        "    nonce = 'unit-nonce'\n"
        "    subprocess.run(['python', \"-I\", nonce], check=False)\n"
        "    return {'nonce': nonce}\n\n"
        "def _verdict_from_capsule_response(payload):\n"
        "    return payload\n\n"
        "def _capsule_response_violation(*, response, verdict):\n"
        "    if verdict.publishable and verdict.binding_status == \"FEASIBLE\" and verdict.routing_status == \"FEASIBLE\":\n"
        "        return None\n"
        "    return 'rejected'\n\n"
        "def _project_terminal_fixed_witness_records_from_capsule(*args, **kwargs):\n"
        "    return kwargs\n\n"
        "def build_terminal_fixed_witness_projection_at_sink(*args, **kwargs):\n"
        f"{dead_call_source}"
        "    verdict = _verdict_from_capsule_response({})\n"
        "    reason = _capsule_response_violation(response=response, verdict=verdict)\n"
        "    return _project_terminal_fixed_witness_records_from_capsule(reason=reason)\n\n"
        "def _execute_isolated_capsule_request(request):\n"
        "    from src.search.terminal_fixed_witness_verifier import verify_terminal_fixed_witness\n"
        "    compute_exact_artifact_hashes = None\n"
        "    _materialize_replay_snapshot = None\n"
        "    canonical_state_bytes_for_fixed_witness = None\n"
        "    return verify_terminal_fixed_witness(request)\n",
    )

    errors = check_phase_review_gate._fixed_witness_capsule_semantics_errors(path=fake_capsule)

    assert "fixed-witness capsule must invoke isolated replay" in errors


def test_fix_3_structure_gate_sources_must_be_in_v99_source_floor(monkeypatch) -> None:
    victim = "src/search/new_structure_checked_sink.py"
    manifest = _manifest()
    monkeypatch.setattr(
        check_p1_2_proof_obligations,
        "CLOSE_KERNEL_V99_STRUCTURAL_GATE_SOURCE_PATHS",
        check_p1_2_proof_obligations.CLOSE_KERNEL_V99_STRUCTURAL_GATE_SOURCE_PATHS
        | {victim},
    )

    errors = check_p1_2_proof_obligations._check_close_kernel_contract(manifest)

    assert (
        f"{victim} is structurally checked by P1.2 gates but missing from "
        "the v99 source-hash floor"
    ) in errors


def test_fix_3_current_phase_gate_stays_blocked() -> None:
    summary, errors = check_phase_review_gate.check_gate(GATE_PATH)

    assert errors == []
    assert "status=blocked_manual_review_count" in summary
    assert "next_allowed=False" in summary
