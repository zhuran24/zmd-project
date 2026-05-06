from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import src.search.phase3b_family_lookup_semantic_repro as repro_module
from src.search.phase3b_family_lookup_semantic_repro import (
    build_phase3b_family_lookup_semantic_repro,
    render_phase3b_family_lookup_semantic_repro_markdown,
    render_phase3b_family_lookup_semantic_repro_text,
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


def test_family_lookup_semantic_repro_reports_missing_campaign(tmp_path: Path) -> None:
    report = build_phase3b_family_lookup_semantic_repro(tmp_path / "project")

    assert report["metadata"]["source"] == "phase3b_family_lookup_semantic_repro_v1"
    assert report["status"]["outcome"] == "campaign_state_missing"
    assert _check_status(report, "campaign_state_present") == "fail"


def test_family_lookup_semantic_repro_builds_terminal_micro_models(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    _write_json(campaign_path, _campaign_state_payload())
    monkeypatch.setattr(
        repro_module,
        "_build_exact_overlay",
        lambda *args, **kwargs: (SimpleNamespace(), object()),
    )
    monkeypatch.setattr(repro_module, "_clone_model_proto", lambda proto: proto)
    monkeypatch.setattr(
        repro_module,
        "_power_family_shell_pair_table_payload",
        lambda *args, **kwargs: {
            "rows_by_family_id": {
                "0": [[0, 0], [0, 1]],
                "1": [[1, 1]],
                "2": [[0, 2]],
            },
            "slots": [
                {
                    "slot_key": "slot_a",
                    "family_lit_indices_by_family_id": {"0": 10, "1": 11},
                },
                {
                    "slot_key": "slot_b",
                    "family_lit_indices_by_family_id": {"1": 12, "2": 13},
                },
            ],
        },
    )

    report = build_phase3b_family_lookup_semantic_repro(
        project_root,
        candidate="67x13",
        anchor_indices=[119],
        variants=["coverage_only", "full_rebuilt_semantics"],
        slot_limit=2,
        family_limit_per_slot=2,
    )

    assert report["campaign_state_unchanged"] is True
    assert report["extraction"]["selected_slot_count"] == 2
    assert report["extraction"]["selected_family_ids"] == [0, 1, 2]
    assert report["status"]["outcome"] == "semantic_repro_terminal_without_zero_branch"
    assert report["repro"]["status_counts"] == {"OPTIMAL": 2}
    assert all(entry["micro_variable_count"] > 0 for entry in report["repro"]["entries"])

    markdown = render_phase3b_family_lookup_semantic_repro_markdown(report)
    text = render_phase3b_family_lookup_semantic_repro_text(report)
    assert "Family Lookup Semantic Repro" in markdown
    assert "outcome=semantic_repro_terminal_without_zero_branch" in text


def test_family_lookup_semantic_repro_cli_writes_and_no_write_skips_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    output_dir = tmp_path / "out"
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "build_phase3b_family_lookup_semantic_repro.py"

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

    assert "phase3b family lookup semantic repro" in no_write.stdout
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

    assert "family_lookup_semantic_repro_json=" in write.stdout
    payload = json.loads(
        (output_dir / "family_lookup_semantic_repro.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metadata"]["source"] == "phase3b_family_lookup_semantic_repro_v1"
    assert (output_dir / "family_lookup_semantic_repro.md").exists()
    assert (output_dir / "family_lookup_semantic_repro.txt").exists()


def _check_status(report: Mapping[str, Any], check_id: str) -> str:
    matches = [check for check in report["checks"] if check["check_id"] == check_id]
    assert len(matches) == 1
    return str(matches[0]["status"])
