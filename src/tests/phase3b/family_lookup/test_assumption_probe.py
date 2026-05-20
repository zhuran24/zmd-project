from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import src.search.phase3b.family_lookup.assumption_probe as probe_module
from src.search.phase3b.family_lookup.assumption_probe import (
    build_phase3b_family_lookup_assumption_probe,
    render_phase3b_family_lookup_assumption_probe_markdown,
    render_phase3b_family_lookup_assumption_probe_text,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _campaign_state_payload() -> dict:
    return {
        "schema_version": 3,
        "final_status": "UNKNOWN",
        "candidates": {
            "67x13": {
                "ghost_rect": {"w": 67, "h": 13, "area": 871},
                "status": "UNKNOWN",
                "proof_summary": {
                    "master_start_failure_attribution": {
                        "failed_anchor_count": 1,
                        "failed_anchor_samples": [{"anchor_idx": 119}],
                    }
                },
            }
        },
    }


class _FakeVar:
    def __init__(self, index: int) -> None:
        self._index = int(index)

    def Index(self) -> int:
        return int(self._index)


def test_family_lookup_assumption_probe_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_family_lookup_assumption_probe(tmp_path / "project")

    assert report["metadata"]["source"] == "phase3b_family_lookup_assumption_probe_v1"
    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_family_lookup_assumption_probe_runs_selected_literal_assumptions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    fake_model = SimpleNamespace(u_vars={119: _FakeVar(500)})
    monkeypatch.setattr(
        probe_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (fake_model, object()),
    )
    monkeypatch.setattr(probe_module, "_clone_model_proto", lambda proto: proto)
    monkeypatch.setattr(
        probe_module,
        "_power_family_shell_pair_table_payload",
        lambda *args, **kwargs: {
            "rows_by_family_id": {"0": [[0, 0]], "1": [[1, 1]]},
            "slots": [
                {
                    "slot_key": "slot_a",
                    "family_lit_indices_by_family_id": {"0": 10, "1": 11},
                }
            ],
        },
    )

    def fake_solve(base_proto: object, **kwargs: Any) -> dict[str, Any]:
        status = (
            "INFEASIBLE"
            if kwargs["forced_bool_true_indices"] == [11]
            else "UNKNOWN"
        )
        return {
            "anchor_idx": kwargs["anchor_idx"],
            "variant": kwargs["variant"],
            "assumption_label": kwargs["assumption_label"],
            "evaluated": True,
            "status": status,
            "wall_time": 0.1,
            "branches": 0,
            "conflicts": 0,
            "forced_bool_true_indices": list(kwargs["forced_bool_true_indices"]),
        }

    monkeypatch.setattr(probe_module, "_solve_slice_clone", fake_solve)

    report = build_phase3b_family_lookup_assumption_probe(
        project_root,
        candidate="67x13",
        anchor_indices=[119],
        variants=["power_coverage_dynamic_and_family_lookup_rebuilt_membership_only"],
        slot_limit=1,
        family_limit_per_slot=2,
    )

    assert report["status"]["outcome"] == "assumption_probe_infeasible_found"
    assert report["profile"]["assumption_count"] == 2
    assert report["probe"]["status_counts"] == {"UNKNOWN": 1, "INFEASIBLE": 1}
    assert report["campaign_state_unchanged"] is True

    markdown = render_phase3b_family_lookup_assumption_probe_markdown(report)
    text = render_phase3b_family_lookup_assumption_probe_text(report)
    assert "Family Lookup Assumption Probe" in markdown
    assert "assumption=slot_a:family_001" in text


def test_family_lookup_assumption_probe_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase3b" / "family_lookup" / "build_assumption_probe.py"

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

    assert "phase3b family lookup assumption probe" in no_write.stdout
    assert not output_dir.exists()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--output-dir",
            str(output_dir),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "family_lookup_assumption_probe_json=" in write.stdout
    payload = json.loads(
        (output_dir / "family_lookup_assumption_probe.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_family_lookup_assumption_probe_v1"
    assert (output_dir / "family_lookup_assumption_probe.md").exists()
    assert (output_dir / "family_lookup_assumption_probe.txt").exists()


def _check_status(report: Mapping[str, Any], check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
