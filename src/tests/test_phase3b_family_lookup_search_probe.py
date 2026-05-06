from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import src.search.phase3b_family_lookup_search_probe as probe_module
from src.search.phase3b_family_lookup_search_probe import (
    build_phase3b_family_lookup_search_probe,
    render_phase3b_family_lookup_search_probe_markdown,
    render_phase3b_family_lookup_search_probe_text,
)


def test_family_lookup_search_probe_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_family_lookup_search_probe(
        tmp_path / "project",
        profiles=[
            {
                "profile_id": "p0",
                "search_branching": "portfolio",
                "cp_model_probing_level": 3,
                "symmetry_level": 3,
                "worker_count": 1,
            }
        ],
    )

    assert report["metadata"]["source"] == "phase3b_family_lookup_search_probe_v1"
    assert report["status"]["outcome"] == "campaign_state_missing"
    assert report["probe"]["entries"] == []
    assert _check_status(report, "search_probe_evaluated") == "skipped"


def test_family_lookup_search_probe_aggregates_profiles(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_build(project_root: Path, **kwargs: Any) -> dict[str, Any]:
        profile = dict(kwargs["solver_parameter_profile"])
        calls.append({"profile": profile, "variants": list(kwargs["variants"])})
        status = "FEASIBLE" if profile["profile_id"] == "fixed" else "UNKNOWN"
        branches = 7 if profile["profile_id"] == "progress" else 0
        return {
            "status": {
                "evaluated": True,
                "outcome": "slice_unknown_remaining",
                "status_counts": {status: 1},
            },
            "slice_matrix": {
                "entries": [
                    {
                        "anchor_idx": 119,
                        "variant": "power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only",
                        "evaluated": True,
                        "status": status,
                        "wall_time": 0.1,
                        "branches": branches,
                        "conflicts": 0,
                        "search_branching": profile["search_branching"],
                        "cp_model_probing_level": profile["cp_model_probing_level"],
                        "symmetry_level": profile["symmetry_level"],
                        "solver_worker_count": profile["worker_count"],
                    }
                ]
            },
            "model_error": None,
            "campaign_state_unchanged": True,
        }

    monkeypatch.setattr(
        probe_module,
        "build_phase3b_forced_anchor_model_slice_diagnostic",
        fake_build,
    )

    report = build_phase3b_family_lookup_search_probe(
        tmp_path / "project",
        variants=["power_coverage_dynamic_and_family_lookup_rebuilt_ordering_only"],
        profiles=[
            {
                "profile_id": "progress",
                "search_branching": "portfolio",
                "cp_model_probing_level": 0,
                "symmetry_level": 0,
                "worker_count": 1,
            },
            {
                "profile_id": "fixed",
                "search_branching": "fixed",
                "cp_model_probing_level": 3,
                "symmetry_level": 3,
                "worker_count": 1,
            },
        ],
    )

    assert [call["profile"]["profile_id"] for call in calls] == ["progress", "fixed"]
    assert report["status"]["outcome"] == "search_probe_terminal_found"
    assert report["probe"]["status_counts"] == {"UNKNOWN": 1, "FEASIBLE": 1}
    assert report["probe"]["status_counts_by_profile"]["fixed"] == {"FEASIBLE": 1}
    assert report["probe"]["unknown_diagnostics"]["search_progress_unknown_count"] == 1
    assert report["campaign_state_unchanged"] is True

    markdown = render_phase3b_family_lookup_search_probe_markdown(report)
    text = render_phase3b_family_lookup_search_probe_text(report)
    assert "Family Lookup Search Probe" in markdown
    assert "profile=fixed" in text


def test_family_lookup_search_probe_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_family_lookup_search_probe.py"

    no_write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "phase3b family lookup search probe" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
            "--profiles-json",
            json.dumps(
                [
                    {
                        "profile_id": "p0",
                        "search_branching": "portfolio",
                        "cp_model_probing_level": 3,
                        "symmetry_level": 3,
                        "worker_count": 1,
                    }
                ]
            ),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "family_lookup_search_probe_json=" in write.stdout
    payload = json.loads(
        (output_dir / "family_lookup_search_probe.json").read_text(encoding="utf-8")
    )
    assert payload["metadata"]["source"] == "phase3b_family_lookup_search_probe_v1"
    assert (output_dir / "family_lookup_search_probe.md").exists()
    assert (output_dir / "family_lookup_search_probe.txt").exists()

    profile_file = tmp_path / "profiles.json"
    profile_file.write_text(
        json.dumps(
            [
                {
                    "profile_id": "p_file",
                    "search_branching": "fixed",
                    "cp_model_probing_level": 0,
                    "symmetry_level": 0,
                    "worker_count": 1,
                }
            ]
        ),
        encoding="utf-8",
    )
    no_write_from_file = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
            "--profiles-json",
            f"@{profile_file}",
            "--no-write",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "phase3b family lookup search probe" in no_write_from_file.stdout


def _check_status(report: Mapping[str, Any], check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
