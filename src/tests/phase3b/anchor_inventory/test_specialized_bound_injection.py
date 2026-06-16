from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.anchor_inventory.specialized_bound_injection import (
    build_phase3b_anchor_specialized_bound_injection_spec,
    render_phase3b_anchor_specialized_bound_injection_markdown,
    render_phase3b_anchor_specialized_bound_injection_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _direct_slice_payload(*, bound: int = 526, u_var_index: int | None = 1234) -> dict:
    direct_entry = {
        "anchor_idx": 119,
        "variant": "target_power_family_bound_direct_after_force",
        "status": "OPTIMAL",
        "branches": 0,
        "conflicts": 0,
        "u_var_index": u_var_index,
        "relaxed_power_family": "family_009",
        "relaxed_power_family_count_var_index": 54590,
        "relaxed_power_family_count_value": 0,
        "relaxed_conditioned_power_family_bound_constraints_removed": 1,
        "replacement_bound_mode": "direct_after_force",
        "replacement_conditioned_power_family_bound": bound,
        "removed_conditioned_power_family_bound_payload": {
            "removed_constraint_count": 1,
            "removed_constraint_indices": [140428],
            "implied_conditioned_upper_bound": bound,
            "implied_global_upper_bound": 612,
        },
    }
    if u_var_index is None:
        direct_entry.pop("u_var_index")
    return {
        "metadata": {"source": "phase3b_forced_anchor_model_slice_diagnostic_v1"},
        "campaign_state_unchanged": True,
        "candidate": {"key": "67x13"},
        "profile": {
            "selected_anchor_indices": [119],
            "target_power_family": "family_009",
        },
        "slice_matrix": {
            "entries": [
                {
                    "anchor_idx": 119,
                    "variant": "base",
                    "status": "UNKNOWN",
                    "branches": 0,
                    "conflicts": 0,
                },
                direct_entry,
            ]
        },
    }


def _semantic_payload(*, bound: int = 526) -> dict:
    return {
        "metadata": {"source": "phase3b_family_bound_semantic_audit_v1"},
        "candidate": {"key": "67x13"},
        "classification": "solver_sensitivity_without_bound_violation",
        "family_bound": {
            "candidate_key": "67x13",
            "all_bounds_consistent": True,
            "anchor_idx": 119,
            "target_power_family": "family_009",
            "derived_conditioned_upper_bound": bound,
            "global_upper_bound": 612,
            "bounds_consistent": True,
        },
        "target_family_slice": {
            "target_status": "OPTIMAL",
            "relaxed_power_family": "family_009",
            "relaxed_power_family_count_value": 0,
            "relaxed_family_bound_violation": -bound,
        },
    }


def _formulation_payload(
    *,
    classification: str = "target_direct_terminal_enforced_unknown_all_family_direct_infeasible",
    all_family_status: str = "INFEASIBLE",
) -> dict:
    return {
        "metadata": {"source": "phase3b_family_bound_formulation_probe_v1"},
        "classification": classification,
        "comparison": {
            "base_status": "UNKNOWN",
            "direct_status": "OPTIMAL",
            "enforced_status": "UNKNOWN",
            "all_family_status": all_family_status,
            "all_family_replacement_count": 34,
            "direct_bound_value": 526,
            "direct_count_value": 0,
        },
    }


def _power_protocol_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_power_protocol_interaction_diagnostic_v1"},
        "analysis": {
            "primary_hypothesis": "target_family_only_direct_bound_injection_candidate",
            "next_actions": [
                "design_target_family_only_direct_bound_injection",
                "prove_single_family_substitution_equivalence_under_forced_anchor",
            ],
        },
        "recommendation": "target-family-only injection with proof-neutral checks",
    }


def test_anchor_specialized_injection_spec_is_diagnostic_ready(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    direct_path = project_root / "direct.json"
    semantic_path = project_root / "semantic.json"
    formulation_path = project_root / "formulation.json"
    power_protocol_path = project_root / "power_protocol.json"
    _write_json(direct_path, _direct_slice_payload())
    _write_json(semantic_path, _semantic_payload())
    _write_json(formulation_path, _formulation_payload())
    _write_json(power_protocol_path, _power_protocol_payload())

    report = build_phase3b_anchor_specialized_bound_injection_spec(
        project_root,
        direct_bound_slice_path=direct_path,
        family_bound_semantic_audit_path=semantic_path,
        family_bound_formulation_probe_path=formulation_path,
        power_protocol_interaction_path=power_protocol_path,
    )

    assert report["metadata"]["source"] == "phase3b_anchor_specialized_bound_injection_v1"
    assert report["gate"]["diagnostic_spec_ready"] is True
    assert report["gate"]["workspace_diagnostic_rerun_allowed"] is True
    assert report["gate"]["runtime_promotion_ready"] is False
    assert report["gate"]["proof_promotion_ready"] is False
    assert report["gate"]["final_long_run_ready"] is False
    target = report["injection_spec"]["target"]
    assert target["anchor_idx"] == 119
    assert target["u_var_index"] == 1234
    assert target["target_power_family"] == "family_009"
    assert target["conditioned_upper_bound"] == 526
    assert report["injection_spec"]["default_enabled"] is False
    assert _check_status(report, "semantic_bound_matches_direct_bound") == "pass"
    assert _check_status(report, "all_family_substitution_blocked") == "pass"

    markdown = render_phase3b_anchor_specialized_bound_injection_markdown(report)
    text = render_phase3b_anchor_specialized_bound_injection_text(report)
    assert "Anchor-Specialized Bound Injection" in markdown
    assert "default_enabled=False" in text
    assert "runtime_promotion_ready=False" in text


def test_anchor_specialized_injection_spec_fails_on_bound_mismatch(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    direct_path = project_root / "direct.json"
    semantic_path = project_root / "semantic.json"
    formulation_path = project_root / "formulation.json"
    power_protocol_path = project_root / "power_protocol.json"
    _write_json(direct_path, _direct_slice_payload(bound=525))
    _write_json(semantic_path, _semantic_payload(bound=526))
    _write_json(formulation_path, _formulation_payload())
    _write_json(power_protocol_path, _power_protocol_payload())

    report = build_phase3b_anchor_specialized_bound_injection_spec(
        project_root,
        direct_bound_slice_path=direct_path,
        family_bound_semantic_audit_path=semantic_path,
        family_bound_formulation_probe_path=formulation_path,
        power_protocol_interaction_path=power_protocol_path,
    )

    assert report["gate"]["diagnostic_spec_ready"] is False
    assert "semantic_bound_matches_direct_bound" in report["gate"]["failed_checks"]
    assert _check_status(report, "semantic_bound_matches_direct_bound") == "fail"


def test_anchor_specialized_injection_spec_requires_force_var_evidence(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    direct_path = project_root / "direct.json"
    semantic_path = project_root / "semantic.json"
    formulation_path = project_root / "formulation.json"
    power_protocol_path = project_root / "power_protocol.json"
    _write_json(direct_path, _direct_slice_payload(u_var_index=None))
    _write_json(semantic_path, _semantic_payload())
    _write_json(formulation_path, _formulation_payload())
    _write_json(power_protocol_path, _power_protocol_payload())

    report = build_phase3b_anchor_specialized_bound_injection_spec(
        project_root,
        direct_bound_slice_path=direct_path,
        family_bound_semantic_audit_path=semantic_path,
        family_bound_formulation_probe_path=formulation_path,
        power_protocol_interaction_path=power_protocol_path,
    )

    assert report["gate"]["diagnostic_spec_ready"] is False
    assert _check_status(report, "force_var_identified") == "fail"


def test_anchor_specialized_injection_spec_blocks_broad_substitution(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    direct_path = project_root / "direct.json"
    semantic_path = project_root / "semantic.json"
    formulation_path = project_root / "formulation.json"
    power_protocol_path = project_root / "power_protocol.json"
    _write_json(direct_path, _direct_slice_payload())
    _write_json(semantic_path, _semantic_payload())
    _write_json(formulation_path, _formulation_payload(all_family_status="OPTIMAL"))
    _write_json(power_protocol_path, _power_protocol_payload())

    report = build_phase3b_anchor_specialized_bound_injection_spec(
        project_root,
        direct_bound_slice_path=direct_path,
        family_bound_semantic_audit_path=semantic_path,
        family_bound_formulation_probe_path=formulation_path,
        power_protocol_interaction_path=power_protocol_path,
    )

    assert report["gate"]["diagnostic_spec_ready"] is False
    assert _check_status(report, "all_family_substitution_blocked") == "fail"


def test_anchor_specialized_injection_cli_writes_and_no_write_skips(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    direct_path = project_root / "direct.json"
    semantic_path = project_root / "semantic.json"
    formulation_path = project_root / "formulation.json"
    power_protocol_path = project_root / "power_protocol.json"
    output_dir = tmp_path / "out"
    _write_json(direct_path, _direct_slice_payload())
    _write_json(semantic_path, _semantic_payload())
    _write_json(formulation_path, _formulation_payload())
    _write_json(power_protocol_path, _power_protocol_payload())
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "anchor_inventory" / "build_specialized_bound_injection.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--direct-bound-slice",
            str(direct_path),
            "--family-bound-semantic-audit",
            str(semantic_path),
            "--family-bound-formulation-probe",
            str(formulation_path),
            "--power-protocol-interaction",
            str(power_protocol_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b anchor-specialized bound injection" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--direct-bound-slice",
            str(direct_path),
            "--family-bound-semantic-audit",
            str(semantic_path),
            "--family-bound-formulation-probe",
            str(formulation_path),
            "--power-protocol-interaction",
            str(power_protocol_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "anchor_specialized_bound_injection_json=" in write.stdout
    payload = json.loads(
        (output_dir / "anchor_specialized_bound_injection.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["gate"]["diagnostic_spec_ready"] is True
    assert (output_dir / "anchor_specialized_bound_injection.md").exists()
    assert (output_dir / "anchor_specialized_bound_injection.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
