from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.search.phase3b.family_bound.formulation_probe import (
    build_phase3b_family_bound_formulation_probe,
    render_phase3b_family_bound_formulation_probe_markdown,
    render_phase3b_family_bound_formulation_probe_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _direct_slice_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_model_slice_diagnostic_v1"},
        "candidate": {"key": "67x13"},
        "campaign_state_unchanged": True,
        "slice_matrix": {
            "entries": [
                {
                    "variant": "base",
                    "status": "UNKNOWN",
                    "wall_time": 20.0,
                    "response_stats_parsed": {"deterministic_time": 5.0},
                },
                {
                    "variant": "target_power_family_bound_direct_after_force",
                    "status": "OPTIMAL",
                    "wall_time": 0.1,
                    "response_stats_parsed": {"deterministic_time": 0.01},
                    "replacement_bound_mode": "direct_after_force",
                    "replacement_conditioned_power_family_bound": 526,
                    "relaxed_power_family_count_value": 0,
                    "relaxed_conditioned_power_family_bound_constraints_removed": 1,
                },
            ]
        },
    }


def _enforced_slice_payload(status: str = "UNKNOWN") -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_model_slice_diagnostic_v1"},
        "candidate": {"key": "67x13"},
        "campaign_state_unchanged": True,
        "slice_matrix": {
            "entries": [
                {
                    "variant": "base",
                    "status": status,
                    "wall_time": 20.0,
                    "branches": 0,
                    "conflicts": 0,
                    "response_stats_parsed": {"deterministic_time": 5.0},
                }
            ]
        },
    }


def _all_family_slice_payload(status: str = "INFEASIBLE") -> dict:
    return {
        "metadata": {"source": "phase3b_forced_anchor_model_slice_diagnostic_v1"},
        "candidate": {"key": "67x13"},
        "campaign_state_unchanged": True,
        "slice_matrix": {
            "entries": [
                {
                    "variant": "all_conditioned_family_bounds_direct_after_force",
                    "status": status,
                    "wall_time": 0.02,
                    "direct_power_family_bound_replacement_count": 34,
                }
            ]
        },
    }


def _semantic_payload() -> dict:
    return {
        "metadata": {"source": "phase3b_family_bound_semantic_audit_v1"},
        "classification": "solver_sensitivity_without_bound_violation",
        "target_family_slice": {"relaxed_family_bound_violation": -526},
    }


def test_formulation_probe_classifies_direct_bound_replacement(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    slice_path = project_root / "slice.json"
    enforced_path = project_root / "enforced.json"
    all_family_path = project_root / "all_family.json"
    semantic_path = project_root / "semantic.json"
    _write_json(slice_path, _direct_slice_payload())
    _write_json(enforced_path, _enforced_slice_payload())
    _write_json(all_family_path, _all_family_slice_payload())
    _write_json(semantic_path, _semantic_payload())

    report = build_phase3b_family_bound_formulation_probe(
        project_root,
        direct_bound_slice_path=slice_path,
        enforced_formulation_slice_path=enforced_path,
        all_family_direct_bound_slice_path=all_family_path,
        family_bound_semantic_audit_path=semantic_path,
    )

    assert report["metadata"]["source"] == "phase3b_family_bound_formulation_probe_v1"
    assert report["classification"] == (
        "target_direct_terminal_enforced_unknown_all_family_direct_infeasible"
    )
    assert report["comparison"]["wall_time_speedup"] == 200.0
    assert report["comparison"]["enforced_status"] == "UNKNOWN"
    assert report["comparison"]["all_family_status"] == "INFEASIBLE"
    assert _check_status(report, "direct_solution_respects_bound") == "pass"
    assert "target-family anchor-specialized injection" in report["recommendation"]

    markdown = render_phase3b_family_bound_formulation_probe_markdown(report)
    text = render_phase3b_family_bound_formulation_probe_text(report)
    assert "Family Bound Formulation Probe" in markdown
    assert "classification=target_direct_terminal" in text


def test_formulation_probe_classifies_direct_bound_infeasible(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    slice_path = project_root / "slice.json"
    enforced_path = project_root / "enforced.json"
    all_family_path = project_root / "all_family.json"
    semantic_path = project_root / "semantic.json"
    direct_payload = _direct_slice_payload()
    direct_payload["slice_matrix"]["entries"][1]["status"] = "INFEASIBLE"
    direct_payload["slice_matrix"]["entries"][1][
        "relaxed_power_family_count_value"
    ] = None
    _write_json(slice_path, direct_payload)
    _write_json(enforced_path, _enforced_slice_payload())
    _write_json(all_family_path, _all_family_slice_payload())
    _write_json(semantic_path, _semantic_payload())

    report = build_phase3b_family_bound_formulation_probe(
        project_root,
        direct_bound_slice_path=slice_path,
        enforced_formulation_slice_path=enforced_path,
        all_family_direct_bound_slice_path=all_family_path,
        family_bound_semantic_audit_path=semantic_path,
    )

    assert report["classification"] == "direct_bound_replacement_infeasible"
    assert "stale" in report["recommendation"]
    assert _check_status(report, "direct_bound_terminal") == "fail"


def test_formulation_probe_cli_writes_and_no_write_skips(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    slice_path = project_root / "slice.json"
    enforced_path = project_root / "enforced.json"
    all_family_path = project_root / "all_family.json"
    semantic_path = project_root / "semantic.json"
    output_dir = tmp_path / "out"
    _write_json(slice_path, _direct_slice_payload())
    _write_json(enforced_path, _enforced_slice_payload())
    _write_json(all_family_path, _all_family_slice_payload())
    _write_json(semantic_path, _semantic_payload())
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "family_bound" / "build_formulation_probe.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--direct-bound-slice",
            str(slice_path),
            "--enforced-formulation-slice",
            str(enforced_path),
            "--all-family-direct-bound-slice",
            str(all_family_path),
            "--family-bound-semantic-audit",
            str(semantic_path),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b family-bound formulation probe" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--direct-bound-slice",
            str(slice_path),
            "--enforced-formulation-slice",
            str(enforced_path),
            "--all-family-direct-bound-slice",
            str(all_family_path),
            "--family-bound-semantic-audit",
            str(semantic_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "family_bound_formulation_probe_json=" in write.stdout
    payload = json.loads(
        (output_dir / "family_bound_formulation_probe.json").read_text(encoding="utf-8")
    )
    assert payload["comparison"]["direct_bound_value"] == 526
    assert (output_dir / "family_bound_formulation_probe.md").exists()
    assert (output_dir / "family_bound_formulation_probe.txt").exists()


def _check_status(report: dict, check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
